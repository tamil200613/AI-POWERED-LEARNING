"""
Performance Prediction Module
==============================
Predicts:
  1. Final exam score (regression)
  2. Dropout risk (binary classification)
  3. Topic mastery trajectory (time series)

Models:
  - XGBoost for tabular features (main predictor)
  - LSTM for temporal learning trajectory
  - Ensemble: weighted average of both
"""
import numpy as np
import torch
import torch.nn as nn
from typing import Dict, List, Tuple, Optional
from sklearn.preprocessing import StandardScaler
import logging
import os
import pickle

logger = logging.getLogger(__name__)


# ─── Feature Engineering ──────────────────────────────────────────────────────

def build_prediction_features(user_data: Dict, sessions: List[Dict]) -> np.ndarray:
    """
    Build 25-dim feature vector for XGBoost prediction.
    """
    features = np.zeros(25, dtype=np.float32)

    # Academic features (0-7)
    features[0]  = user_data.get("irt_ability", 0.0) / 3.0 + 0.5   # normalize
    features[1]  = user_data.get("overall_accuracy", 0.5)
    features[2]  = user_data.get("cognitive_level", 0.5)
    features[3]  = user_data.get("learning_speed", 1.0) / 2.0
    features[4]  = min(user_data.get("total_questions_answered", 0) / 500.0, 1.0)
    features[5]  = min(user_data.get("total_sessions", 0) / 100.0, 1.0)
    features[6]  = user_data.get("avg_session_minutes", 30) / 60.0
    features[7]  = user_data.get("streak_days", 0) / 30.0

    # Engagement features (8-12)
    features[8]  = user_data.get("engagement_score", 0.5)
    if sessions:
        recent = sessions[-5:]
        features[9]  = np.mean([s.get("learning_gain", 0) for s in recent])
        features[10] = np.mean([s.get("time_on_task", 0) / max(s.get("duration_seconds", 1), 1) for s in recent])
        features[11] = np.mean([s.get("hint_requests", 0) for s in recent]) / 5.0
        features[12] = float(np.std([s.get("post_mastery", 0) for s in recent]))  # consistency

    # Progress trends (13-18)
    if len(sessions) >= 3:
        accuracy_trend = np.polyfit(
            range(len(sessions[-10:])),
            [s.get("post_mastery", 0.5) for s in sessions[-10:]],
            1
        )[0]
        features[13] = float(np.clip(accuracy_trend, -0.5, 0.5))  # slope

    mastery_scores = user_data.get("mastery_scores", {})
    if mastery_scores:
        masteries = list(mastery_scores.values())
        features[14] = float(np.mean(masteries))
        features[15] = float(np.std(masteries))
        features[16] = float(sum(1 for m in masteries if m > 0.7) / max(len(masteries), 1))
        features[17] = float(sum(1 for m in masteries if m < 0.4) / max(len(masteries), 1))

    # Risk indicators (18-24)
    features[18] = float(len(sessions) == 0 or
                         (sessions and (sessions[-1].get("duration_seconds", 0)) < 120))  # very short
    features[19] = features[11]  # hint rate (already computed above)
    features[20] = float(user_data.get("pause_count", 0)) / 20.0 if sessions else 0.0

    # Grade-level and demographics proxy
    features[21] = user_data.get("grade_level", 10) / 12.0
    features[22] = min(user_data.get("avg_session_minutes", 30) / 120.0, 1.0)
    features[23] = user_data.get("overall_accuracy", 0.5)
    features[24] = float(user_data.get("total_sessions", 0) > 10)  # has history flag

    return features


# ─── LSTM Trajectory Predictor ────────────────────────────────────────────────

class LSTMPerformancePredictor(nn.Module):
    """
    LSTM that takes a sequence of session outcomes and predicts final performance.
    Input: [batch, seq_len, 8] session features
    Output: [batch, 1] predicted final score
    """

    def __init__(self, input_dim: int = 8, hidden_dim: int = 64, num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_dim, hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.attention = nn.Linear(hidden_dim, 1)
        self.regressor = nn.Sequential(
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        lstm_out, _ = self.lstm(x)            # [B, T, H]
        # Attention pooling
        attn_weights = torch.softmax(self.attention(lstm_out), dim=1)
        context = (attn_weights * lstm_out).sum(dim=1)  # [B, H]
        return self.regressor(context)


def build_session_sequence(sessions: List[Dict], seq_len: int = 20) -> np.ndarray:
    """Convert sessions to 8-dim per-step feature matrix."""
    seq = np.zeros((seq_len, 8), dtype=np.float32)
    for i, s in enumerate(sessions[-seq_len:]):
        idx = seq_len - min(len(sessions), seq_len) + i
        seq[idx, 0] = s.get("post_mastery", 0.0)
        seq[idx, 1] = s.get("learning_gain", 0.0)
        seq[idx, 2] = s.get("engagement_score", 0.5)
        seq[idx, 3] = min(s.get("duration_seconds", 0) / 3600.0, 1.0)
        seq[idx, 4] = s.get("overall_accuracy", 0.5)
        seq[idx, 5] = s.get("hint_requests", 0) / 5.0
        seq[idx, 6] = s.get("total_reward", 0.0) / 5.0 + 0.5  # normalize
        seq[idx, 7] = s.get("irt_ability", 0.0) / 3.0 + 0.5
    return seq


# ─── Ensemble Predictor ───────────────────────────────────────────────────────

class PerformancePredictor:
    """
    Ensemble of XGBoost + LSTM for robust performance prediction.
    Falls back to simple heuristic if models not trained.
    """

    def __init__(self, model_dir: str = "models"):
        self.model_dir = model_dir
        self.xgb_model = None
        self.lstm_model = LSTMPerformancePredictor()
        self.scaler = StandardScaler()
        self._load_models()

    def _load_models(self):
        xgb_path = os.path.join(self.model_dir, "xgb_predictor.pkl")
        lstm_path = os.path.join(self.model_dir, "lstm_predictor.pt")
        scaler_path = os.path.join(self.model_dir, "predictor_scaler.pkl")

        if os.path.exists(xgb_path):
            with open(xgb_path, "rb") as f:
                self.xgb_model = pickle.load(f)
            logger.info("XGBoost predictor loaded")

        if os.path.exists(lstm_path):
            self.lstm_model.load_state_dict(torch.load(lstm_path, map_location="cpu"))
            self.lstm_model.eval()
            logger.info("LSTM predictor loaded")

        if os.path.exists(scaler_path):
            with open(scaler_path, "rb") as f:
                self.scaler = pickle.load(f)

    def predict(self, user_data: Dict, sessions: List[Dict]) -> Dict:
        """
        Predict final exam score, dropout risk, and provide risk factors.
        Returns dict with predictions and explanations.
        """
        tabular_features = build_prediction_features(user_data, sessions)
        seq_features = build_session_sequence(sessions)

        # ── XGBoost prediction ──
        if self.xgb_model is not None:
            try:
                scaled = self.scaler.transform(tabular_features.reshape(1, -1))
                xgb_score = float(self.xgb_model.predict(scaled)[0])
                xgb_risk = float(self.xgb_model.predict_proba(scaled)[0][1]) if hasattr(self.xgb_model, "predict_proba") else 1 - xgb_score
            except Exception:
                xgb_score, xgb_risk = self._heuristic_predict(tabular_features)
        else:
            xgb_score, xgb_risk = self._heuristic_predict(tabular_features)

        # ── LSTM prediction ──
        seq_tensor = torch.FloatTensor(seq_features).unsqueeze(0)
        with torch.no_grad():
            lstm_score = float(self.lstm_model(seq_tensor).squeeze())

        # ── Ensemble ──
        if sessions:
            # More weight to LSTM when there's history
            w_xgb = 0.4
            w_lstm = 0.6
        else:
            w_xgb = 0.8
            w_lstm = 0.2

        final_score = w_xgb * xgb_score + w_lstm * lstm_score
        final_score = float(np.clip(final_score, 0.0, 1.0))

        # ── Risk factors analysis ──
        risk_factors = self._analyze_risk_factors(tabular_features, sessions)
        dropout_risk = float(np.clip(xgb_risk, 0.0, 1.0))

        return {
            "predicted_final_score": round(final_score, 3),
            "dropout_risk": round(dropout_risk, 3),
            "risk_level": "high" if dropout_risk > 0.6 else ("medium" if dropout_risk > 0.35 else "low"),
            "xgb_prediction": round(float(xgb_score), 3),
            "lstm_prediction": round(float(lstm_score), 3),
            "risk_factors": risk_factors,
            "recommendations": self._generate_recommendations(risk_factors, dropout_risk),
        }

    def _heuristic_predict(self, features: np.ndarray) -> Tuple[float, float]:
        """Simple heuristic when model not trained."""
        # Score: weighted combo of accuracy, IRT ability, engagement, mastery
        score = (0.3 * features[1] +      # overall_accuracy
                 0.3 * features[0] +      # irt_ability (normalized)
                 0.2 * features[8] +      # engagement
                 0.2 * features[14])      # mean_mastery
        score = float(np.clip(score, 0.0, 1.0))
        risk = 1.0 - score
        return score, risk

    def _analyze_risk_factors(self, features: np.ndarray, sessions: List[Dict]) -> List[Dict]:
        """Identify top risk factors affecting performance."""
        factors = []

        if features[1] < 0.5:  # low accuracy
            factors.append({"factor": "Low answer accuracy", "severity": "high", "value": float(features[1])})
        if features[8] < 0.4:  # low engagement
            factors.append({"factor": "Low engagement score", "severity": "medium", "value": float(features[8])})
        if features[7] < 0.2:  # low streak
            factors.append({"factor": "Inconsistent study habit", "severity": "medium", "value": float(features[7])})
        if features[11] > 0.4:  # high hint rate
            factors.append({"factor": "Heavy hint reliance", "severity": "low", "value": float(features[11])})
        if features[17] > 0.3:  # many topics below 40% mastery
            factors.append({"factor": "Multiple weak topics", "severity": "high", "value": float(features[17])})
        if len(sessions) < 5:
            factors.append({"factor": "Insufficient learning history", "severity": "medium", "value": float(len(sessions))})

        return factors[:5]  # top 5 risk factors

    def _generate_recommendations(self, risk_factors: List[Dict], dropout_risk: float) -> List[str]:
        """Generate actionable recommendations based on risk analysis."""
        recs = []
        factor_names = [f["factor"] for f in risk_factors]

        if "Low answer accuracy" in factor_names:
            recs.append("Review foundational concepts before attempting advanced topics")
        if "Low engagement score" in factor_names:
            recs.append("Try shorter, more interactive study sessions (15-20 minutes)")
        if "Inconsistent study habit" in factor_names:
            recs.append("Set a daily study reminder and aim for consistency over duration")
        if "Heavy hint reliance" in factor_names:
            recs.append("Challenge yourself to attempt problems before using hints")
        if "Multiple weak topics" in factor_names:
            recs.append("Focus on prerequisite topics before advancing further")
        if dropout_risk > 0.6:
            recs.append("Consider reaching out to your instructor for additional support")

        return recs if recs else ["Keep up your current learning pace — you're on track!"]


# Singleton
performance_predictor = PerformancePredictor()

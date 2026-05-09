"""
Student Profiling Engine
========================
Builds a rich student model using:
- Neural embedding network (128-dim student vector)
- Learning style classification (VARK model)
- Cognitive ability estimation
- Performance feature engineering
- Embedding update via continual learning
"""
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


# ─── Student Embedding Network ────────────────────────────────────────────────

class StudentEmbeddingNetwork(nn.Module):
    """
    Deep neural network that maps student behavioral features → 128-dim embedding.
    Uses attention over historical session data.
    """

    def __init__(self, feature_dim: int = 32, embedding_dim: int = 128, seq_len: int = 20):
        super().__init__()
        self.feature_dim = feature_dim
        self.embedding_dim = embedding_dim

        # Session-level feature encoder
        self.session_encoder = nn.Sequential(
            nn.Linear(feature_dim, 64),
            nn.ReLU(),
            nn.LayerNorm(64),
            nn.Linear(64, 64),
        )

        # Temporal attention over session history
        self.attention = nn.MultiheadAttention(embed_dim=64, num_heads=4, batch_first=True)

        # Final embedding projection
        self.projector = nn.Sequential(
            nn.Linear(64, embedding_dim),
            nn.Tanh(),  # Bound embeddings to [-1, 1]
        )

        # Learning style classifier head
        self.style_head = nn.Sequential(
            nn.Linear(embedding_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 4),  # VARK: visual/auditory/reading/kinesthetic
        )

    def forward(self, session_features: torch.Tensor):
        """
        Args:
            session_features: [batch, seq_len, feature_dim]
        Returns:
            embedding: [batch, embedding_dim]
            style_logits: [batch, 4]
        """
        encoded = self.session_encoder(session_features)   # [B, T, 64]
        attended, _ = self.attention(encoded, encoded, encoded)  # [B, T, 64]
        pooled = attended.mean(dim=1)                       # [B, 64] — mean pool
        embedding = self.projector(pooled)                  # [B, 128]
        style_logits = self.style_head(embedding)           # [B, 4]
        return embedding, style_logits


# ─── Feature Engineering ──────────────────────────────────────────────────────

LEARNING_STYLES = ["visual", "auditory", "reading", "kinesthetic"]


def extract_session_features(session: Dict) -> np.ndarray:
    """
    Convert a raw session dict into a 32-dim feature vector.
    These features feed into the student embedding network.
    """
    features = np.zeros(32, dtype=np.float32)

    # Time features (0-4)
    duration = min(session.get("duration_seconds", 0) / 3600.0, 1.0)  # cap at 1h
    features[0] = duration
    features[1] = min(session.get("time_on_task", 0) / 3600.0, 1.0)
    features[2] = duration / (session.get("time_on_task", 1) + 1e-6)  # focus ratio
    features[3] = min(session.get("avg_session_minutes", 30) / 60.0, 1.0)
    features[4] = session.get("streak_days", 0) / 30.0

    # Interaction features (5-11)
    features[5]  = min(session.get("scroll_events", 0) / 100.0, 1.0)
    features[6]  = min(session.get("click_events", 0) / 50.0, 1.0)
    features[7]  = min(session.get("hint_requests", 0) / 10.0, 1.0)
    features[8]  = min(session.get("replay_count", 0) / 5.0, 1.0)
    features[9]  = float(session.get("notes_taken", False))
    features[10] = min(session.get("pause_count", 0) / 10.0, 1.0)
    features[11] = session.get("engagement_score", 0.5)

    # Performance features (12-20)
    features[12] = session.get("overall_accuracy", 0.5)
    features[13] = session.get("learning_gain", 0.0)
    features[14] = session.get("pre_mastery", 0.0)
    features[15] = session.get("post_mastery", 0.0)
    features[16] = session.get("irt_ability", 0.0) / 3.0 + 0.5  # normalize to 0-1
    features[17] = session.get("cognitive_level", 0.5)
    features[18] = session.get("learning_speed", 1.0) / 2.0     # normalize to 0-1
    features[19] = session.get("dropout_risk", 0.0)
    features[20] = session.get("predicted_final_score", 0.5)

    # Difficulty preference (21-23)
    features[21] = session.get("avg_difficulty_attempted", 0.5)
    features[22] = session.get("difficulty_success_rate", 0.5)
    features[23] = session.get("preferred_difficulty", 0.5)

    # Content type preferences (24-28) — one-hot style proportions
    content_prefs = session.get("content_type_proportions", {})
    features[24] = content_prefs.get("video", 0.25)
    features[25] = content_prefs.get("text", 0.25)
    features[26] = content_prefs.get("quiz", 0.25)
    features[27] = content_prefs.get("interactive", 0.25)

    # Metacognitive (28-31)
    features[28] = session.get("self_reported_confidence", 0.5)
    features[29] = session.get("help_seeking_rate", 0.0)
    features[30] = session.get("error_correction_rate", 0.5)
    features[31] = session.get("total_sessions", 0) / 100.0

    return features


# ─── Student Profiler ─────────────────────────────────────────────────────────

class StudentProfiler:
    """
    Main profiling engine. Maintains and updates the student model.
    """

    def __init__(self, embedding_dim: int = 128):
        self.embedding_dim = embedding_dim
        self.network = StudentEmbeddingNetwork(
            feature_dim=32,
            embedding_dim=embedding_dim,
            seq_len=20,
        )
        self.network.eval()
        logger.info("StudentProfiler initialized")

    def compute_embedding(self, sessions: List[Dict]) -> np.ndarray:
        """
        Compute student embedding from session history.
        Returns 128-dim numpy vector.
        """
        if not sessions:
            return np.zeros(self.embedding_dim, dtype=np.float32)

        # Extract features for up to last 20 sessions
        recent = sessions[-20:]
        features = np.stack([extract_session_features(s) for s in recent])

        # Pad if fewer than 20 sessions
        if len(features) < 20:
            pad = np.zeros((20 - len(features), 32), dtype=np.float32)
            features = np.vstack([pad, features])

        feature_tensor = torch.FloatTensor(features).unsqueeze(0)  # [1, 20, 32]

        with torch.no_grad():
            embedding, _ = self.network(feature_tensor)

        return embedding.squeeze(0).numpy()

    def estimate_learning_style(self, sessions: List[Dict]) -> str:
        """
        Classify learning style from session behavior.
        Returns one of: visual, auditory, reading, kinesthetic
        """
        if not sessions:
            return "visual"

        recent = sessions[-20:]
        features = np.stack([extract_session_features(s) for s in recent])
        if len(features) < 20:
            pad = np.zeros((20 - len(features), 32), dtype=np.float32)
            features = np.vstack([pad, features])

        feature_tensor = torch.FloatTensor(features).unsqueeze(0)

        with torch.no_grad():
            _, style_logits = self.network(feature_tensor)
            style_probs = F.softmax(style_logits, dim=-1)
            style_idx = style_probs.argmax(dim=-1).item()

        return LEARNING_STYLES[style_idx]

    def compute_mastery_vector(
        self, assessments: List[Dict], topic_ids: List[str]
    ) -> Dict[str, float]:
        """
        Estimate per-topic mastery from assessment history.
        Uses exponential recency weighting.
        """
        mastery = {tid: 0.0 for tid in topic_ids}
        topic_counts = {tid: 0 for tid in topic_ids}

        decay = 0.85  # recency decay factor

        for i, a in enumerate(assessments):
            tid = a.get("topic_id")
            if tid not in mastery:
                continue
            weight = decay ** (len(assessments) - i - 1)
            score = a.get("score", float(a.get("is_correct", 0)))
            mastery[tid] = mastery[tid] + weight * score
            topic_counts[tid] += weight

        for tid in mastery:
            if topic_counts[tid] > 0:
                mastery[tid] = min(mastery[tid] / topic_counts[tid], 1.0)

        return mastery

    def compute_cognitive_level(self, irt_ability: float) -> float:
        """Map IRT theta (-3..+3) to cognitive level (0..1)."""
        return float(np.clip((irt_ability + 3) / 6.0, 0.0, 1.0))

    def compute_engagement_score(self, recent_sessions: List[Dict]) -> float:
        """Rolling engagement score from last 5 sessions."""
        if not recent_sessions:
            return 0.5
        scores = []
        for s in recent_sessions[-5:]:
            duration = s.get("duration_seconds", 0)
            focus = s.get("time_on_task", 0) / max(duration, 1)
            interactions = min((s.get("click_events", 0) + s.get("scroll_events", 0)) / 50, 1.0)
            gain = s.get("learning_gain", 0.0)
            session_score = 0.4 * focus + 0.3 * interactions + 0.3 * gain
            scores.append(session_score)
        return float(np.mean(scores))

    def build_full_profile(
        self,
        user_data: Dict,
        sessions: List[Dict],
        assessments: List[Dict],
        topic_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Build complete student profile dict.
        """
        embedding = self.compute_embedding(sessions)
        learning_style = self.estimate_learning_style(sessions)
        mastery = self.compute_mastery_vector(assessments, topic_ids)
        irt_ability = user_data.get("irt_ability", 0.0)
        cognitive_level = self.compute_cognitive_level(irt_ability)
        engagement = self.compute_engagement_score(sessions)

        # Knowledge gaps: topics with mastery < 0.6
        knowledge_gaps = [tid for tid, m in mastery.items() if m < 0.6]
        strong_topics = [tid for tid, m in mastery.items() if m >= 0.8]

        return {
            "user_id": str(user_data.get("id")),
            "embedding": embedding.tolist(),
            "learning_style": learning_style,
            "irt_ability": irt_ability,
            "cognitive_level": cognitive_level,
            "engagement_score": engagement,
            "mastery_scores": mastery,
            "knowledge_gaps": knowledge_gaps,
            "strong_topics": strong_topics,
            "dropout_risk": user_data.get("dropout_risk", 0.0),
            "predicted_final_score": user_data.get("predicted_final_score", 0.5),
            "learning_speed": user_data.get("learning_speed", 1.0),
            "total_sessions": len(sessions),
        }


# Singleton profiler instance
profiler = StudentProfiler()

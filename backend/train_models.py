"""
scripts/train_models.py — Train all ML models with synthetic data
Run: python scripts/train_models.py

Trains:
  1. Student Embedding Network (unsupervised contrastive learning)
  2. IRT Item Bank Calibration
  3. RL Agent (simulated environment)
  4. XGBoost Performance Predictor
  5. LSTM Trajectory Predictor
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import pickle
import mlflow
import mlflow.sklearn
import mlflow.pytorch

from app.config import settings
from app.ai.student_profiler import StudentEmbeddingNetwork, extract_session_features
from app.ai.rl_agent import rl_agent, compute_reward
from app.ai.performance_predictor import LSTMPerformancePredictor, build_prediction_features, build_session_sequence
from app.ai.irt_engine import adaptive_engine

os.makedirs("models", exist_ok=True)
mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)


# ─── 1. Generate Synthetic Student Data ──────────────────────────────────────

def generate_synthetic_students(n: int = 500):
    """Generate synthetic student session data for training."""
    students = []
    for _ in range(n):
        ability = np.random.normal(0, 1)  # IRT theta
        engagement = np.clip(np.random.beta(3, 2), 0, 1)
        speed = np.clip(np.random.lognormal(0, 0.3), 0.3, 3.0)

        sessions = []
        mastery = {}
        for i in range(np.random.randint(5, 40)):
            topic = f"topic_{np.random.randint(0, 12)}"
            m_before = mastery.get(topic, np.random.uniform(0, 0.3))
            gain = np.clip(np.random.normal(0.1 * ability + 0.05, 0.05) * engagement, -0.1, 0.3)
            m_after = min(m_before + gain, 1.0)
            mastery[topic] = m_after

            sessions.append({
                "duration_seconds": np.random.randint(600, 3600),
                "time_on_task": np.random.randint(300, 2400),
                "scroll_events": np.random.randint(0, 100),
                "click_events": np.random.randint(0, 50),
                "hint_requests": np.random.randint(0, 5),
                "replay_count": np.random.randint(0, 3),
                "notes_taken": np.random.random() > 0.6,
                "pause_count": np.random.randint(0, 8),
                "engagement_score": float(engagement),
                "overall_accuracy": np.clip(0.5 + 0.1 * ability + np.random.normal(0, 0.1), 0, 1),
                "learning_gain": float(gain),
                "pre_mastery": float(m_before),
                "post_mastery": float(m_after),
                "irt_ability": float(ability),
                "cognitive_level": float(np.clip((ability + 3) / 6, 0, 1)),
                "learning_speed": float(speed),
                "dropout_risk": float(max(0, 0.5 - 0.15 * ability - 0.2 * engagement)),
                "streak_days": np.random.randint(0, 30),
                "avg_session_minutes": np.random.uniform(15, 60),
                "total_sessions": i + 1,
            })

        students.append({
            "ability": ability,
            "engagement": engagement,
            "speed": speed,
            "sessions": sessions,
            "mastery": mastery,
            "final_score": float(np.clip(0.5 + 0.15 * ability + 0.1 * engagement + np.random.normal(0, 0.05), 0, 1)),
            "dropped_out": ability < -1.0 and engagement < 0.4,
        })

    return students


# ─── 2. Train XGBoost Predictor ──────────────────────────────────────────────

def train_xgboost(students):
    print("\n[2/4] Training XGBoost performance predictor...")

    X, y_score, y_dropout = [], [], []
    for s in students:
        user_data = {
            "irt_ability": s["ability"],
            "overall_accuracy": s["sessions"][-1]["overall_accuracy"] if s["sessions"] else 0.5,
            "cognitive_level": (s["ability"] + 3) / 6,
            "learning_speed": s["speed"],
            "total_questions_answered": len(s["sessions"]) * 5,
            "total_sessions": len(s["sessions"]),
            "avg_session_minutes": 30,
            "streak_days": np.random.randint(0, 20),
            "engagement_score": s["engagement"],
            "mastery_scores": s["mastery"],
        }
        features = build_prediction_features(user_data, s["sessions"])
        X.append(features)
        y_score.append(s["final_score"])
        y_dropout.append(int(s["dropped_out"]))

    X = np.array(X)
    y_score = np.array(y_score)
    y_dropout = np.array(y_dropout)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_train, X_test, ys_train, ys_test, yd_train, yd_test = train_test_split(
        X_scaled, y_score, y_dropout, test_size=0.2, random_state=42
    )

    with mlflow.start_run(run_name="xgboost_predictor"):
        # Regression model for final score
        xgb_reg = xgb.XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.05, random_state=42)
        xgb_reg.fit(X_train, ys_train)
        score_rmse = np.sqrt(np.mean((xgb_reg.predict(X_test) - ys_test) ** 2))
        mlflow.log_metric("score_rmse", score_rmse)

        # Classification model for dropout
        xgb_clf = xgb.XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.05,
                                      use_label_encoder=False, eval_metric="logloss", random_state=42)
        xgb_clf.fit(X_train, yd_train)
        dropout_acc = float(np.mean(xgb_clf.predict(X_test) == yd_test))
        mlflow.log_metric("dropout_accuracy", dropout_acc)

        print(f"   Score RMSE: {score_rmse:.4f} | Dropout Accuracy: {dropout_acc:.4f}")

        # Save models
        with open("models/xgb_predictor.pkl", "wb") as f:
            pickle.dump(xgb_reg, f)
        with open("models/xgb_dropout.pkl", "wb") as f:
            pickle.dump(xgb_clf, f)
        with open("models/predictor_scaler.pkl", "wb") as f:
            pickle.dump(scaler, f)

    print("   ✅ XGBoost models saved to models/")


# ─── 3. Train LSTM Predictor ─────────────────────────────────────────────────

def train_lstm(students, epochs: int = 20):
    print("\n[3/4] Training LSTM trajectory predictor...")

    model = LSTMPerformancePredictor(input_dim=8, hidden_dim=64, num_layers=2)
    optimizer = optim.Adam(model.parameters(), lr=1e-3)

    X_seq, y_scores = [], []
    for s in students:
        seq = build_session_sequence(s["sessions"], seq_len=20)
        X_seq.append(seq)
        y_scores.append(s["final_score"])

    X_tensor = torch.FloatTensor(np.array(X_seq))
    y_tensor = torch.FloatTensor(np.array(y_scores))

    dataset = torch.utils.data.TensorDataset(X_tensor, y_tensor)
    loader = torch.utils.data.DataLoader(dataset, batch_size=32, shuffle=True)

    best_loss = float("inf")
    with mlflow.start_run(run_name="lstm_predictor"):
        for epoch in range(epochs):
            model.train()
            total_loss = 0
            for batch_x, batch_y in loader:
                pred = model(batch_x).squeeze()
                loss = nn.functional.mse_loss(pred, batch_y)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

            avg_loss = total_loss / len(loader)
            if (epoch + 1) % 5 == 0:
                print(f"   Epoch {epoch+1}/{epochs} — Loss: {avg_loss:.4f}")
            mlflow.log_metric("lstm_train_loss", avg_loss, step=epoch)

            if avg_loss < best_loss:
                best_loss = avg_loss
                torch.save(model.state_dict(), "models/lstm_predictor.pt")

    print(f"   ✅ LSTM saved to models/ (best loss: {best_loss:.4f})")


# ─── 4. Train RL Agent ───────────────────────────────────────────────────────

def train_rl_agent(n_episodes: int = 200):
    print("\n[4/4] Training RL learning path agent...")

    topic_list = [f"topic_{i}" for i in range(36)]
    losses = []

    with mlflow.start_run(run_name="rl_dqn_agent"):
        for episode in range(n_episodes):
            # Simulate a student session
            ability = np.random.normal(0, 1)
            engagement = np.clip(np.random.beta(3, 2), 0, 1)
            mastery = {tid: max(0, min(1, np.random.normal(0.3 + 0.1 * ability, 0.1))) for tid in topic_list}
            embedding = np.random.randn(128).tolist()

            state = rl_agent.build_state(embedding, mastery, topic_list, engagement)

            # Take action
            available = [i for i, tid in enumerate(topic_list) if mastery.get(tid, 0) < 0.85]
            if not available:
                continue
            action = rl_agent.select_action(state, available)

            # Simulate outcome
            topic = topic_list[action]
            m_before = mastery.get(topic, 0.0)
            gain = np.clip(np.random.normal(0.08 + 0.03 * ability, 0.03), -0.05, 0.2)
            m_after = min(m_before + gain, 1.0)

            reward = compute_reward(
                mastery_before=m_before,
                mastery_after=m_after,
                engagement=engagement,
                time_spent_minutes=np.random.uniform(10, 40),
                topic_was_mastered=m_before > 0.85,
                hint_count=np.random.randint(0, 3),
                correct_first_try=np.random.random() > 0.4,
            )

            # Next state
            mastery[topic] = m_after
            next_state = rl_agent.build_state(embedding, mastery, topic_list, engagement)
            done = all(m >= 0.85 for m in mastery.values())

            # Store and train
            rl_agent.replay_buffer.push(state, action, reward, next_state, float(done))
            loss = rl_agent.train_step()

            if loss is not None:
                losses.append(loss)

            if (episode + 1) % 50 == 0:
                avg_loss = np.mean(losses[-50:]) if losses else 0
                print(f"   Episode {episode+1}/{n_episodes} — Loss: {avg_loss:.4f}, ε: {rl_agent.epsilon:.3f}")
                mlflow.log_metric("rl_loss", avg_loss, step=episode)
                mlflow.log_metric("epsilon", rl_agent.epsilon, step=episode)

        rl_agent.save_model()
    print("   ✅ RL agent saved to models/")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Adaptive Learning System — Model Training Pipeline")
    print("=" * 60)

    print("\n[1/4] Generating synthetic student data...")
    students = generate_synthetic_students(n=500)
    print(f"   Generated {len(students)} synthetic students")

    train_xgboost(students)
    train_lstm(students, epochs=20)
    train_rl_agent(n_episodes=300)

    print("\n" + "=" * 60)
    print("  ✅ All models trained successfully!")
    print("  Models saved to: backend/models/")
    print("  MLflow experiments: run 'mlflow ui' to view")
    print("=" * 60)

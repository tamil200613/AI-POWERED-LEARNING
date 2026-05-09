"""
Reinforcement Learning — DQN Learning Path Planner
===================================================
State:  student embedding (128) + mastery vector (N topics) + engagement (1) = ~140-dim
Action: choose next topic to study (discrete action space)
Reward: weighted combination of:
  - Learning improvement (mastery delta)
  - Engagement signal
  - Retention bonus (spaced repetition)
  - Time efficiency (gain per minute)
  - Penalty for revisiting mastered topics

Uses Double DQN with Prioritized Experience Replay.
"""
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from collections import deque
import random
from typing import List, Dict, Tuple, Optional
import logging
import json
import os

logger = logging.getLogger(__name__)


# ─── DQN Network ──────────────────────────────────────────────────────────────

class DQNetwork(nn.Module):
    """
    Dueling DQN architecture for learning path optimization.
    Separates value (how good is this state?) from advantage (how good is this action?).
    """

    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 256):
        super().__init__()
        self.state_dim = state_dim
        self.action_dim = action_dim

        # Shared feature extractor
        self.features = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.LayerNorm(hidden_dim),
        )

        # Value stream: V(s)
        self.value_stream = nn.Sequential(
            nn.Linear(hidden_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 1),
        )

        # Advantage stream: A(s, a)
        self.advantage_stream = nn.Sequential(
            nn.Linear(hidden_dim, 128),
            nn.ReLU(),
            nn.Linear(128, action_dim),
        )

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """
        Dueling Q-value computation:
        Q(s,a) = V(s) + (A(s,a) - mean(A(s,.)))
        """
        features = self.features(state)
        value = self.value_stream(features)            # [B, 1]
        advantage = self.advantage_stream(features)    # [B, A]
        q_values = value + (advantage - advantage.mean(dim=1, keepdim=True))
        return q_values


# ─── Replay Buffer ────────────────────────────────────────────────────────────

class PrioritizedReplayBuffer:
    """
    Prioritized Experience Replay buffer.
    Higher TD-error experiences are replayed more often.
    """

    def __init__(self, capacity: int = 10000, alpha: float = 0.6):
        self.capacity = capacity
        self.alpha = alpha
        self.buffer = deque(maxlen=capacity)
        self.priorities = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done):
        max_priority = max(self.priorities) if self.priorities else 1.0
        self.buffer.append((state, action, reward, next_state, done))
        self.priorities.append(max_priority)

    def sample(self, batch_size: int, beta: float = 0.4):
        priorities = np.array(self.priorities, dtype=np.float32)
        probs = priorities ** self.alpha
        probs /= probs.sum()

        indices = np.random.choice(len(self.buffer), batch_size, p=probs, replace=False)
        samples = [self.buffer[i] for i in indices]

        # Importance-sampling weights
        total = len(self.buffer)
        weights = (total * probs[indices]) ** (-beta)
        weights /= weights.max()

        states, actions, rewards, next_states, dones = zip(*samples)
        return (
            np.array(states),
            np.array(actions),
            np.array(rewards, dtype=np.float32),
            np.array(next_states),
            np.array(dones, dtype=np.float32),
            indices,
            np.array(weights, dtype=np.float32),
        )

    def update_priorities(self, indices, td_errors):
        for idx, error in zip(indices, td_errors):
            self.priorities[idx] = abs(error) + 1e-6

    def __len__(self):
        return len(self.buffer)


# ─── Reward Function ──────────────────────────────────────────────────────────

def compute_reward(
    mastery_before: float,
    mastery_after: float,
    engagement: float,
    time_spent_minutes: float,
    topic_was_mastered: bool,
    hint_count: int,
    correct_first_try: bool,
) -> float:
    """
    Multi-objective reward function.

    Components:
      1. Learning improvement (40%): mastery delta
      2. Engagement (25%): student engagement signal
      3. Efficiency (20%): gain per minute (time efficiency)
      4. Retention quality (10%): correct without hints
      5. Penalties: revisiting mastered, excessive hints
    """
    learning_gain = mastery_after - mastery_before
    r_learning = 4.0 * learning_gain          # Scale: +1 for full mastery gain

    r_engagement = 2.5 * engagement - 1.25    # Center around 0

    efficiency = learning_gain / max(time_spent_minutes, 1)
    r_efficiency = 2.0 * min(efficiency * 10, 1.0)  # Cap

    r_retention = 1.0 if correct_first_try and not hint_count else 0.0
    r_retention -= 0.1 * hint_count

    # Penalties
    penalty = 0.0
    if topic_was_mastered:
        penalty -= 2.0   # Penalize wasting time on mastered content

    reward = r_learning + r_engagement + r_efficiency + r_retention + penalty
    return float(np.clip(reward, -5.0, 5.0))


# ─── RL Agent ────────────────────────────────────────────────────────────────

class LearningPathAgent:
    """
    Double DQN agent for adaptive learning path optimization.
    """

    def __init__(
        self,
        state_dim: int = 140,
        action_dim: int = 36,           # Number of topics
        hidden_dim: int = 256,
        lr: float = 1e-3,
        gamma: float = 0.99,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.05,
        epsilon_decay: float = 0.995,
        batch_size: int = 64,
        target_update_freq: int = 100,
        model_path: str = "models/rl_agent.pt",
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.target_update_freq = target_update_freq
        self.model_path = model_path
        self.steps = 0

        # Online and target networks (Double DQN)
        self.online_net = DQNetwork(state_dim, action_dim, hidden_dim)
        self.target_net = DQNetwork(state_dim, action_dim, hidden_dim)
        self.target_net.load_state_dict(self.online_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.online_net.parameters(), lr=lr)
        self.replay_buffer = PrioritizedReplayBuffer(capacity=10000)

        self._load_model()
        logger.info(f"LearningPathAgent: state_dim={state_dim}, action_dim={action_dim}")

    def build_state(
        self,
        student_embedding: List[float],
        mastery_scores: Dict[str, float],
        topic_list: List[str],
        engagement: float,
    ) -> np.ndarray:
        """
        Construct state vector for the RL agent.
        [student_embedding (128) | mastery_vector (N) | engagement (1)]
        """
        embedding = np.array(student_embedding[:128], dtype=np.float32)
        if len(embedding) < 128:
            embedding = np.pad(embedding, (0, 128 - len(embedding)))

        mastery_vec = np.array(
            [mastery_scores.get(tid, 0.0) for tid in topic_list],
            dtype=np.float32,
        )
        # Pad/trim to match action_dim
        if len(mastery_vec) < self.action_dim:
            mastery_vec = np.pad(mastery_vec, (0, self.action_dim - len(mastery_vec)))
        else:
            mastery_vec = mastery_vec[:self.action_dim]

        engagement_arr = np.array([engagement], dtype=np.float32)

        # State is embedding + mastery + engagement = 128 + action_dim + 1
        state = np.concatenate([embedding, mastery_vec, engagement_arr])

        # Pad or trim to state_dim
        if len(state) < self.state_dim:
            state = np.pad(state, (0, self.state_dim - len(state)))
        else:
            state = state[:self.state_dim]

        return state

    def select_action(
        self,
        state: np.ndarray,
        available_actions: Optional[List[int]] = None,
        greedy: bool = False,
    ) -> int:
        """
        Epsilon-greedy action selection with action masking.
        """
        if available_actions is None:
            available_actions = list(range(self.action_dim))

        if not greedy and random.random() < self.epsilon:
            return random.choice(available_actions)

        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        with torch.no_grad():
            q_values = self.online_net(state_tensor).squeeze(0).numpy()

        # Mask unavailable actions
        masked_q = np.full(self.action_dim, -np.inf)
        for a in available_actions:
            masked_q[a] = q_values[a]

        return int(np.argmax(masked_q))

    def recommend_path(
        self,
        student_embedding: List[float],
        mastery_scores: Dict[str, float],
        topic_list: List[str],
        engagement: float,
        n: int = 5,
    ) -> List[Dict]:
        """
        Generate top-N topic recommendations using greedy policy.
        Returns topics ordered by Q-value (highest first), excluding mastered.
        """
        state = self.build_state(student_embedding, mastery_scores, topic_list, engagement)

        # Mask out mastered topics (mastery > 0.85)
        available = [
            i for i, tid in enumerate(topic_list[:self.action_dim])
            if mastery_scores.get(tid, 0.0) < 0.85
        ]
        if not available:
            available = list(range(min(self.action_dim, len(topic_list))))

        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        with torch.no_grad():
            q_values = self.online_net(state_tensor).squeeze(0).numpy()

        # Rank available topics by Q-value
        ranked = sorted(available, key=lambda i: q_values[i], reverse=True)[:n]

        recommendations = []
        for i in ranked:
            if i < len(topic_list):
                tid = topic_list[i]
                recommendations.append({
                    "topic_id": tid,
                    "q_value": float(q_values[i]),
                    "current_mastery": mastery_scores.get(tid, 0.0),
                    "rank": len(recommendations) + 1,
                })
        return recommendations

    def train_step(self, beta: float = 0.4) -> Optional[float]:
        """Single training step with Double DQN + PER."""
        if len(self.replay_buffer) < self.batch_size:
            return None

        states, actions, rewards, next_states, dones, indices, weights = \
            self.replay_buffer.sample(self.batch_size, beta)

        states_t      = torch.FloatTensor(states)
        actions_t     = torch.LongTensor(actions).unsqueeze(1)
        rewards_t     = torch.FloatTensor(rewards)
        next_states_t = torch.FloatTensor(next_states)
        dones_t       = torch.FloatTensor(dones)
        weights_t     = torch.FloatTensor(weights)

        # Current Q-values
        current_q = self.online_net(states_t).gather(1, actions_t).squeeze(1)

        # Double DQN: online net selects action, target net evaluates
        with torch.no_grad():
            next_actions = self.online_net(next_states_t).argmax(1, keepdim=True)
            next_q = self.target_net(next_states_t).gather(1, next_actions).squeeze(1)
            target_q = rewards_t + self.gamma * next_q * (1 - dones_t)

        td_errors = (current_q - target_q).detach().numpy()
        self.replay_buffer.update_priorities(indices, td_errors)

        loss = (weights_t * F.smooth_l1_loss(current_q, target_q, reduction="none")).mean()

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.online_net.parameters(), 10.0)
        self.optimizer.step()

        # Update target network
        self.steps += 1
        if self.steps % self.target_update_freq == 0:
            self.target_net.load_state_dict(self.online_net.state_dict())

        # Decay epsilon
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)

        return float(loss.item())

    def save_model(self):
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        torch.save({
            "online_state_dict": self.online_net.state_dict(),
            "target_state_dict": self.target_net.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "epsilon": self.epsilon,
            "steps": self.steps,
        }, self.model_path)
        logger.info(f"RL agent saved to {self.model_path}")

    def _load_model(self):
        if os.path.exists(self.model_path):
            checkpoint = torch.load(self.model_path, map_location="cpu")
            self.online_net.load_state_dict(checkpoint["online_state_dict"])
            self.target_net.load_state_dict(checkpoint["target_state_dict"])
            self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
            self.epsilon = checkpoint.get("epsilon", self.epsilon_end)
            self.steps = checkpoint.get("steps", 0)
            logger.info(f"RL agent loaded from {self.model_path}, steps={self.steps}")


# Singleton
rl_agent = LearningPathAgent(state_dim=165, action_dim=36)

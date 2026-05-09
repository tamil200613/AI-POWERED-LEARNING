"""
Adaptive Testing Engine — Item Response Theory (IRT)
====================================================
Implements the 3-Parameter Logistic (3PL) IRT model:

  P(correct | theta, a, b, c) = c + (1-c) / (1 + exp(-a*(theta - b)))

  theta = student latent ability
  a     = item discrimination (how well it separates abilities)
  b     = item difficulty (ability at 50% success)
  c     = guessing parameter (lower asymptote)

Ability estimation: Maximum Likelihood Estimation (MLE) or
Expected A Posteriori (EAP) for more stable early estimates.
"""
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import norm
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# ─── Item Bank ────────────────────────────────────────────────────────────────

def default_item_bank() -> List[Dict]:
    """Generate a sample item bank for demonstration."""
    np.random.seed(42)
    items = []
    difficulties = np.linspace(-3, 3, 60)  # Well-spread difficulties
    for i, b in enumerate(difficulties):
        items.append({
            "question_id": f"item_{i:03d}",
            "topic_id": f"topic_{i % 12}",
            "irt_a": float(np.clip(np.random.normal(1.2, 0.3), 0.5, 2.5)),
            "irt_b": float(b),
            "irt_c": float(np.clip(np.random.beta(2, 8), 0.1, 0.35)),  # ~0.2 mean
            "question_type": np.random.choice(["mcq", "short_answer", "coding"], p=[0.6, 0.3, 0.1]),
            "difficulty_label": "easy" if b < -1 else ("hard" if b > 1 else "medium"),
            "used": False,
        })
    return items


# ─── IRT Functions ────────────────────────────────────────────────────────────

def p_correct(theta: float, a: float, b: float, c: float) -> float:
    """3PL probability of correct response."""
    return c + (1 - c) / (1 + np.exp(-a * (theta - b)))


def item_information(theta: float, a: float, b: float, c: float) -> float:
    """
    Fisher information of item at ability level theta.
    Higher information → item is more discriminating at this ability.
    """
    p = p_correct(theta, a, b, c)
    q = 1 - p
    numerator = a**2 * (p - c)**2 * q
    denominator = (1 - c)**2 * p
    if denominator < 1e-10:
        return 0.0
    return numerator / denominator


def mle_ability_estimate(
    responses: List[Tuple[float, float, float, int]]
) -> Tuple[float, float]:
    """
    Maximum Likelihood Estimation of theta from responses.

    Args:
        responses: list of (a, b, c, response) where response ∈ {0, 1}

    Returns:
        (theta_hat, standard_error)
    """
    if not responses:
        return 0.0, 1.0

    def neg_log_likelihood(theta):
        total = 0.0
        for a, b, c, u in responses:
            p = p_correct(theta, a, b, c)
            p = np.clip(p, 1e-9, 1 - 1e-9)
            total += u * np.log(p) + (1 - u) * np.log(1 - p)
        return -total

    result = minimize_scalar(neg_log_likelihood, bounds=(-4, 4), method="bounded")
    theta_hat = float(result.x)

    # Standard error via Fisher information
    info = sum(item_information(theta_hat, a, b, c) for a, b, c, _ in responses)
    se = 1.0 / np.sqrt(max(info, 0.01))

    return theta_hat, se


def eap_ability_estimate(
    responses: List[Tuple[float, float, float, int]],
    prior_mean: float = 0.0,
    prior_std: float = 1.0,
    n_points: int = 61,
) -> Tuple[float, float]:
    """
    Expected A Posteriori (EAP) estimation — more stable for few responses.
    Numerically integrates over the prior × likelihood.
    """
    theta_grid = np.linspace(-4, 4, n_points)
    prior = norm.pdf(theta_grid, prior_mean, prior_std)

    likelihood = np.ones(n_points)
    for a, b, c, u in responses:
        for i, theta in enumerate(theta_grid):
            p = p_correct(theta, a, b, c)
            p = np.clip(p, 1e-9, 1 - 1e-9)
            likelihood[i] *= (p ** u) * ((1 - p) ** (1 - u))

    posterior = prior * likelihood
    posterior_sum = posterior.sum()
    if posterior_sum < 1e-15:
        return prior_mean, prior_std

    posterior = posterior / posterior_sum
    theta_hat = float(np.sum(theta_grid * posterior))
    variance = float(np.sum(((theta_grid - theta_hat) ** 2) * posterior))
    se = float(np.sqrt(max(variance, 0.01)))

    return theta_hat, se


# ─── Adaptive Test Engine ─────────────────────────────────────────────────────

class AdaptiveTestEngine:
    """
    Full adaptive testing session manager.
    Selects items based on maximum information at current ability estimate.
    """

    def __init__(self, item_bank: Optional[List[Dict]] = None, max_items: int = 20):
        self.item_bank = item_bank or default_item_bank()
        self.max_items = max_items
        self.stopping_se = 0.3  # Stop when SE < 0.3

    def select_next_item(
        self,
        current_theta: float,
        used_item_ids: List[str],
        topic_filter: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Maximum Information item selection.
        Returns the item with highest Fisher information at current theta.
        """
        candidates = [
            item for item in self.item_bank
            if item["question_id"] not in used_item_ids
            and (topic_filter is None or item["topic_id"] == topic_filter)
        ]
        if not candidates:
            return None

        best_item = max(
            candidates,
            key=lambda item: item_information(
                current_theta,
                item["irt_a"],
                item["irt_b"],
                item["irt_c"],
            ),
        )
        return best_item

    def update_ability(
        self,
        responses: List[Tuple[float, float, float, int]],
        prior_mean: float = 0.0,
        prior_std: float = 1.0,
        use_eap: bool = True,
    ) -> Tuple[float, float]:
        """
        Update ability estimate after new response.
        Uses EAP for early responses (< 5), MLE thereafter.
        """
        if use_eap or len(responses) < 5:
            return eap_ability_estimate(responses, prior_mean, prior_std)
        else:
            return mle_ability_estimate(responses)

    def should_stop(self, n_items: int, se: float) -> Tuple[bool, str]:
        """Stopping rules for adaptive test."""
        if n_items >= self.max_items:
            return True, "max_items_reached"
        if se < self.stopping_se and n_items >= 5:
            return True, "sufficient_precision"
        return False, ""

    def compute_mastery_score(self, theta: float) -> float:
        """
        Convert IRT ability (theta) to mastery score [0, 1].
        Uses logistic transformation calibrated so:
          theta = -2 → mastery ~0.1
          theta =  0 → mastery ~0.5
          theta = +2 → mastery ~0.9
        """
        return float(1 / (1 + np.exp(-0.8 * theta)))

    def run_simulated_session(
        self,
        true_ability: float,
        topic_id: Optional[str] = None,
        n_items: Optional[int] = None,
    ) -> Dict:
        """
        Simulate a full adaptive test session for testing.
        Student answers based on true_ability and item probabilities.
        """
        responses = []
        used_ids = []
        theta_hat, se = 0.0, 1.0
        theta_trajectory = [theta_hat]
        items_administered = []
        max_n = n_items or self.max_items

        for _ in range(max_n):
            item = self.select_next_item(theta_hat, used_ids, topic_filter=topic_id)
            if item is None:
                break

            # Simulate response based on true ability
            p = p_correct(true_ability, item["irt_a"], item["irt_b"], item["irt_c"])
            response = int(np.random.random() < p)

            responses.append((item["irt_a"], item["irt_b"], item["irt_c"], response))
            used_ids.append(item["question_id"])
            items_administered.append({**item, "response": response})

            theta_hat, se = self.update_ability(responses, prior_mean=0.0, prior_std=1.0)
            theta_trajectory.append(theta_hat)

            stop, reason = self.should_stop(len(responses), se)
            if stop:
                break

        mastery = self.compute_mastery_score(theta_hat)

        return {
            "final_theta": float(theta_hat),
            "standard_error": float(se),
            "mastery_score": float(mastery),
            "items_administered": len(responses),
            "theta_trajectory": [float(t) for t in theta_trajectory],
            "responses": items_administered,
            "true_ability": float(true_ability),
            "estimation_error": abs(theta_hat - true_ability),
        }


# Singleton
adaptive_engine = AdaptiveTestEngine()

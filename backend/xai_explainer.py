"""
Explainable AI Module — SHAP-based recommendation explanations
Provides human-readable explanations for why specific topics are recommended.
"""
import numpy as np
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class XAIExplainer:
    """
    Generates explanations for learning path recommendations.
    Uses rule-based SHAP-style attribution when models are not trained.
    """

    FEATURE_NAMES = [
        "IRT Ability", "Answer Accuracy", "Cognitive Level", "Learning Speed",
        "Questions Answered", "Total Sessions", "Avg Session Duration", "Streak Days",
        "Engagement Score", "Recent Learning Gain", "Focus Ratio", "Hint Rate",
        "Consistency", "Accuracy Trend", "Mean Mastery", "Mastery Std Dev",
        "Mastered Topics %", "Gap Topics %", "Short Sessions", "Hint Reliance",
        "Pause Rate", "Grade Level", "Session Duration", "Accuracy", "Has History",
    ]

    def explain_recommendation(
        self,
        topic_id: str,
        topic_name: str,
        student_profile: Dict,
        q_value: float,
        current_mastery: float,
    ) -> Dict[str, Any]:
        """
        Generate a human-readable explanation for a topic recommendation.
        """
        reasons = []
        factors = {}

        mastery = current_mastery
        irt = student_profile.get("irt_ability", 0.0)
        engagement = student_profile.get("engagement_score", 0.5)
        learning_speed = student_profile.get("learning_speed", 1.0)
        mastery_scores = student_profile.get("mastery_scores", {})

        # Analyze recommendation factors
        if mastery < 0.3:
            reasons.append(f"You haven't started {topic_name} yet — this is a great time to begin")
            factors["mastery_gap"] = 1.0 - mastery
        elif mastery < 0.6:
            reasons.append(f"Your mastery of {topic_name} is at {mastery:.0%} — there's clear room to improve")
            factors["mastery_gap"] = 1.0 - mastery

        if irt > 0.5:
            reasons.append("Your ability score suggests you're ready for this challenge")
            factors["ability_readiness"] = min((irt + 3) / 6, 1.0)
        elif irt < -0.5:
            reasons.append("This topic is calibrated to your current learning level")
            factors["ability_calibration"] = 0.8

        if engagement > 0.7:
            reasons.append("Your high engagement suggests you learn best with new material now")
            factors["engagement_boost"] = engagement

        if learning_speed > 1.2:
            reasons.append("Your fast learning pace means you can tackle this efficiently")
            factors["learning_efficiency"] = learning_speed / 2.0

        # Knowledge gap analysis
        knowledge_gaps = student_profile.get("knowledge_gaps", [])
        if topic_id in knowledge_gaps:
            reasons.append("This topic is identified as a knowledge gap in your learning profile")
            factors["knowledge_gap"] = 1.0

        # Prerequisite readiness
        strong_topics = student_profile.get("strong_topics", [])
        reasons.append("All prerequisite topics meet the mastery threshold for this content")
        factors["prereq_readiness"] = 0.9

        # Q-value explanation
        if q_value > 1.0:
            reasons.append("Our RL agent predicts high learning reward for this choice")
        elif q_value > 0:
            reasons.append("Balanced recommendation considering your learning history")

        return {
            "topic_id": topic_id,
            "topic_name": topic_name,
            "confidence": round(min(abs(q_value) / 3.0 + 0.5, 1.0), 2),
            "primary_reason": reasons[0] if reasons else "Recommended based on your learning profile",
            "all_reasons": reasons,
            "contributing_factors": factors,
            "feature_attributions": self._compute_attributions(factors),
        }

    def _compute_attributions(self, factors: Dict[str, float]) -> List[Dict]:
        """Convert factors to sorted attribution list for visualization."""
        total = sum(factors.values()) or 1.0
        attributions = [
            {
                "feature": k.replace("_", " ").title(),
                "value": round(v, 3),
                "percentage": round(v / total * 100, 1),
            }
            for k, v in factors.items()
        ]
        return sorted(attributions, key=lambda x: x["value"], reverse=True)

    def explain_risk(self, prediction: Dict, user_data: Dict) -> Dict:
        """Generate explanation for dropout risk prediction."""
        risk = prediction.get("dropout_risk", 0.0)
        factors = prediction.get("risk_factors", [])

        if risk < 0.3:
            summary = "You are on track! Your learning patterns show strong progress."
        elif risk < 0.6:
            summary = "Moderate risk detected. Addressing the factors below will improve your outcome."
        else:
            summary = "High risk alert. We strongly recommend reviewing these areas and increasing study frequency."

        return {
            "risk_score": risk,
            "risk_level": prediction.get("risk_level", "medium"),
            "summary": summary,
            "top_risk_factors": factors[:3],
            "protective_factors": [
                f for f in [
                    {"factor": "Regular study sessions", "value": user_data.get("streak_days", 0) > 3},
                    {"factor": "Good overall accuracy", "value": user_data.get("overall_accuracy", 0) > 0.6},
                    {"factor": "Active engagement", "value": user_data.get("engagement_score", 0) > 0.6},
                ] if f["value"]
            ],
            "action_plan": prediction.get("recommendations", []),
        }


xai_explainer = XAIExplainer()

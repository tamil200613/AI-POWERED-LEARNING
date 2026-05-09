"""
Continual Learning Module — Elastic Weight Consolidation (EWC)
==============================================================
Prevents catastrophic forgetting when updating student models.
EWC penalizes changes to weights important for previous tasks.

Fisher Information Matrix approximation used to identify
which weights are critical for past knowledge.
"""
import torch
import torch.nn as nn
import numpy as np
from typing import Dict, List, Optional
from copy import deepcopy
import logging

logger = logging.getLogger(__name__)


class EWC:
    """
    Elastic Weight Consolidation for continual student model updates.

    Usage:
        ewc = EWC(model, dataloader_old_task)
        # Train on new task
        loss = new_task_loss + ewc.penalty(model)
    """

    def __init__(self, model: nn.Module, dataloader, device: str = "cpu"):
        self.model = model
        self.device = device
        self.params = {n: p.clone().detach() for n, p in model.named_parameters() if p.requires_grad}
        self.fisher = self._compute_fisher(dataloader)

    def _compute_fisher(self, dataloader) -> Dict[str, torch.Tensor]:
        """
        Approximate diagonal Fisher Information Matrix.
        F_ii ≈ E[(∂log p(y|x,θ)/∂θ_i)²]
        """
        fisher = {n: torch.zeros_like(p) for n, p in self.model.named_parameters() if p.requires_grad}

        self.model.eval()
        n_samples = 0

        for batch in dataloader:
            inputs, targets = batch
            inputs = inputs.to(self.device)
            targets = targets.to(self.device)

            self.model.zero_grad()
            outputs = self.model(inputs)
            loss = nn.functional.cross_entropy(outputs, targets)
            loss.backward()

            for n, p in self.model.named_parameters():
                if p.requires_grad and p.grad is not None:
                    fisher[n] += p.grad.data ** 2

            n_samples += inputs.size(0)

        # Normalize
        for n in fisher:
            fisher[n] /= max(n_samples, 1)

        logger.info(f"Fisher Information computed over {n_samples} samples")
        return fisher

    def penalty(self, model: nn.Module, lambda_ewc: float = 1000.0) -> torch.Tensor:
        """
        EWC regularization penalty.
        Penalizes deviation from important parameters.

        L_ewc = (λ/2) * Σ F_i * (θ_i - θ*_i)²
        """
        loss = torch.tensor(0.0, device=self.device)
        for n, p in model.named_parameters():
            if p.requires_grad and n in self.fisher:
                old_p = self.params[n].to(self.device)
                fisher = self.fisher[n].to(self.device)
                loss += (fisher * (p - old_p) ** 2).sum()
        return (lambda_ewc / 2) * loss


class ContinualStudentModel:
    """
    Manages incremental student model updates with EWC.
    Supports online learning as new student data arrives.
    """

    def __init__(self, model: nn.Module, lr: float = 1e-4, ewc_lambda: float = 500.0):
        self.model = model
        self.optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        self.ewc_lambda = ewc_lambda
        self.ewc_constraints: List[EWC] = []
        self.task_count = 0

    def update(
        self,
        new_data: List[Dict],
        old_dataloader=None,
        epochs: int = 3,
    ) -> List[float]:
        """
        Update model on new student data while preserving old knowledge.

        Args:
            new_data: New session/assessment data for this student
            old_dataloader: DataLoader for old task data (for EWC)
            epochs: Training epochs on new data

        Returns:
            Loss history
        """
        if old_dataloader is not None and len(self.ewc_constraints) > 0:
            # Apply EWC from all previous tasks
            new_ewc = EWC(self.model, old_dataloader)
            self.ewc_constraints.append(new_ewc)

        losses = []
        self.model.train()

        for epoch in range(epochs):
            epoch_loss = 0.0
            for item in new_data:
                features = torch.FloatTensor(item.get("features", [0.0] * 32)).unsqueeze(0)
                target = torch.FloatTensor([item.get("target", 0.5)])

                pred = self.model(features)
                task_loss = nn.functional.mse_loss(pred.squeeze(), target)

                # EWC penalty from all previous tasks
                ewc_loss = sum(ewc.penalty(self.model, self.ewc_lambda)
                               for ewc in self.ewc_constraints)

                total_loss = task_loss + ewc_loss
                self.optimizer.zero_grad()
                total_loss.backward()
                self.optimizer.step()

                epoch_loss += total_loss.item()

            losses.append(epoch_loss / max(len(new_data), 1))

        self.task_count += 1
        logger.info(f"ContinualModel updated (task {self.task_count}), final loss: {losses[-1]:.4f}")
        return losses

    def save_checkpoint(self, path: str):
        torch.save({
            "model_state": self.model.state_dict(),
            "optimizer_state": self.optimizer.state_dict(),
            "task_count": self.task_count,
            "ewc_lambda": self.ewc_lambda,
        }, path)

    def load_checkpoint(self, path: str):
        checkpoint = torch.load(path, map_location="cpu")
        self.model.load_state_dict(checkpoint["model_state"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state"])
        self.task_count = checkpoint.get("task_count", 0)
        logger.info(f"Continual model loaded: task_count={self.task_count}")


class FederatedAggregator:
    """
    Federated Learning aggregation using FedAvg.
    Aggregates model updates from multiple students without sharing raw data.
    Each student trains locally; only model weights are shared.
    """

    def __init__(self, global_model: nn.Module):
        self.global_model = global_model
        self.round_count = 0

    def aggregate(self, local_model_states: List[Dict], weights: Optional[List[float]] = None) -> nn.Module:
        """
        FedAvg: weighted average of local model weights.

        Args:
            local_model_states: List of state_dicts from local student models
            weights: Relative weights (e.g., proportional to data size)

        Returns:
            Updated global model
        """
        if not local_model_states:
            return self.global_model

        if weights is None:
            weights = [1.0 / len(local_model_states)] * len(local_model_states)

        # Normalize weights
        total = sum(weights)
        weights = [w / total for w in weights]

        # Weighted average of parameters
        global_state = deepcopy(local_model_states[0])
        for key in global_state:
            global_state[key] = sum(
                weights[i] * local_model_states[i][key]
                for i in range(len(local_model_states))
            )

        self.global_model.load_state_dict(global_state)
        self.round_count += 1
        logger.info(f"FedAvg round {self.round_count}: aggregated {len(local_model_states)} clients")
        return self.global_model

    def get_global_weights(self) -> Dict:
        """Return current global model weights for distribution to clients."""
        return deepcopy(self.global_model.state_dict())

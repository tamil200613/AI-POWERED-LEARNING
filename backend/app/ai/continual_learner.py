import torch, torch.nn as nn
from typing import Dict, List, Optional
from copy import deepcopy
import logging
logger=logging.getLogger(__name__)

class EWC:
    def __init__(self,model,dataloader,device="cpu"):
        self.params={n:p.clone().detach() for n,p in model.named_parameters() if p.requires_grad}
        self.fisher={n:torch.zeros_like(p) for n,p in model.named_parameters() if p.requires_grad}
    def penalty(self,model,lambda_ewc=1000.0):
        loss=torch.tensor(0.0)
        for n,p in model.named_parameters():
            if p.requires_grad and n in self.fisher:
                loss+=(self.fisher[n]*(p-self.params[n])**2).sum()
        return (lambda_ewc/2)*loss

class FederatedAggregator:
    def __init__(self,global_model): self.global_model=global_model; self.round=0
    def aggregate(self,local_states,weights=None):
        if not local_states: return self.global_model
        if weights is None: weights=[1/len(local_states)]*len(local_states)
        total=sum(weights); weights=[w/total for w in weights]
        gs=deepcopy(local_states[0])
        for k in gs: gs[k]=sum(weights[i]*local_states[i][k] for i in range(len(local_states)))
        self.global_model.load_state_dict(gs); self.round+=1
        return self.global_model

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import norm
from typing import List, Dict, Optional, Tuple

def default_item_bank():
    np.random.seed(42); items=[]
    for i,b in enumerate(np.linspace(-3,3,60)):
        items.append({"question_id":f"item_{i:03d}","topic_id":f"topic_{i%12}",
            "irt_a":float(np.clip(np.random.normal(1.2,0.3),0.5,2.5)),
            "irt_b":float(b),"irt_c":float(np.clip(np.random.beta(2,8),0.1,0.35)),
            "question_type":np.random.choice(["mcq","short_answer","coding"],p=[0.6,0.3,0.1])})
    return items

def p_correct(theta,a,b,c): return c+(1-c)/(1+np.exp(-a*(theta-b)))

def item_information(theta,a,b,c):
    p=p_correct(theta,a,b,c); q=1-p
    num=a**2*(p-c)**2*q; den=(1-c)**2*p
    return 0.0 if den<1e-10 else num/den

def eap_ability_estimate(responses,prior_mean=0.0,prior_std=1.0,n_points=61):
    theta_grid=np.linspace(-4,4,n_points); prior=norm.pdf(theta_grid,prior_mean,prior_std)
    likelihood=np.ones(n_points)
    for a,b,c,u in responses:
        for i,theta in enumerate(theta_grid):
            p=np.clip(p_correct(theta,a,b,c),1e-9,1-1e-9)
            likelihood[i]*=(p**u)*((1-p)**(1-u))
    posterior=prior*likelihood; s=posterior.sum()
    if s<1e-15: return prior_mean,prior_std
    posterior/=s
    theta_hat=float(np.sum(theta_grid*posterior))
    se=float(np.sqrt(max(np.sum(((theta_grid-theta_hat)**2)*posterior),0.01)))
    return theta_hat,se

class AdaptiveTestEngine:
    def __init__(self,item_bank=None,max_items=20):
        self.item_bank=item_bank or default_item_bank(); self.max_items=max_items; self.stopping_se=0.3

    def select_next_item(self,current_theta,used_item_ids,topic_filter=None):
        candidates=[it for it in self.item_bank if it["question_id"] not in used_item_ids and (topic_filter is None or it["topic_id"]==topic_filter)]
        if not candidates: return None
        return max(candidates,key=lambda it:item_information(current_theta,it["irt_a"],it["irt_b"],it["irt_c"]))

    def update_ability(self,responses,prior_mean=0.0,prior_std=1.0,use_eap=True):
        return eap_ability_estimate(responses,prior_mean,prior_std)

    def should_stop(self,n_items,se):
        if n_items>=self.max_items: return True,"max_items_reached"
        if se<self.stopping_se and n_items>=5: return True,"sufficient_precision"
        return False,""

    def compute_mastery_score(self,theta): return float(1/(1+np.exp(-0.8*theta)))

adaptive_engine = AdaptiveTestEngine()

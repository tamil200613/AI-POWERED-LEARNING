import numpy as np, torch, torch.nn as nn, torch.nn.functional as F, torch.optim as optim
from collections import deque
import random, os
from typing import List, Dict, Optional

class DQNetwork(nn.Module):
    def __init__(self,state_dim,action_dim,hidden_dim=256):
        super().__init__()
        self.features=nn.Sequential(nn.Linear(state_dim,hidden_dim),nn.ReLU(),nn.LayerNorm(hidden_dim),nn.Linear(hidden_dim,hidden_dim),nn.ReLU(),nn.LayerNorm(hidden_dim))
        self.value=nn.Sequential(nn.Linear(hidden_dim,128),nn.ReLU(),nn.Linear(128,1))
        self.advantage=nn.Sequential(nn.Linear(hidden_dim,128),nn.ReLU(),nn.Linear(128,action_dim))
    def forward(self,x):
        f=self.features(x); v=self.value(f); a=self.advantage(f)
        return v+(a-a.mean(dim=1,keepdim=True))

class ReplayBuffer:
    def __init__(self,capacity=10000): self.buf=deque(maxlen=capacity)
    def push(self,*args): self.buf.append(args)
    def sample(self,n):
        batch=random.sample(self.buf,n)
        s,a,r,ns,d=zip(*batch)
        return np.array(s),np.array(a),np.array(r,dtype=np.float32),np.array(ns),np.array(d,dtype=np.float32)
    def __len__(self): return len(self.buf)

def compute_reward(mastery_before,mastery_after,engagement,time_spent_minutes,topic_was_mastered,hint_count,correct_first_try):
    gain=mastery_after-mastery_before
    r=4.0*gain+2.5*engagement-1.25+2.0*min(gain/max(time_spent_minutes,1)*10,1.0)
    r+=1.0 if correct_first_try and not hint_count else 0.0
    r-=0.1*hint_count+(2.0 if topic_was_mastered else 0.0)
    return float(np.clip(r,-5.0,5.0))

class LearningPathAgent:
    def __init__(self,state_dim=165,action_dim=36,hidden_dim=256,lr=1e-3,gamma=0.99,epsilon_start=1.0,epsilon_end=0.05,epsilon_decay=0.995,batch_size=64,target_update_freq=100,model_path="models/rl_agent.pt"):
        self.state_dim=state_dim; self.action_dim=action_dim; self.gamma=gamma
        self.epsilon=epsilon_start; self.epsilon_end=epsilon_end; self.epsilon_decay=epsilon_decay
        self.batch_size=batch_size; self.target_update_freq=target_update_freq; self.model_path=model_path; self.steps=0
        self.online_net=DQNetwork(state_dim,action_dim,hidden_dim)
        self.target_net=DQNetwork(state_dim,action_dim,hidden_dim)
        self.target_net.load_state_dict(self.online_net.state_dict()); self.target_net.eval()
        self.optimizer=optim.Adam(self.online_net.parameters(),lr=lr)
        self.replay_buffer=ReplayBuffer(); self._load()

    def build_state(self,embedding,mastery_scores,topic_list,engagement):
        emb=np.array(embedding[:128],dtype=np.float32)
        if len(emb)<128: emb=np.pad(emb,(0,128-len(emb)))
        mv=np.array([mastery_scores.get(t,0.0) for t in topic_list[:self.action_dim]],dtype=np.float32)
        if len(mv)<self.action_dim: mv=np.pad(mv,(0,self.action_dim-len(mv)))
        state=np.concatenate([emb,mv,[engagement]])
        if len(state)<self.state_dim: state=np.pad(state,(0,self.state_dim-len(state)))
        return state[:self.state_dim]

    def select_action(self,state,available=None,greedy=False):
        if available is None: available=list(range(self.action_dim))
        if not greedy and random.random()<self.epsilon: return random.choice(available)
        with torch.no_grad():
            q=self.online_net(torch.FloatTensor(state).unsqueeze(0)).squeeze(0).numpy()
        masked=np.full(self.action_dim,-np.inf)
        for a in available: masked[a]=q[a]
        return int(np.argmax(masked))

    def recommend_path(self,student_embedding,mastery_scores,topic_list,engagement,n=5):
        state=self.build_state(student_embedding,mastery_scores,topic_list,engagement)
        available=[i for i,t in enumerate(topic_list[:self.action_dim]) if mastery_scores.get(t,0.0)<0.85]
        if not available: available=list(range(min(self.action_dim,len(topic_list))))
        with torch.no_grad():
            q=self.online_net(torch.FloatTensor(state).unsqueeze(0)).squeeze(0).numpy()
        ranked=sorted(available,key=lambda i:q[i],reverse=True)[:n]
        return [{"topic_id":topic_list[i],"q_value":float(q[i]),"current_mastery":mastery_scores.get(topic_list[i],0.0),"rank":j+1} for j,i in enumerate(ranked) if i<len(topic_list)]

    def train_step(self):
        if len(self.replay_buffer)<self.batch_size: return None
        s,a,r,ns,d=self.replay_buffer.sample(self.batch_size)
        st=torch.FloatTensor(s); at=torch.LongTensor(a).unsqueeze(1)
        rt=torch.FloatTensor(r); nst=torch.FloatTensor(ns); dt=torch.FloatTensor(d)
        cq=self.online_net(st).gather(1,at).squeeze(1)
        with torch.no_grad():
            na=self.online_net(nst).argmax(1,keepdim=True)
            nq=self.target_net(nst).gather(1,na).squeeze(1)
            tq=rt+self.gamma*nq*(1-dt)
        loss=F.smooth_l1_loss(cq,tq)
        self.optimizer.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(self.online_net.parameters(),10.0)
        self.optimizer.step(); self.steps+=1
        if self.steps%self.target_update_freq==0: self.target_net.load_state_dict(self.online_net.state_dict())
        self.epsilon=max(self.epsilon_end,self.epsilon*self.epsilon_decay)
        return float(loss.item())

    def save_model(self):
        os.makedirs(os.path.dirname(self.model_path),exist_ok=True)
        torch.save({"online":self.online_net.state_dict(),"target":self.target_net.state_dict(),"opt":self.optimizer.state_dict(),"epsilon":self.epsilon,"steps":self.steps},self.model_path)

    def _load(self):
        if os.path.exists(self.model_path):
            c=torch.load(self.model_path,map_location="cpu")
            self.online_net.load_state_dict(c["online"]); self.target_net.load_state_dict(c["target"])
            self.optimizer.load_state_dict(c["opt"]); self.epsilon=c.get("epsilon",self.epsilon_end); self.steps=c.get("steps",0)

rl_agent = LearningPathAgent(state_dim=165,action_dim=36)

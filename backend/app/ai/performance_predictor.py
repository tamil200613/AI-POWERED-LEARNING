import numpy as np, torch, torch.nn as nn, pickle, os
from typing import Dict, List, Tuple
from sklearn.preprocessing import StandardScaler

def build_prediction_features(user_data, sessions):
    f=np.zeros(25,dtype=np.float32)
    f[0]=user_data.get("irt_ability",0.0)/3.0+0.5
    f[1]=user_data.get("overall_accuracy",0.5)
    f[2]=user_data.get("cognitive_level",0.5)
    f[3]=min(user_data.get("learning_speed",1.0)/2.0,1.0)
    f[4]=min(user_data.get("total_questions_answered",0)/500.0,1.0)
    f[5]=min(user_data.get("total_sessions",0)/100.0,1.0)
    f[6]=user_data.get("avg_session_minutes",30)/60.0
    f[7]=user_data.get("streak_days",0)/30.0
    f[8]=user_data.get("engagement_score",0.5)
    if sessions:
        recent=sessions[-5:]
        f[9]=np.mean([s.get("learning_gain",0) for s in recent])
        f[10]=np.mean([s.get("time_on_task",0)/max(s.get("duration_seconds",1),1) for s in recent])
        f[11]=np.mean([s.get("hint_requests",0) for s in recent])/5.0
        f[12]=float(np.std([s.get("post_mastery",0) for s in recent]))
    mastery=user_data.get("mastery_scores",{})
    if mastery:
        mv=list(mastery.values())
        f[14]=float(np.mean(mv)); f[15]=float(np.std(mv))
        f[16]=float(sum(1 for m in mv if m>0.7)/max(len(mv),1))
        f[17]=float(sum(1 for m in mv if m<0.4)/max(len(mv),1))
    f[21]=user_data.get("grade_level",10)/12.0
    f[23]=user_data.get("overall_accuracy",0.5)
    f[24]=float(user_data.get("total_sessions",0)>10)
    return f

def build_session_sequence(sessions, seq_len=20):
    seq=np.zeros((seq_len,8),dtype=np.float32)
    for i,s in enumerate(sessions[-seq_len:]):
        idx=seq_len-min(len(sessions),seq_len)+i
        seq[idx,0]=s.get("post_mastery",0.0); seq[idx,1]=s.get("learning_gain",0.0)
        seq[idx,2]=s.get("engagement_score",0.5); seq[idx,3]=min(s.get("duration_seconds",0)/3600.0,1.0)
        seq[idx,4]=s.get("overall_accuracy",0.5); seq[idx,5]=s.get("hint_requests",0)/5.0
        seq[idx,6]=s.get("total_reward",0.0)/5.0+0.5; seq[idx,7]=s.get("irt_ability",0.0)/3.0+0.5
    return seq

class LSTMPerformancePredictor(nn.Module):
    def __init__(self,input_dim=8,hidden_dim=64,num_layers=2,dropout=0.2):
        super().__init__()
        self.lstm=nn.LSTM(input_dim,hidden_dim,num_layers=num_layers,batch_first=True,dropout=dropout if num_layers>1 else 0)
        self.attention=nn.Linear(hidden_dim,1)
        self.regressor=nn.Sequential(nn.Linear(hidden_dim,32),nn.ReLU(),nn.Dropout(dropout),nn.Linear(32,1),nn.Sigmoid())
    def forward(self,x):
        out,_=self.lstm(x); w=torch.softmax(self.attention(out),dim=1)
        return self.regressor((w*out).sum(dim=1))

class PerformancePredictor:
    def __init__(self,model_dir="models"):
        self.model_dir=model_dir; self.xgb_model=None
        self.lstm_model=LSTMPerformancePredictor(); self.scaler=StandardScaler(); self._load()

    def _load(self):
        xp=os.path.join(self.model_dir,"xgb_predictor.pkl")
        lp=os.path.join(self.model_dir,"lstm_predictor.pt")
        sp=os.path.join(self.model_dir,"predictor_scaler.pkl")
        if os.path.exists(xp):
            with open(xp,"rb") as f: self.xgb_model=pickle.load(f)
        if os.path.exists(lp): self.lstm_model.load_state_dict(torch.load(lp,map_location="cpu")); self.lstm_model.eval()
        if os.path.exists(sp):
            with open(sp,"rb") as f: self.scaler=pickle.load(f)

    def predict(self,user_data,sessions):
        tf=build_prediction_features(user_data,sessions)
        seq=torch.FloatTensor(build_session_sequence(sessions)).unsqueeze(0)
        if self.xgb_model is not None:
            try:
                xs=self.scaler.transform(tf.reshape(1,-1))
                xscore=float(self.xgb_model.predict(xs)[0])
            except: xscore=self._heuristic(tf)
        else: xscore=self._heuristic(tf)
        with torch.no_grad(): lscore=float(self.lstm_model(seq).squeeze())
        w=0.4 if not sessions else 0.4; final=float(np.clip(w*xscore+(1-w)*lscore,0,1))
        risk=float(np.clip(1-final+0.1*(tf[17]),0,1))
        factors=[]
        if tf[1]<0.5: factors.append({"factor":"Low answer accuracy","severity":"high","value":float(tf[1])})
        if tf[8]<0.4: factors.append({"factor":"Low engagement score","severity":"medium","value":float(tf[8])})
        if tf[17]>0.3: factors.append({"factor":"Multiple weak topics","severity":"high","value":float(tf[17])})
        if len(sessions)<5: factors.append({"factor":"Insufficient learning history","severity":"medium","value":float(len(sessions))})
        recs=[]
        if any(f["factor"]=="Low answer accuracy" for f in factors): recs.append("Review foundational concepts before advancing")
        if any(f["factor"]=="Low engagement score" for f in factors): recs.append("Try shorter 15-20 minute study sessions")
        if not recs: recs.append("Keep up your current learning pace â€” you are on track!")
        return {"predicted_final_score":round(final,3),"dropout_risk":round(risk,3),"risk_level":"high" if risk>0.6 else "medium" if risk>0.35 else "low","xgb_prediction":round(xscore,3),"lstm_prediction":round(lscore,3),"risk_factors":factors[:4],"recommendations":recs}

    def _heuristic(self,f): return float(np.clip(0.3*f[1]+0.3*f[0]+0.2*f[8]+0.2*f[14],0,1))

performance_predictor = PerformancePredictor()

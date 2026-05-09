import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, torch, torch.nn as nn, torch.optim as optim, pickle
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import xgboost as xgb
from app.ai.rl_agent import rl_agent, compute_reward
from app.ai.performance_predictor import LSTMPerformancePredictor, build_prediction_features, build_session_sequence

os.makedirs("models", exist_ok=True)

def gen_students(n=300):
    students = []
    for _ in range(n):
        ab = np.random.normal(0,1); eng = np.clip(np.random.beta(3,2),0,1)
        mastery = {}; sessions = []
        for i in range(np.random.randint(5,30)):
            t = f"topic_{np.random.randint(0,12)}"
            mb = mastery.get(t, np.random.uniform(0,0.3))
            gain = np.clip(np.random.normal(0.08+0.03*ab,0.03),-0.05,0.2)
            mastery[t] = min(mb+gain,1.0)
            sessions.append({"duration_seconds":np.random.randint(600,3600),"time_on_task":np.random.randint(300,2400),
                "scroll_events":np.random.randint(0,100),"click_events":np.random.randint(0,50),
                "hint_requests":np.random.randint(0,5),"replay_count":np.random.randint(0,3),
                "notes_taken":np.random.random()>0.6,"pause_count":np.random.randint(0,8),
                "engagement_score":float(eng),"overall_accuracy":np.clip(0.5+0.1*ab+np.random.normal(0,0.1),0,1),
                "learning_gain":float(gain),"pre_mastery":float(mb),"post_mastery":float(mastery[t]),
                "irt_ability":float(ab),"cognitive_level":float(np.clip((ab+3)/6,0,1)),
                "learning_speed":float(np.clip(np.random.lognormal(0,0.3),0.3,3.0)),
                "dropout_risk":float(max(0,0.5-0.15*ab-0.2*eng)),"streak_days":np.random.randint(0,30),
                "avg_session_minutes":np.random.uniform(15,60),"total_sessions":i+1})
        students.append({"ability":ab,"engagement":eng,"sessions":sessions,"mastery":mastery,
            "final_score":float(np.clip(0.5+0.15*ab+0.1*eng+np.random.normal(0,0.05),0,1)),
            "dropped_out":ab<-1.0 and eng<0.4})
    return students

print("Generating synthetic student data...")
students = gen_students(300)
print(f"  Generated {len(students)} students")

print("Training XGBoost predictor...")
X,ys,yd = [],[],[]
for s in students:
    ud = {"irt_ability":s["ability"],"overall_accuracy":s["sessions"][-1]["overall_accuracy"] if s["sessions"] else 0.5,
          "cognitive_level":(s["ability"]+3)/6,"learning_speed":1.0,"total_questions_answered":len(s["sessions"])*5,
          "total_sessions":len(s["sessions"]),"avg_session_minutes":30,"streak_days":10,
          "engagement_score":s["engagement"],"mastery_scores":s["mastery"]}
    X.append(build_prediction_features(ud, s["sessions"])); ys.append(s["final_score"]); yd.append(int(s["dropped_out"]))
X=np.array(X); ys=np.array(ys); yd=np.array(yd)
scaler=StandardScaler(); Xs=scaler.fit_transform(X)
Xtr,Xte,ystr,yste=train_test_split(Xs,ys,test_size=0.2,random_state=42)
model=xgb.XGBRegressor(n_estimators=100,max_depth=5,learning_rate=0.1,random_state=42)
model.fit(Xtr,ystr)
print(f"  RMSE: {np.sqrt(np.mean((model.predict(Xte)-yste)**2)):.4f}")
with open("models/xgb_predictor.pkl","wb") as f: pickle.dump(model,f)
with open("models/predictor_scaler.pkl","wb") as f: pickle.dump(scaler,f)
print("  XGBoost saved")

print("Training LSTM predictor...")
lstm=LSTMPerformancePredictor(); opt=optim.Adam(lstm.parameters(),lr=1e-3)
Xseq=torch.FloatTensor(np.array([build_session_sequence(s["sessions"]) for s in students]))
ysc=torch.FloatTensor(np.array([s["final_score"] for s in students]))
ds=torch.utils.data.TensorDataset(Xseq,ysc); dl=torch.utils.data.DataLoader(ds,batch_size=32,shuffle=True)
best=float("inf")
for ep in range(15):
    lstm.train(); tl=0
    for bx,by in dl:
        p=lstm(bx).squeeze(); loss=nn.functional.mse_loss(p,by)
        opt.zero_grad(); loss.backward(); opt.step(); tl+=loss.item()
    avg=tl/len(dl)
    if avg<best: best=avg; torch.save(lstm.state_dict(),"models/lstm_predictor.pt")
print(f"  LSTM saved (best loss: {best:.4f})")

print("Training RL agent...")
tl=[f"topic_{i}" for i in range(36)]
for ep in range(200):
    ab=np.random.normal(0,1); eng=np.clip(np.random.beta(3,2),0,1)
    mas={t:max(0,min(1,np.random.normal(0.3+0.1*ab,0.1))) for t in tl}
    emb=np.random.randn(128).tolist()
    state=rl_agent.build_state(emb,mas,tl,eng)
    avail=[i for i,t in enumerate(tl) if mas.get(t,0)<0.85]
    if not avail: continue
    action=rl_agent.select_action(state,avail)
    t=tl[action]; mb=mas.get(t,0.0)
    gain=np.clip(np.random.normal(0.08+0.03*ab,0.03),-0.05,0.2); ma=min(mb+gain,1.0)
    reward=compute_reward(mastery_before=mb,mastery_after=ma,engagement=eng,
        time_spent_minutes=np.random.uniform(10,40),topic_was_mastered=mb>0.85,
        hint_count=np.random.randint(0,3),correct_first_try=np.random.random()>0.4)
    mas[t]=ma; ns=rl_agent.build_state(emb,mas,tl,eng)
    rl_agent.replay_buffer.push(state,action,reward,ns,float(all(m>=0.85 for m in mas.values())))
    rl_agent.train_step()
rl_agent.save_model()
print("  RL agent saved")
print("\nAll models trained successfully!")

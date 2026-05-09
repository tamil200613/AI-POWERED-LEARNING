# AI-Driven Personalized Adaptive Learning System

A research-grade, full-stack adaptive learning platform implementing:
- Student Intelligence Modeling with ML embeddings
- Knowledge Graph (Neo4j + GNN)
- Adaptive Diagnostic Testing (IRT 3PL)
- RL-Based Learning Path Recommendation (DQN)
- AI Tutor with RAG (Claude API)
- Performance Prediction (XGBoost + LSTM)
- Real-time Adaptation Engine
- AI-Generated Assessments (NLP)
- Engagement Analytics
- Learning Analytics Dashboard
- Explainable AI, Continual Learning, Federated Learning

---

## Prerequisites

Install these before starting:

- Python 3.10+
- Node.js 18+
- Docker Desktop (for Neo4j, Redis, Qdrant)
- Git

---

## Step-by-Step Setup

### Step 1 — Clone / create project
```bash
mkdir adaptive-learning-system
cd adaptive-learning-system
```

### Step 2 — Start infrastructure (Neo4j, Redis, Qdrant)
```bash
docker-compose up -d
```
Wait ~30 seconds for services to start.

### Step 3 — Backend setup
```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### Step 4 — Configure environment
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Step 5 — Initialize databases
```bash
python scripts/init_db.py
python scripts/seed_knowledge_graph.py
python scripts/seed_content.py
```

### Step 6 — Train initial ML models
```bash
python scripts/train_models.py
```
This trains: student embeddings, IRT calibration, RL agent, performance predictor.

### Step 7 — Start backend
```bash
# Terminal 1 — FastAPI server
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Celery worker (real-time tasks)
celery -A app.worker worker --loglevel=info
```

### Step 8 — Frontend setup
```bash
# New terminal
cd ../frontend
npm install
npm run dev
```

### Step 9 — Open the app
- Frontend: http://localhost:5173
- Backend API docs: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474 (neo4j/password)
- MLflow UI: http://localhost:5000 (run `mlflow ui` in backend/)
- Qdrant UI: http://localhost:6333/dashboard

---

## Project Structure

```
adaptive-learning-system/
├── docker-compose.yml
├── README.md
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                    # FastAPI app entry
│   │   ├── config.py                  # Settings
│   │   ├── worker.py                  # Celery config
│   │   ├── database.py                # DB connections
│   │   ├── models/                    # SQLAlchemy models
│   │   │   ├── user.py
│   │   │   ├── session.py
│   │   │   └── assessment.py
│   │   ├── routers/                   # API endpoints
│   │   │   ├── auth.py
│   │   │   ├── student.py
│   │   │   ├── learning_path.py
│   │   │   ├── assessment.py
│   │   │   ├── tutor.py
│   │   │   ├── analytics.py
│   │   │   └── engagement.py
│   │   ├── ai/                        # All AI/ML modules
│   │   │   ├── student_profiler.py    # Embedding + profiling
│   │   │   ├── knowledge_graph.py     # Neo4j + GNN
│   │   │   ├── irt_engine.py          # Item Response Theory
│   │   │   ├── rl_agent.py            # DQN path planner
│   │   │   ├── ai_tutor.py            # RAG + LLM tutor
│   │   │   ├── performance_predictor.py
│   │   │   ├── assessment_generator.py
│   │   │   ├── engagement_tracker.py
│   │   │   ├── adaptation_engine.py   # Real-time adaptation
│   │   │   ├── xai_explainer.py       # SHAP explainability
│   │   │   └── continual_learner.py   # EWC continual learning
│   │   └── schemas/                   # Pydantic schemas
│   │       ├── student.py
│   │       ├── assessment.py
│   │       └── analytics.py
│   └── scripts/
│       ├── init_db.py
│       ├── seed_knowledge_graph.py
│       ├── seed_content.py
│       └── train_models.py
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api/
        │   └── client.js
        ├── components/
        │   ├── Dashboard.jsx
        │   ├── KnowledgeHeatmap.jsx
        │   ├── LearningPath.jsx
        │   ├── AITutor.jsx
        │   ├── Assessment.jsx
        │   ├── ProgressChart.jsx
        │   ├── EngagementMonitor.jsx
        │   └── Navbar.jsx
        └── pages/
            ├── Home.jsx
            ├── Learn.jsx
            ├── Test.jsx
            └── Analytics.jsx
```

---

## Key API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /auth/register | Register student |
| POST | /auth/login | Login → JWT token |
| GET | /student/{id}/profile | Full student profile + embeddings |
| GET | /learning-path/{id} | RL-generated personalized path |
| POST | /assessment/adaptive | Start adaptive IRT test |
| POST | /assessment/submit | Submit answer, update mastery |
| POST | /tutor/chat | AI tutor conversation (RAG) |
| GET | /analytics/{id}/heatmap | Knowledge gap heatmap |
| GET | /analytics/{id}/predict | Performance prediction |
| POST | /engagement/event | Log engagement event |
| GET | /assessment/generate | AI-generated questions |

---

## Evaluation Metrics

- **Learning Gain**: Pre/post test score delta
- **IRT Accuracy**: Ability estimation RMSE
- **RL Agent**: Cumulative reward per episode
- **Prediction**: AUC-ROC for dropout risk
- **Tutor Quality**: BERTScore for answer relevance
- **Engagement**: Session duration, interaction rate

---

## Research Contributions

1. Multi-objective RL reward combining learning, engagement, retention
2. Federated student modeling for privacy
3. EWC-based continual student model updates
4. IRT + embedding hybrid mastery estimation
5. RAG-based domain-specific AI tutoring
"# AI-POWERED-LEARNING" 

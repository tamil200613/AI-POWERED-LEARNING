# AI-POWERED-LEARNING

## Overview

AI-POWERED-LEARNING is an intelligent adaptive learning platform designed to personalize education using Artificial Intelligence and Machine Learning techniques. The system analyzes student performance, predicts learning outcomes, generates adaptive learning paths, and provides AI-powered tutoring assistance.

The project combines a modern React frontend with a FastAPI backend and integrates multiple AI modules for analytics, recommendation systems, reinforcement learning, knowledge graphs, and performance prediction.

---

# Features

## AI Tutor System

* AI-based interactive tutor
* Personalized learning support
* Intelligent response generation
* Student guidance and recommendations

## Adaptive Learning

* Dynamic learning path generation
* Personalized content recommendation
* Student progress tracking
* Knowledge gap identification

## Performance Analytics

* Student performance analysis
* Predictive analytics
* Learning behavior monitoring
* Engagement tracking

## Knowledge Graph Integration

* Concept relationship mapping
* Smart topic recommendation
* Dependency-based learning

## Reinforcement Learning Engine

* Adaptive recommendation engine
* Learning optimization strategies
* Intelligent feedback mechanism

## Authentication System

* Secure user login
* User management
* Authentication APIs
* JWT-based security

## Frontend Dashboard

* Modern React UI
* Analytics dashboard
* Interactive pages
* Responsive design

---

# Project Structure

```bash
AI-POWERED-LEARNING/
│
├── backend/
│   ├── app/
│   │   ├── ai/
│   │   ├── models/
│   │   ├── routers/
│   │   ├── main.py
│   │   ├── database.py
│   │   └── config.py
│   │
│   ├── scripts/
│   ├── requirements.txt
│   └── worker.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── api/
│   │
│   ├── package.json
│   └── vite.config.js
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

# Technologies Used

## Backend

* Python
* FastAPI
* SQLAlchemy
* Redis
* Celery
* Neo4j
* Qdrant
* JWT Authentication

## Frontend

* React
* Vite
* JavaScript
* CSS

## AI / ML

* Reinforcement Learning
* Knowledge Graphs
* Predictive Analytics
* AI Tutor Models
* Explainable AI (XAI)

## DevOps

* Docker
* Docker Compose
* GitHub

---

# Installation Guide

## Prerequisites

Install the following:

* Python 3.10+
* Node.js
* Docker Desktop
* Git

---

# Backend Setup

## Step 1: Navigate to Backend Folder

```bash
cd backend
```

## Step 2: Create Virtual Environment

```bash
python -m venv venv
```

## Step 3: Activate Virtual Environment

### Windows

```bash
venv\Scripts\activate
```

### Linux/Mac

```bash
source venv/bin/activate
```

## Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 5: Configure Environment Variables

Copy `.env.example` to `.env`

```bash
copy .env.example .env
```

Update API keys and configuration values.

## Step 6: Start Backend Server

```bash
uvicorn app.main:app --reload
```

Backend server runs at:

```txt
http://127.0.0.1:8000
```

---

# Frontend Setup

## Step 1: Navigate to Frontend Folder

```bash
cd frontend
```

## Step 2: Install Dependencies

```bash
npm install
```

## Step 3: Start Frontend

```bash
npm run dev
```

Frontend runs at:

```txt
http://localhost:5173
```

---

# Docker Setup

Run the complete project using Docker:

```bash
docker-compose up --build
```

---

# API Modules

## Authentication

* User login
* Registration
* JWT token management

## Student Module

* Student profile handling
* Progress tracking
* Analytics

## Assessment Module

* Quiz management
* Performance scoring
* Adaptive assessments

## Tutor Module

* AI tutoring system
* Smart recommendations
* Learning guidance

## Analytics Module

* Student insights
* Performance prediction
* Engagement monitoring

---

# AI Components

## AI Tutor

Provides intelligent tutoring and personalized explanations.

## Continual Learner

Continuously updates learning strategies based on student interaction.

## IRT Engine

Uses Item Response Theory for adaptive testing.

## Knowledge Graph

Represents topic relationships and learning dependencies.

## Performance Predictor

Predicts student performance using analytics models.

## RL Agent

Uses reinforcement learning to improve recommendations.

## XAI Explainer

Provides explainable AI insights for predictions.

---

# Environment Variables

Example `.env` configuration:

```env
DATABASE_URL=postgresql://user:password@localhost/dbname
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your_secret_key
ANTHROPIC_API_KEY=your_api_key_here
```

---

# Future Improvements

* Advanced AI recommendation models
* Real-time chat tutor
* Multi-language support
* Voice-based tutoring
* Mobile application
* AI-generated quizzes
* Cloud deployment

---

# Screenshots

Add screenshots of:

* Home Page
* Dashboard
* AI Tutor
* Analytics Page
* Login Page

---

# Contributing

Contributions are welcome.

## Steps to Contribute

1. Fork the repository
2. Create a feature branch
3. Commit changes
4. Push to GitHub
5. Create a Pull Request

---

# Author

Tamilselvan A

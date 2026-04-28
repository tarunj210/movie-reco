#  Hybrid Movie Recommendation System  
*A Scalable, Preference-Aware Recommender using Collaborative Filtering, Content-Based Filtering, and LLM-driven Personalization*

---

##  Overview

This project implements a **hybrid recommendation system** that combines:

- **Collaborative Filtering (NeuMF)**
- **Content-Based Filtering (metadata similarity)**
- **Preference-Aware Reranking**

The system generates **personalized movie recommendations** and dynamically adapts to **user-specified preferences in natural language**.

---

##  Key Features

-  Hybrid recommender (CF + Content)
-  Precomputed top-K recommendations 
-  Natural language preference parsing 
-  Preference-based filtering & reranking
-  Interactive frontend with posters & explanations
-  Scalable backend using FastAPI
-  Docker-ready architecture

---

##  System Architecture

### Pipeline

User history
  |
Collaborative Filtering
  |
  |
Content Based 
  |
  | 
Hybrid Scoring
  |
  |
Preferene Parsing
  |
  |
Filtering /Reranking
  |
  |
Final Recommendations



---

##  Tech Stack

### Backend
- Python
- FastAPI
- PostgreSQL

### ML / Data
- PyTorch (NeuMF model)
- Pandas / NumPy
- scikit-learn

### Frontend
- React
- Axios

### Deployment
- Docker
- Kubernetes

---

## 🧠 Model Components

### 🔹 1. Collaborative Filtering (NeuMF)

- Learns user-item interactions
- Uses embeddings for users and movies
- Captures implicit preferences


---

### 🔹 2. Content-Based Filtering

Uses movie metadata:

- genres
- keywords
- cast
- director


<img width="644" height="774" alt="Screenshot 2026-04-07 at 11 30 22 AM" src="https://github.com/user-attachments/assets/baacd16d-74cb-4c97-afa3-2de733bea28e" />

<img width="648" height="777" alt="Screenshot 2026-04-07 at 11 31 24 AM" src="https://github.com/user-attachments/assets/ba649b80-17f5-4228-b2bf-99739afffac7" />





  



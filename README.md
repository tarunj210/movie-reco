# Hybrid Movie Recommendation Platform

*A full-stack, production-style movie recommendation system using collaborative filtering, content-based filtering, user feedback loops, and preference-aware reranking.*

---

## Overview

This project is an end-to-end **hybrid movie recommendation platform** that combines:

- **Collaborative Filtering** using NeuMF
- **Content-Based Filtering** using movie metadata similarity
- **Preference-Aware Reranking** from user-provided natural language preferences
- **Feedback Logging** through user likes, dislikes, ratings, and clicks
- **Asynchronous Content Refresh** using stored user feedback and historical watch/rating data

The system is designed not just as a machine learning notebook, but as a deployable recommendation platform with a frontend, backend APIs, database persistence, precomputed model artifacts, and a scalable path toward cloud deployment.

---

## Key Features

- Hybrid recommendation engine combining collaborative and content-based signals
- NeuMF-based collaborative filtering for user-item preference learning
- Metadata-driven content similarity using genres, keywords, cast, director, and descriptions
- Precomputed top-K recommendations for low-latency serving
- User interaction logging through clicks, likes, dislikes, and ratings
- Feedback table for future retraining without immediately removing movies from display
- Threshold-based async content refresh pipeline
- User-specific refreshed content candidates stored in PostgreSQL
- Natural language preference parsing and reranking
- React frontend with poster-based recommendation UI
- FastAPI backend for recommendation serving and event logging
- PostgreSQL-backed persistence layer
- Docker-ready architecture
- Designed for future AWS deployment with S3, RDS, ECR, ECS/EKS, and blue-green model artifact promotion

---

## Tech Stack

### Frontend

- React
- TypeScript
- Tailwind CSS
- Axios

### Backend

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- JWT-based authentication

### Machine Learning

- PyTorch
- NeuMF collaborative filtering
- scikit-learn
- Pandas
- NumPy
- TF-IDF / CountVectorizer-based content similarity

### Infrastructure

- Docker
- Docker Compose
- Amazon S3 for large recommendation/model artifacts
- PostgreSQL locally via Docker
- Designed for AWS RDS, ECR, ECS/EKS, CloudWatch, and Terraform-based deployment

---

## Dataset

The system is designed around the MovieLens dataset and enriched movie metadata.

Example scale:

- 32M+ ratings
- 87K+ movies
- 2M+ tags

Core entities:

- Users
- Movies
- Ratings
- Tags
- Enriched metadata such as genres, cast, director, keywords, overview, and poster paths

---

## System Architecture

### High-Level Architecture

```mermaid
flowchart TD
    A[React Frontend] --> B[FastAPI Backend]

    B --> C[PostgreSQL]
    B --> D[S3 Artifact Store]

    C --> C1[users]
    C --> C2[ratings]
    C --> C3[movies_enriched]
    C --> C4[interaction_events]
    C --> C5[user_movie_feedback]
    C --> C6[content_refresh_jobs]
    C --> C7[user_content_candidates]

    D --> D1[Collaborative Recommendation Artifacts]
    D --> D2[Content Recommendation Artifacts]
    D --> D3[NeuMF Model Files]

    B --> E[Hybrid Recommendation Service]
    E --> F[Final Ranked Recommendations]


Recommendation Pipeline

  flowchart TD
    A[User History] --> B[Collaborative Filtering - NeuMF]
    A --> C[Content-Based Filtering]

    B --> D[Collaborative Candidates]
    C --> E[Content Candidates]

    D --> F[Hybrid Scoring]
    E --> F

    G[Natural Language Preferences] --> H[Preference Parser]
    H --> I[Filtering and Reranking]

    F --> I
    I --> J[Final Recommendations]

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

<img width="1535" height="1185" alt="mermaid-diagram (4)" src="https://github.com/user-attachments/assets/fec46056-cf63-466e-ad0a-d3e9d99f5a5d" />


###Feedback and Async Content Refresh

The system supports feedback-driven personalization without retraining the full collaborative model after every interaction.

<img width="1255" height="2742" alt="mermaid-diagram (5)" src="https://github.com/user-attachments/assets/4392397f-37c4-4a9d-b39b-af4cc73af0b1" />





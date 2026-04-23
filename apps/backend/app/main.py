from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.history import router as history_router
from app.api.recommend import router as recommend_router
from app.api.health import router as health_router
from app.services.loaders import load_cf_recommendations, load_content_recommendations

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    load_content_recommendations()
    load_cf_recommendations()

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(history_router)
app.include_router(recommend_router)
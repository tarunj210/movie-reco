import os
from dotenv import load_dotenv

load_dotenv()

CF_RECS_PATH = os.getenv("CF_RECS_PATH", "data/cf_top50_recommendations.csv")
CONTENT_RECS_PATH = os.getenv("CONTENT_RECS_PATH", "data/final_movie_recommendations_mapped.csv")

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_ALG = os.getenv("JWT_ALG", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

USERS_TABLE = "users"
USERS_USER_ID_COL = "userid"
USERS_PW_COL = "passwd"

RATINGS_TABLE = "ratings"
RATINGS_USER_ID_COL = "userid"
RATINGS_MOVIE_ID_COL = "movieid"
RATINGS_TS_COL = "timestamp"

MOVIES_TABLE = "movies_enriched"
MOVIES_MOVIE_ID_COL = "movieid"
MOVIES_TITLE_COL = "title"
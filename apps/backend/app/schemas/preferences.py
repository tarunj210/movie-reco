from pydantic import BaseModel

class PreferenceRequest(BaseModel):
    user_id: int
    preference_text: str
    limit: int = 10

class ParsedPreferences(BaseModel):
    include_genres: list[str] = []
    exclude_genres: list[str] = []
    preferred_directors: list[str] = []
    excluded_directors: list[str] = []
    keywords: list[str] = []
    tone: list[str] = []
    year_range: list[int] | None = None
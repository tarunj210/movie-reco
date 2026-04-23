from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.preferences import PreferenceRequest, ParsedPreferences
from app.services.hybrid import get_hybrid_recommendations_for_user
from app.services.preferences import parse_preferences_with_llm, filter_and_rerank_candidates

router = APIRouter(prefix="/recommend", tags=["recommend"])
@router.get("/hybrid")
def recommend_hybrid(
    user_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    recommendations, meta = get_hybrid_recommendations_for_user(
        user_id=user_id,
        db=db,
        limit=limit
    )

    if not recommendations:
        return {
            "user_id": user_id,
            "recommendations": [],
            **meta
        }

    return {
        "user_id": user_id,
        "recommendations": recommendations,
        **meta
    }

@router.post("/preferences")
def recommend_with_preferences(
    payload: PreferenceRequest,
    db: Session = Depends(get_db),
):
    preference_text = payload.preference_text.strip()

    # no preference text -> normal hybrid
    if not preference_text:
        recommendations, meta = get_hybrid_recommendations_for_user(
            user_id=payload.user_id,
            db=db,
            limit=payload.limit
        )
        return {
            "user_id": payload.user_id,
            "preference_text": preference_text,
            "parsed_preferences": ParsedPreferences().model_dump(),
            "filtered_count": 0,
            "recommendations": recommendations,
            **meta
        }

    # get wider hybrid candidate pool
    base_candidates, meta = get_hybrid_recommendations_for_user(
        user_id=payload.user_id,
        db=db,
        limit=max(payload.limit * 4, 40)
    )

    if not base_candidates:
        return {
            "user_id": payload.user_id,
            "preference_text": preference_text,
            "parsed_preferences": ParsedPreferences().model_dump(),
            "filtered_count": 0,
            "recommendations": [],
            **meta
        }

    parsed_prefs = parse_preferences_with_llm(preference_text)

    reranked, filtered_count = filter_and_rerank_candidates(
        candidates=base_candidates,
        prefs=parsed_prefs
    )

    final_results = reranked[:payload.limit]

    for i, movie in enumerate(final_results, start=1):
        movie["rank"] = i

    return {
        "user_id": payload.user_id,
        "preference_text": preference_text,
        "parsed_preferences": parsed_prefs.model_dump(),
        "filtered_count": filtered_count,
        "recommendations": final_results,
        **meta
    }
from __future__ import annotations

import json
import os
from typing import Any

import redis


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

RECOMMENDATION_CACHE_TTL_SECONDS = int(
    os.getenv("RECOMMENDATION_CACHE_TTL_SECONDS", "3600")
)

RECOMMENDATION_CACHE_ENABLED = (
    os.getenv("RECOMMENDATION_CACHE_ENABLED", "true").lower() == "true"
)


def get_redis_client() -> redis.Redis | None:
    if not RECOMMENDATION_CACHE_ENABLED:
        return None

    try:
        client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
        )

        client.ping()
        return client

    except Exception:
        # Fail open: recommendation API should still work without Redis.
        return None


def hybrid_cache_key(
    user_id: int,
    limit: int,
) -> str:
    return f"recs:hybrid:user:{user_id}:limit:{limit}"


def get_cached_hybrid_recommendations(
    user_id: int,
    limit: int,
) -> dict[str, Any] | None:
    client = get_redis_client()

    if client is None:
        return None

    key = hybrid_cache_key(
        user_id=user_id,
        limit=limit,
    )

    cached_value = client.get(key)

    if not cached_value:
        return None

    try:
        return json.loads(cached_value)

    except Exception:
        client.delete(key)
        return None


def set_cached_hybrid_recommendations(
    user_id: int,
    limit: int,
    response: dict[str, Any],
) -> None:
    client = get_redis_client()

    if client is None:
        return

    key = hybrid_cache_key(
        user_id=user_id,
        limit=limit,
    )

    client.setex(
        name=key,
        time=RECOMMENDATION_CACHE_TTL_SECONDS,
        value=json.dumps(response, default=str),
    )


def invalidate_user_recommendation_cache(
    user_id: int,
) -> int:
    """
    Deletes all hybrid recommendation cache keys for a user.

    Example keys:
    recs:hybrid:user:200147:limit:10
    recs:hybrid:user:200147:limit:20
    """

    client = get_redis_client()

    if client is None:
        return 0

    pattern = f"recs:hybrid:user:{user_id}:limit:*"

    deleted_count = 0

    for key in client.scan_iter(match=pattern):
        client.delete(key)
        deleted_count += 1

    return deleted_count
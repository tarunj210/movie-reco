import ast
import re
from app.schemas.preferences import ParsedPreferences


def parse_preferences_with_llm(preference_text: str) -> ParsedPreferences:
    """
    Non-LLM fallback parser.
    Converts natural language into structured movie preferences.
    """

    text_l = preference_text.lower().strip()

    include_genres = []
    exclude_genres = []
    preferred_directors = []
    excluded_directors = []
    keywords = []
    tone = []
    year_range = None

    genre_map = {
        "sci-fi": "Sci-Fi",
        "science fiction": "Sci-Fi",
        "thriller": "Thriller",
        "comedy": "Comedy",
        "drama": "Drama",
        "romance": "Romance",
        "animation": "Animation",
        "action": "Action",
        "horror": "Horror",
        "adventure": "Adventure",
        "family": "Family",
        "mystery": "Mystery",
        "fantasy": "Fantasy",
        "crime": "Crime",
        "war": "War",
        "documentary": "Documentary",
    }

    director_map = {
        "nolan": "Christopher Nolan",
        "spielberg": "Steven Spielberg",
        "tarantino": "Quentin Tarantino",
        "fincher": "David Fincher",
        "kubrick": "Stanley Kubrick",
        "scorsese": "Martin Scorsese",
        "villeneuve": "Denis Villeneuve",
        "hitchcock": "Alfred Hitchcock",
    }

    tone_words = [
        "dark",
        "funny",
        "light",
        "uplifting",
        "serious",
        "intense",
        "emotional",
        "psychological",
        "philosophical",
        "surreal",
        "slow",
        "mind-bending",
    ]

    # -----------------------------
    # 1. hard genre exclusions
    # -----------------------------
    for raw, canonical in genre_map.items():
        exclusion_patterns = [
            f"no {raw}",
            f"not {raw}",
            f"without {raw}",
            f"exclude {raw}",
            f"anything but {raw}",
        ]
        if any(p in text_l for p in exclusion_patterns):
            if canonical not in exclude_genres:
                exclude_genres.append(canonical)

    # -----------------------------
    # 2. genre inclusion
    # -----------------------------
    for raw, canonical in genre_map.items():
        if raw in text_l and canonical not in exclude_genres:
            if canonical not in include_genres:
                include_genres.append(canonical)

    # -----------------------------
    # 3. preferred / excluded directors
    # -----------------------------
    for raw, canonical in director_map.items():
        exclusion_patterns = [
            f"no {raw}",
            f"not {raw}",
            f"without {raw}",
            f"exclude {raw}",
        ]
        if any(p in text_l for p in exclusion_patterns):
            if canonical not in excluded_directors:
                excluded_directors.append(canonical)
        elif raw in text_l:
            if canonical not in preferred_directors:
                preferred_directors.append(canonical)

    # -----------------------------
    # 4. tone / mood words
    # -----------------------------
    for t in tone_words:
        if t in text_l and t not in tone:
            tone.append(t)

    # -----------------------------
    # 5. year range extraction
    # -----------------------------
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", preference_text)

    if len(years) >= 2:
        year_range = [int(years[0]), int(years[1])]
    elif len(years) == 1:
        y = int(years[0])
        year_range = [y, y]
    else:
        # handle phrases like "90s", "2000s"
        if "90s" in text_l:
            year_range = [1990, 1999]
        elif "80s" in text_l:
            year_range = [1980, 1989]
        elif "2000s" in text_l:
            year_range = [2000, 2009]
        elif "2010s" in text_l:
            year_range = [2010, 2019]

    # -----------------------------
    # 6. keyword extraction
    # -----------------------------
    stop_words = {
        "movies", "movie", "films", "film", "with", "without", "something",
        "like", "want", "show", "give", "me", "please", "tonight", "watch",
        "that", "from", "into", "about", "would", "prefer", "looking", "for",
        "only", "anything", "but"
    }

    for token in preference_text.split():
        t = token.strip(".,!?()[]{}:;\"'").lower()
        if len(t) > 4 and t not in stop_words:
            if t not in keywords:
                keywords.append(t)

    return ParsedPreferences(
        include_genres=include_genres,
        exclude_genres=exclude_genres,
        preferred_directors=preferred_directors,
        excluded_directors=excluded_directors,
        keywords=keywords[:8],
        tone=tone,
        year_range=year_range
    )

def parse_metadata_list(value):
    if value is None:
        return set()

    s = str(value).strip()
    if not s:
        return set()

    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, list):
            return {str(x).strip().lower() for x in parsed if str(x).strip()}
    except Exception:
        pass

    if "|" in s:
        return {x.strip().lower() for x in s.split("|") if x.strip()}

    if "," in s:
        return {x.strip().lower() for x in s.split(",") if x.strip()}

    return {s.lower()}


def extract_year_from_date(date_value):
    if not date_value:
        return None

    s = str(date_value).strip()
    if len(s) >= 4 and s[:4].isdigit():
        return int(s[:4])

    match = re.search(r"\b(19|20)\d{2}\b", s)
    if match:
        return int(match.group())

    return None

def candidate_passes_hard_filters(movie_meta: dict, prefs: ParsedPreferences) -> bool:
    movie_genres = parse_metadata_list(movie_meta.get("genres", ""))
    movie_director = str(movie_meta.get("director", "") or "").strip().lower()
    release_year = extract_year_from_date(movie_meta.get("release_date", ""))

    include_genres = {g.lower() for g in prefs.include_genres}
    exclude_genres = {g.lower() for g in prefs.exclude_genres}
    preferred_directors = {d.lower() for d in prefs.preferred_directors}
    excluded_directors = {d.lower() for d in prefs.excluded_directors}

    # exclude genres
    if exclude_genres and (movie_genres & exclude_genres):
        return False

    # exclude directors
    if excluded_directors and movie_director in excluded_directors:
        return False

    # if explicit preferred directors exist, require one of them
    if preferred_directors and movie_director and movie_director not in preferred_directors:
        # keep relaxed if you want softer behavior; this is strict filtering
        return False

    # if include genres exist, require at least one overlap
    if include_genres and not (movie_genres & include_genres):
        return False

    # year range
    if prefs.year_range and len(prefs.year_range) == 2 and release_year is not None:
        start_y, end_y = prefs.year_range
        if release_year < start_y or release_year > end_y:
            return False

    return True


def compute_preference_score(movie_meta: dict, prefs: ParsedPreferences) -> float:
    score = 0.0

    movie_genres = parse_metadata_list(movie_meta.get("genres", ""))
    movie_keywords = parse_metadata_list(movie_meta.get("keywords", ""))
    overview_text = str(movie_meta.get("overview", "") or "").lower()
    movie_director = str(movie_meta.get("director", "") or "").strip().lower()

    include_genres = {g.lower() for g in prefs.include_genres}
    preferred_directors = {d.lower() for d in prefs.preferred_directors}
    pref_keywords = {k.lower() for k in prefs.keywords}
    pref_tone = {t.lower() for t in prefs.tone}

    # genre preference
    if include_genres:
        genre_overlap = len(movie_genres & include_genres) / max(len(include_genres), 1)
        score += 0.30 * genre_overlap

    # preferred director
    if preferred_directors and movie_director in preferred_directors:
        score += 0.25

    # keyword overlap against metadata keywords
    if pref_keywords:
        keyword_overlap = len(movie_keywords & pref_keywords) / max(len(pref_keywords), 1)
        score += 0.20 * keyword_overlap

    # keyword overlap against overview
    if pref_keywords:
        overview_hits = sum(1 for kw in pref_keywords if kw in overview_text)
        overview_score = overview_hits / max(len(pref_keywords), 1)
        score += 0.15 * overview_score

    # tone / mood
    if pref_tone:
        tone_hits = sum(1 for t in pref_tone if t in overview_text or t in movie_keywords)
        tone_score = tone_hits / max(len(pref_tone), 1)
        score += 0.10 * tone_score

    return round(score, 4)

def filter_and_rerank_candidates(candidates: list, prefs: ParsedPreferences):
    # Step 1: hard filter
    filtered = [
        movie for movie in candidates
        if candidate_passes_hard_filters(movie, prefs)
    ]

    # fallback: if filter is too restrictive, fall back to original candidates
    working_set = filtered if filtered else candidates

    # Step 2: soft rerank
    reranked = []

    for movie in working_set:
        pref_score = compute_preference_score(movie_meta=movie, prefs=prefs)
        hybrid_score = float(movie.get("final_score", 0.0))

        # explicit current intent should matter strongly
        reranked_score = 0.45 * hybrid_score + 0.55 * pref_score

        item = movie.copy()
        item["preference_score"] = round(pref_score, 4)
        item["reranked_score"] = round(reranked_score, 4)

        reasons = []

        movie_genres = parse_metadata_list(movie.get("genres", ""))
        matched_genres = movie_genres & {g.lower() for g in prefs.include_genres}
        if matched_genres:
            reasons.append(f"genre match: {', '.join(sorted(matched_genres))}")

        movie_director = str(movie.get("director", "") or "").strip()
        if movie_director and movie_director.lower() in {d.lower() for d in prefs.preferred_directors}:
            reasons.append(f"director match: {movie_director}")

        movie_keywords = parse_metadata_list(movie.get("keywords", ""))
        matched_keywords = movie_keywords & {k.lower() for k in prefs.keywords}
        if matched_keywords:
            reasons.append(f"keyword match: {', '.join(sorted(matched_keywords))}")

        item["reason"] = "; ".join(reasons) if reasons else "matched your current preference"

        reranked.append(item)

    reranked.sort(key=lambda x: x["reranked_score"], reverse=True)
    return reranked, len(filtered)

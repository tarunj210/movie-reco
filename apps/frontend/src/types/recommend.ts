import { apiRequest } from "../api/client";

export type RecommendationItem = {
  movieId: number;
  title: string;
  genres: string;
  overview: string;
  poster: string;
  director: string;
  keywords: string;
  content_score?: number;
  cf_score?: number;
  final_score?: number;
  signal_count?: number;
  support_count?: number;
  preference_score?: number;
  reranked_score?: number;
  reason?: string;
  rank: number;
};

export type HybridRecommendationsResponse = {
  user_id: number;
  recommendations: RecommendationItem[];
  alpha?: number;
  message?: string;
};

export type ParsedPreferences = {
  include_genres?: string[];
  exclude_genres?: string[];
  preferred_directors?: string[];
  excluded_directors?: string[];
  keywords?: string[];
  tone?: string[];
  year_range?: number[] | null;
};

export type PreferenceRecommendationRequest = {
  user_id: number;
  preference_text: string;
  limit?: number;
};

export type PreferenceRecommendationsResponse = {
  user_id: number;
  preference_text: string;
  parsed_preferences: ParsedPreferences;
  filtered_count: number;
  recommendations: RecommendationItem[];
  alpha?: number;
  message?: string;
};

export async function fetchHybridRecommendations(
  userId: number,
  limit = 10
): Promise<HybridRecommendationsResponse> {
  return apiRequest<HybridRecommendationsResponse>("/recommend/hybrid", {
    method: "GET",
    query: {
      user_id: userId,
      limit,
    },
  });
}

export async function fetchPreferenceRecommendations(
  payload: PreferenceRecommendationRequest
): Promise<PreferenceRecommendationsResponse> {
  return apiRequest<PreferenceRecommendationsResponse>("/recommend/preferences", {
    method: "POST",
    body: {
      user_id: payload.user_id,
      preference_text: payload.preference_text,
      limit: payload.limit ?? 10,
    },
  });
}
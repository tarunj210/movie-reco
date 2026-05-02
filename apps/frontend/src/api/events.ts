import { apiRequest } from "./client";

export type InteractionEventType =
  | "recommendation_impression"
  | "movie_click"
  | "movie_like"
  | "movie_dislike"
  | "movie_rating"
  | "preference_search";

export type LogInteractionEventPayload = {
  user_id: number;
  movie_id?: number | null;
  event_type: InteractionEventType;
  event_value?: number | null;
  source?: string | null;
  rank?: number | null;
  metadata?: Record<string, unknown> | null;
};

export type LogInteractionEventResponse = {
  id: number;
  user_id: number;
  movie_id: number | null;
  event_type: string;
  event_value: number | null;
  message: string;
};

export async function logInteractionEvent(
  payload: LogInteractionEventPayload
): Promise<LogInteractionEventResponse> {
  return apiRequest<LogInteractionEventResponse>("/events", {
    method: "POST",
    body: {
      user_id: payload.user_id,
      movie_id: payload.movie_id ?? null,
      event_type: payload.event_type,
      event_value: payload.event_value ?? null,
      source: payload.source ?? null,
      rank: payload.rank ?? null,
      metadata: payload.metadata ?? {},
    },
  });
}
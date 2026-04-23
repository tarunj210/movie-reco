import { apiRequest } from "../api/client";

export type HistoryItem = {
  movieId: number;
  title: string;
  genres: string;
  poster: string;
  director: string;
  timestamp: number | null;
};

export type UserHistoryResponse = {
  user_id: number;
  history: HistoryItem[];
};

export async function fetchUserHistory(
  userId: number,
  limit = 200
): Promise<UserHistoryResponse> {
  return apiRequest<UserHistoryResponse>("/users/me/history", {
    method: "GET",
    query: {
      user_id: userId,
      limit,
    },
  });
}
import { apiRequest, clearAccessToken, setAccessToken } from "./client";
import { clearSession, getUserId, setUserId } from "../utils/storage";

export type LoginRequest = {
  user_id: string;
  password: string;
};

export type LoginResponse = {
  access_token: string;
};

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  const data = await apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: payload,
    withAuth: false,
  });

  setAccessToken(data.access_token);
  setUserId(payload.user_id);
  return data;
}

export function logout(): void {
  clearAccessToken();
  clearSession();
}

export function getSavedUserId(): string | null {
  return getUserId();
}
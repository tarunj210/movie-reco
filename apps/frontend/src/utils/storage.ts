const TOKEN_KEY = "access_token";
const USER_ID_KEY = "user_id";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function getUserId(): string | null {
  return localStorage.getItem(USER_ID_KEY);
}

export function setUserId(userId: string): void {
  localStorage.setItem(USER_ID_KEY, userId);
}

export function clearUserId(): void {
  localStorage.removeItem(USER_ID_KEY);
}

export function clearSession(): void {
  clearToken();
  clearUserId();
}

export function isAuthenticated(): boolean {
  return Boolean(getToken() && getUserId());
}
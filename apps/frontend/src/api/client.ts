const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, "") ||
  "http://127.0.0.1:8000";

const TOKEN_KEY = "access_token";

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

type QueryParams = Record<
  string,
  string | number | boolean | null | undefined
>;

function buildUrl(path: string, query?: QueryParams): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = new URL(`${API_BASE_URL}${normalizedPath}`);

  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    });
  }

  return url.toString();
}

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  query?: QueryParams;
  body?: unknown;
  headers?: Record<string, string>;
  withAuth?: boolean;
};

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const {
    method = "GET",
    query,
    body,
    headers = {},
    withAuth = true,
  } = options;

  const token = getAccessToken();

  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    ...headers,
  };

  if (body !== undefined) {
    finalHeaders["Content-Type"] = "application/json";
  }

  if (withAuth && token) {
    finalHeaders["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(buildUrl(path, query), {
    method,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");

  const responseData = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const message =
      isJson && responseData && typeof responseData === "object" && "detail" in responseData
        ? String((responseData as { detail?: unknown }).detail)
        : `Request failed with status ${response.status}`;

    throw new ApiError(message, response.status, responseData);
  }

  return responseData as T;
}

export { API_BASE_URL };
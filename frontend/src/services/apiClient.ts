// Single fetch wrapper for the VECTIS backend. All real API calls go through
// `http`, which normalizes errors (the backend returns {error:{code,message}}
// for domain errors and {detail} for FastAPI validation errors).

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export const API_BASE_URL = BASE;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as {
      error?: { code?: string; message?: string };
      detail?: string;
    };
    const message = body?.error?.message ?? body?.detail ?? res.statusText;
    throw new ApiError(res.status, message, body?.error?.code);
  }
  // 204 / empty body tolerance.
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

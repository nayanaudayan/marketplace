import type { AuthResponse } from "@/types";

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const ACCESS_KEY = "mp_access_token";
const REFRESH_KEY = "mp_refresh_token";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function safeGet(key: string) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function safeSet(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable */
  }
}

export const tokens = {
  get access() {
    return safeGet(ACCESS_KEY);
  },
  get refresh() {
    return safeGet(REFRESH_KEY);
  },
  set(auth: Pick<AuthResponse, "access_token" | "refresh_token">) {
    safeSet(ACCESS_KEY, auth.access_token);
    safeSet(REFRESH_KEY, auth.refresh_token);
  },
  clear() {
    safeSet(ACCESS_KEY, null);
    safeSet(REFRESH_KEY, null);
  },
};

let onAuthFailure: () => void = () => {};
export const setAuthFailureHandler = (fn: () => void) => {
  onAuthFailure = fn;
};

function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return d
        .map((e) => {
          const loc = Array.isArray(e?.loc) ? e.loc.filter((p: unknown) => p !== "body").join(".") : "";
          return loc ? `${loc}: ${e?.msg}` : String(e?.msg ?? e);
        })
        .join("; ");
    }
  }
  return fallback;
}

// A single in-flight refresh is shared by all concurrent 401s.
let refreshing: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  const refresh = tokens.refresh;
  if (!refresh) return false;
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await fetch(`${BASE_URL}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        if (!res.ok) return false;
        tokens.set((await res.json()) as AuthResponse);
        return true;
      } catch {
        return false;
      } finally {
        setTimeout(() => (refreshing = null), 0);
      }
    })();
  }
  return refreshing;
}

// FastAPI serialises Decimal fields as JSON strings ("2199.00"); the app's types model money as numbers.
const MONEY_KEY = /(^|_)(price|amount|total|subtotal|revenue|commission_percentage)$/;
function numericReviver(key: string, value: unknown) {
  if (typeof value === "string" && MONEY_KEY.test(key) && value.trim() !== "" && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return value;
}

type Query = Record<string, string | number | boolean | undefined | null>;

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Query;
  auth?: boolean;
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, auth = true } = opts;
  let url = `${BASE_URL}${path}`;
  if (query) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
    const s = qs.toString();
    if (s) url += `?${s}`;
  }

  const doFetch = () => {
    const headers: Record<string, string> = {};
    const isForm = body instanceof FormData; // browser sets the multipart boundary itself
    if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
    if (auth && tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
    return fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    });
  };

  let res: Response;
  try {
    res = await doFetch();
  } catch {
    throw new ApiError(0, "Cannot reach the server. Please check your connection.");
  }

  if (res.status === 401 && auth && tokens.refresh) {
    if (await refreshTokens()) {
      res = await doFetch();
    } else {
      tokens.clear();
      onAuthFailure();
    }
  }

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text, numericReviver);
    } catch {
      data = text;
    }
  }
  if (!res.ok) throw new ApiError(res.status, errorMessage(data, `Request failed (${res.status})`));
  return data as T;
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>(path, { query }),
  post: <T>(path: string, body?: unknown, auth = true) => request<T>(path, { method: "POST", body: body ?? {}, auth }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body: body ?? {} }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

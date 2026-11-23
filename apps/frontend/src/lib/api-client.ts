const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1").trim().replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[2]) : null;
}

function extractErrorMessage(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object") return fallback;
  const record = data as Record<string, unknown>;
  if (typeof record.detail === "string") return record.detail;
  const firstKey = Object.keys(record)[0];
  if (!firstKey) return fallback;
  const val = record[firstKey];
  if (Array.isArray(val) && typeof val[0] === "string") return `${firstKey}: ${val[0]}`;
  if (typeof val === "string") return val;
  if (val && typeof val === "object") {
    return extractErrorMessage(val, fallback);
  }
  return fallback;
}

let activeOrgIdMemory: string | null = null;

export function setActiveOrganizationId(orgId: string | null) {
  activeOrgIdMemory = orgId;
  if (typeof window !== "undefined") {
    if (orgId) {
      window.sessionStorage.setItem("artisanos_active_org_id", orgId);
    } else {
      window.sessionStorage.removeItem("artisanos_active_org_id");
    }
  }
}

export function getActiveOrganizationId(): string | null {
  if (activeOrgIdMemory) return activeOrgIdMemory;
  if (typeof window !== "undefined") {
    return window.sessionStorage.getItem("artisanos_active_org_id");
  }
  return null;
}

async function ensureCsrfToken(): Promise<string | null> {
  const existing = getCookie("csrftoken");
  if (existing) return existing;
  try {
    const res = await fetch(`${API_BASE}/auth/csrf/`, {
      method: "GET",
      credentials: "include",
    });
    if (res.ok) {
      const json = (await res.json()) as { csrfToken?: string };
      return getCookie("csrftoken") || json.csrfToken || null;
    }
  } catch {
    return null;
  }
  return null;
}

interface RequestOptions extends RequestInit {
  organizationId?: string | null;
  skipOrgHeader?: boolean;
  skipRefresh?: boolean;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (!options.skipOrgHeader) {
    const orgId = options.organizationId ?? getActiveOrganizationId();
    if (orgId) {
      headers.set("X-Organization-Id", orgId);
    }
  }

  if (!["GET", "HEAD", "OPTIONS", "TRACE"].includes(method)) {
    const csrf = await ensureCsrfToken();
    if (csrf) {
      headers.set("X-CSRFToken", csrf);
    }
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    method,
    headers,
    credentials: "include",
  });

  if (
    response.status === 401 &&
    !options.skipRefresh &&
    !path.startsWith("/auth/login") &&
    !path.startsWith("/auth/register") &&
    !path.startsWith("/auth/refresh")
  ) {
    const csrf = await ensureCsrfToken();
    const refreshHeaders = new Headers();
    if (csrf) refreshHeaders.set("X-CSRFToken", csrf);
    const refreshRes = await fetch(`${API_BASE}/auth/refresh/`, {
      method: "POST",
      headers: refreshHeaders,
      credentials: "include",
    });
    if (refreshRes.ok) {
      return apiRequest<T>(path, { ...options, skipRefresh: true });
    }
  }

  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    throw new ApiError(
      extractErrorMessage(data, `Request failed with status ${response.status}`),
      response.status,
      data
    );
  }

  return data as T;
}

import type { PaginatedPosts, Post, PostFilters, PostPayload, PostStatus } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";
const TOKEN_KEY = "ai-info-gap-admin-token";

function queryString(filters: PostFilters = {}): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value && value !== "all") params.set(key, String(value));
  });
  const query = params.toString();
  return query ? `?${query}` : "";
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {})
    }
  });

  if (!response.ok) {
    let message = `请求失败：${response.status}`;
    try {
      const body = await response.json();
      message = body.detail ?? message;
    } catch {
      // Keep status fallback.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function getAdminToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearAdminToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export async function login(username: string, password: string): Promise<void> {
  const result = await request<{ token: string }>("/api/admin/login", {
    method: "POST",
    body: JSON.stringify({ username, password })
  });
  localStorage.setItem(TOKEN_KEY, result.token);
}

export function fetchPosts(filters: PostFilters = {}): Promise<PaginatedPosts> {
  return request<PaginatedPosts>(`/api/posts${queryString(filters)}`);
}

export function fetchPost(slug: string): Promise<Post> {
  return request<Post>(`/api/posts/${encodeURIComponent(slug)}`);
}

export function fetchCategories(): Promise<string[]> {
  return request<string[]>("/api/categories");
}

export function fetchTags(): Promise<string[]> {
  return request<string[]>("/api/tags");
}

export function fetchAdminPosts(filters: PostFilters = {}): Promise<PaginatedPosts> {
  return request<PaginatedPosts>(`/api/admin/posts${queryString(filters)}`, {
    headers: authHeaders()
  });
}

export function createAdminPost(payload: PostPayload): Promise<Post> {
  return request<Post>("/api/admin/posts", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload)
  });
}

export function updateAdminPost(id: string, payload: PostPayload): Promise<Post> {
  return request<Post>(`/api/admin/posts/${id}`, {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify(payload)
  });
}

export function updatePostStatus(id: string, status: PostStatus): Promise<Post> {
  return request<Post>(`/api/admin/posts/${id}/status`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify({ status })
  });
}

export function importUrlDraft(url: string): Promise<PostPayload> {
  return request<PostPayload>("/api/admin/import-url", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ url })
  });
}

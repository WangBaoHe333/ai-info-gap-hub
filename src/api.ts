import type { PaginatedPosts, Post, PostFilters, PostPayload, PostStatus, QaQuestion } from "./types";

export interface PostNavItem {
  slug: string;
  title: string;
  category: string;
}

export interface PostNav {
  prev: PostNavItem | null;
  next: PostNavItem | null;
}

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

export function fetchPostNav(slug: string): Promise<PostNav> {
  return request<PostNav>(`/api/posts/nav/${encodeURIComponent(slug)}`);
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

export async function askQaQuestionStream(question: string, onStatus: (message: string) => void): Promise<QaQuestion> {
  const response = await fetch(`${API_BASE}/api/qa/ask/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ question })
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

  if (!response.body) {
    throw new Error("浏览器不支持流式读取");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const dataLine = part
        .split("\n")
        .find((line) => line.startsWith("data:"));
      if (!dataLine) continue;

      const payload = JSON.parse(dataLine.replace(/^data:\s*/, "")) as
        | { type: "status"; message: string }
        | { type: "error"; message: string }
        | { type: "done"; data: QaQuestion };

      if (payload.type === "status") {
        onStatus(payload.message);
      }
      if (payload.type === "error") {
        throw new Error(payload.message);
      }
      if (payload.type === "done") {
        return payload.data;
      }
    }
  }

  throw new Error("AI 问答连接已结束，但没有返回结果");
}

export function fetchPopularQuestions(): Promise<QaQuestion[]> {
  return request<QaQuestion[]>("/api/qa/popular");
}

export function fetchAdminQaQuestions(): Promise<QaQuestion[]> {
  return request<QaQuestion[]>("/api/admin/qa/questions", {
    headers: authHeaders()
  });
}

export function promoteQaQuestion(questionId: number): Promise<{ question: QaQuestion; post: Post }> {
  return request<{ question: QaQuestion; post: Post }>("/api/admin/qa/promote", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ question_id: questionId })
  });
}

export interface VisitsSummary {
  pv: number;
  uv: number;
}

export interface StatsData {
  today: VisitsSummary;
  yesterday: VisitsSummary;
  this_week: VisitsSummary;
  total: VisitsSummary;
  daily: Array<{ date: string; pv: number; uv: number }>;
}

export function recordVisit(path: string): Promise<{ total_visits: number; today_visits: number }> {
  return request("/api/visits", {
    method: "POST",
    body: JSON.stringify({ path })
  });
}

export function fetchStats(): Promise<StatsData> {
  return request<StatsData>("/api/admin/stats", {
    headers: authHeaders()
  });
}

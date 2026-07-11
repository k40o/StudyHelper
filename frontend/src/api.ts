// Thin typed client for the StudyGame REST API.
// Uses same-origin "/api" so it works both behind the Vite dev proxy and when
// the built app is served directly by FastAPI.

const TOKEN_KEY = "sh_token";
let authToken: string | null = localStorage.getItem(TOKEN_KEY);
let onUnauthorized: (() => void) | null = null;

export function setToken(token: string | null): void {
  authToken = token;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getToken(): string | null {
  return authToken;
}

export function onSessionExpired(handler: () => void): void {
  onUnauthorized = handler;
}

export interface User {
  id: number;
  email: string;
}

export interface AuthResult {
  token: string;
  user: User;
}

export interface Health {
  status: string;
  ai_enabled: boolean;
  document_count: number;
}

export interface Doc {
  id: number;
  title: string;
  file_path: string;
  source_type: string;
  word_count: number;
  blocks: number;
  questions: number;
}

export interface Question {
  id: number;
  document_id: number;
  question_type: string;
  prompt: string;
  answer: string;
  explanation: string;
  difficulty: string;
  topic: string;
  options: string[];
  answer_data: Record<string, unknown>;
  source_title: string;
  source_location: string;
}

export interface ImportResult {
  path: string;
  status: string;
  title: string | null;
  blocks: number;
  error: string | null;
  warning: string | null;
}

export interface Source {
  title: string;
  location: string;
  score: number;
}

export interface AskResponse {
  text: string;
  grounded: boolean;
  sources: Source[];
}

export interface SearchHit {
  text: string;
  title: string | null;
  source_type: string | null;
  page: number | null;
  slide: number | null;
  score: number;
}

export interface Achievement {
  key: string;
  name: string;
  description: string;
  icon: string;
  unlocked: boolean;
}

export interface Profile {
  level: number;
  total_xp: number;
  xp_in_level: number;
  xp_for_next: number;
  coins: number;
  hearts: number;
  max_hearts: number;
  current_streak: number;
  longest_streak: number;
  total_answers: number;
  correct_answers: number;
  accuracy: number;
  due_reviews: number;
  achievements: Achievement[];
}

export interface AnswerResult {
  correct: boolean;
  xp_earned: number;
  coins_earned: number;
  hearts: number;
  lost_heart: boolean;
  level: number;
  leveled_up: boolean;
  current_streak: number;
  new_achievements: { key: string; name: string; description: string; icon: string }[];
  profile: Profile;
}

export interface Boss {
  document_id: number;
  title: string;
  question_count: number;
  max_hp: number;
  defeated: boolean;
  times_defeated: number;
}

export interface BossComplete {
  document_id: number;
  xp_earned: number;
  coins_earned: number;
  times_defeated: number;
  leveled_up: boolean;
  level: number;
  profile: Profile;
}

function authHeaders(): Record<string, string> {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...authHeaders() },
    ...init,
  });
  if (res.status === 401) {
    onUnauthorized?.();
  }
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  signup: (email: string, password: string) =>
    json<AuthResult>("/api/auth/signup", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    json<AuthResult>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => json<User>("/api/auth/me"),
  health: () => json<Health>("/api/health"),
  documents: () => json<Doc[]>("/api/documents"),
  async upload(file: File): Promise<ImportResult> {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/documents/upload", { method: "POST", body: form, headers: authHeaders() });
    if (res.status === 401) onUnauthorized?.();
    if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
    return res.json();
  },
  async deleteDoc(id: number): Promise<void> {
    const res = await fetch(`/api/documents/${id}`, { method: "DELETE", headers: authHeaders() });
    if (res.status === 401) onUnauthorized?.();
    if (!res.ok && res.status !== 204) throw new Error(`${res.status}: ${await res.text()}`);
  },
  profile: () => json<Profile>("/api/profile"),
  answer: (questionId: number, correct: boolean) =>
    json<AnswerResult>("/api/answer", {
      method: "POST",
      body: JSON.stringify({ question_id: questionId, correct }),
    }),
  dueReviews: (limit = 10) => json<Question[]>(`/api/reviews/due?limit=${limit}`),
  bosses: () => json<Boss[]>("/api/bosses"),
  completeBoss: (docId: number) =>
    json<BossComplete>(`/api/bosses/${docId}/complete`, { method: "POST" }),
  generate: (docId: number, maxQuestions = 20) =>
    json<{ generated: number; total: number; ai_enabled: boolean }>(
      `/api/documents/${docId}/generate`,
      { method: "POST", body: JSON.stringify({ max_questions: maxQuestions }) }
    ),
  quiz: (limit = 10, docId?: number) =>
    json<Question[]>(
      `/api/quiz?limit=${limit}` + (docId ? `&document_id=${docId}` : "")
    ),
  ask: (question: string) =>
    json<AskResponse>("/api/tutor/ask", {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
  search: (query: string) =>
    json<{ hits: SearchHit[] }>("/api/search", {
      method: "POST",
      body: JSON.stringify({ query, k: 6 }),
    }),
};

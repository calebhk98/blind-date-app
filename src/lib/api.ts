/**
 * Typed fetch client for the Blind Date backend (FastAPI, see ../../backend).
 *
 * Base URL comes from NEXT_PUBLIC_API_URL (falls back to the backend's
 * default of http://localhost:3001). Every call goes through `request()`,
 * which normalizes network failures and non-2xx responses into `ApiError` so
 * pages can render a single graceful error state instead of crashing.
 *
 * Shapes here match backend/api/routes/*.py and backend/db/migrations/
 * 0001_initial.sql directly (read, never edited — this app only owns src/):
 *  - POST /judge takes {item_type, id, label} and returns
 *    {decision, source, route_to_review, trigger_reason} — not the
 *    per-modality verdicts.
 *  - GET /draw nests the photo/text payload under "content"
 *    ({file_path} for photos, {bio_text} for text) and calls the
 *    photo/text field "modality", not "kind".
 *  - GET /profiles/{id} returns {profile, photos}, not a flat object.
 *  - GET /dashboard's rolling accuracy key is "rolling_accuracy".
 * NOTE: photos are only ever given to the client as a server-local
 * `file_path` (e.g. "/tmp/.../photo-0.jpg") — the backend has no route that
 * serves image bytes over HTTP yet. `resolvePhotoUrl()` below only trusts
 * values that already look like an http(s) URL and otherwise reports the
 * raw path so the UI can degrade honestly instead of guessing a URL.
 *
 * Model boundary (design doc §8.1): this client only forwards whatever the
 * inference endpoint returns (a probability plus an optional caveat). It
 * never inspects training state or branches on "cold start" vs. "well
 * trained" — a fresh, untrained model and a mature one are consumed
 * identically by every function below.
 */

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001"
).replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// ---- Shared domain types ---------------------------------------------------

export type Modality = "photo" | "text";
export type PhotoLabel = "yes" | "no" | "not_relevant";
export type TextLabel = "yes" | "no";
export type Verdict = "pending" | "yes" | "no";
/** profiles.final_decision — a DB column, so it defaults to "pending". */
export type Decision = "pending" | "yes" | "no";
/**
 * The `decision` field on /judge and /review responses: the underlying
 * Decision enum is only ever set to yes/no when resolved, otherwise the API
 * sends null (never the literal string "pending").
 */
export type ResolvedDecision = "yes" | "no";
export type DecisionSource = "auto" | "review";
export type ModelName = "image" | "text" | "combined";

export interface DrawContent {
  bio_text?: string | null;
  file_path?: string | null;
}

export interface DrawItem {
  app_id: string;
  modality: Modality;
  item_id: string;
  profile_id: string;
  hard_filter_hit: boolean;
  content: DrawContent;
}

export interface JudgeRequest {
  item_type: Modality;
  id: string;
  label: PhotoLabel | TextLabel;
}

export interface JudgeResponse {
  decision: ResolvedDecision | null;
  source: DecisionSource | null;
  route_to_review: boolean;
  trigger_reason: string | null;
}

export interface ReviewRequest {
  user_decision: "yes" | "no";
}

export interface ReviewResponse {
  decision: ResolvedDecision | null;
  source: DecisionSource | null;
}

export interface SwipeApproveResponse {
  profile_id: string;
  swiped_now: boolean;
}

export interface InferenceResponse {
  probability: number;
  caveat?: string;
}

export interface DashboardResponse {
  pending: Record<string, number>;
  decisions: Record<string, number>;
  rolling_accuracy: Record<string, number | null>;
}

export interface App {
  app_id: string;
  backend_type?: string;
  display_name?: string;
}

export interface ProfilePhoto {
  photo_id: string;
  profile_id: string;
  file_path: string;
  order_index: number;
  label?: string;
  judged_at?: string | null;
}

export interface ProfileRecord {
  profile_id: string;
  app_id: string;
  external_id?: string;
  bio_text?: string | null;
  fetched_at?: string;
  image_verdict?: Verdict;
  text_verdict?: Verdict;
  // Raw SQLite INTEGER columns (CHECK IN (0,1)) come back as JSON numbers,
  // not booleans — dict(sqlite3.Row) preserves the underlying int.
  hard_filter_hit?: 0 | 1;
  final_decision?: Decision;
  decision_source?: DecisionSource | null;
  swiped?: 0 | 1;
}

export interface ProfileResponse {
  profile: ProfileRecord;
  photos: ProfilePhoto[];
}

/**
 * The backend hands photos over as a server-local filesystem path, not a
 * URL — there's no image-serving route yet. Only trust the value as an
 * <img src> if it already looks like an http(s) URL; otherwise surface the
 * raw path so the UI can show an honest "preview unavailable" state instead
 * of guessing at a URL scheme that may not exist.
 */
export function resolvePhotoUrl(filePath: string | null | undefined): string | null {
  if (!filePath) return null;
  return /^https?:\/\//i.test(filePath) ? filePath : null;
}

/**
 * URL of the backend route that streams a photo's bytes by id
 * (GET /photos/{photo_id}/image). Prefer this over resolvePhotoUrl(file_path):
 * the draw payload's `item_id` (for a photo modality) and a profile photo's
 * `photo_id` are both valid ids here.
 */
export function photoImageUrl(photoId: string | null | undefined): string | null {
  if (!photoId) return null;
  return `${API_BASE_URL}/photos/${encodeURIComponent(photoId)}/image`;
}

// ---- Core request helper ---------------------------------------------------

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `Could not reach the backend at ${API_BASE_URL}. Is it running?`,
      0,
    );
  }

  if (!res.ok) {
    const detail = await safeErrorDetail(res);
    throw new ApiError(
      detail ?? `Request failed with status ${res.status}`,
      res.status,
    );
  }

  if (res.status === 204) {
    return undefined as T;
  }

  try {
    return (await res.json()) as T;
  } catch {
    throw new ApiError("Backend returned an invalid response.", res.status);
  }
}

async function safeErrorDetail(res: Response): Promise<string | null> {
  try {
    const body: unknown = await res.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      return typeof detail === "string" ? detail : JSON.stringify(detail);
    }
  } catch {
    // Response body wasn't JSON; fall through to the generic message.
  }
  return null;
}

function qs(
  params: Record<string, string | number | boolean | undefined>,
): string {
  const usable = Object.entries(params).filter(
    ([, v]) => v !== undefined,
  ) as [string, string | number | boolean][];
  if (usable.length === 0) return "";
  const search = new URLSearchParams(usable.map(([k, v]) => [k, String(v)]));
  return `?${search.toString()}`;
}

// ---- Endpoints --------------------------------------------------------------

export const api = {
  baseUrl: API_BASE_URL,

  /** GET /draw?hard_filter=bool — one pending item, or null when the pool is empty. */
  getDraw(hardFilter = true): Promise<DrawItem | null> {
    return request<DrawItem | null>(`/draw${qs({ hard_filter: hardFilter })}`);
  },

  /** POST /judge */
  postJudge(payload: JudgeRequest): Promise<JudgeResponse> {
    return request<JudgeResponse>("/judge", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  /** POST /review/{profile_id} */
  postReview(
    profileId: string,
    payload: ReviewRequest,
  ): Promise<ReviewResponse> {
    return request<ReviewResponse>(
      `/review/${encodeURIComponent(profileId)}`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },

  /** POST /swipe/{profile_id}/approve */
  postSwipeApprove(profileId: string): Promise<SwipeApproveResponse> {
    return request<SwipeApproveResponse>(
      `/swipe/${encodeURIComponent(profileId)}/approve`,
      { method: "POST" },
    );
  },

  /** GET /inference/{model}/{target_id} */
  getInference(model: ModelName, targetId: string): Promise<InferenceResponse> {
    return request<InferenceResponse>(
      `/inference/${model}/${encodeURIComponent(targetId)}`,
    );
  },

  /** GET /dashboard */
  getDashboard(): Promise<DashboardResponse> {
    return request<DashboardResponse>("/dashboard");
  },

  /** GET /apps */
  getApps(): Promise<App[]> {
    return request<App[]>("/apps");
  },

  /** GET /profiles/{id} */
  getProfile(id: string): Promise<ProfileResponse> {
    return request<ProfileResponse>(`/profiles/${encodeURIComponent(id)}`);
  },
};

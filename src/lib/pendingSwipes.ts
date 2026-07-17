/**
 * Client-side queue of decisions awaiting swipe execution.
 *
 * The backend contract this UI is built against has no "list decisions
 * awaiting swipe" endpoint — only POST /swipe/{profile_id}/approve, which
 * executes a single swipe. So the blind-draw and full-profile-review flows
 * push a profile in here the moment its decision resolves to yes/no; the
 * Swipe Approval view reads this queue, calls approve, and drops the entry
 * on success. Persisted to localStorage so it survives reloads/navigation
 * within this browser (every swipe still requires explicit user approval —
 * this queue never calls the approve endpoint on its own).
 */

const STORAGE_KEY = "blind-date:pending-swipes";

export interface PendingSwipe {
  profileId: string;
  decision: "yes" | "no";
  appId?: string;
  source: "draw" | "review";
  addedAt: string;
}

function readAll(): PendingSwipe[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as PendingSwipe[]) : [];
  } catch {
    return [];
  }
}

function writeAll(items: PendingSwipe[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch {
    // localStorage unavailable (private mode, quota, etc.) — degrade silently.
  }
}

export function listPendingSwipes(): PendingSwipe[] {
  return readAll();
}

export function addPendingSwipe(entry: Omit<PendingSwipe, "addedAt">): void {
  const items = readAll().filter((i) => i.profileId !== entry.profileId);
  items.unshift({ ...entry, addedAt: new Date().toISOString() });
  writeAll(items);
}

export function removePendingSwipe(profileId: string): void {
  writeAll(readAll().filter((i) => i.profileId !== profileId));
}

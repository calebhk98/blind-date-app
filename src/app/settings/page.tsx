"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { api, ApiError, type HardFilterSettings } from "@/lib/api";
import { StateMessage } from "@/components/StateMessage/StateMessage";
import styles from "./page.module.css";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready" };

type SaveState = "idle" | "saving" | "saved" | "error";

interface FormState {
  minAge: string;
  maxAge: string;
  maxDistance: string;
  blockedKeywords: string;
  requiredKeywords: string;
  enabled: boolean;
}

const EMPTY_FORM: FormState = {
  minAge: "",
  maxAge: "",
  maxDistance: "",
  blockedKeywords: "",
  requiredKeywords: "",
  enabled: true,
};

function settingsToForm(settings: HardFilterSettings): FormState {
  return {
    minAge: settings.criteria.min_age?.toString() ?? "",
    maxAge: settings.criteria.max_age?.toString() ?? "",
    maxDistance: settings.criteria.max_distance?.toString() ?? "",
    blockedKeywords: settings.criteria.blocked_keywords.join(", "),
    requiredKeywords: settings.criteria.required_keywords.join(", "),
    enabled: settings.enabled,
  };
}

function parseKeywords(value: string): string[] {
  return value
    .split(",")
    .map((k) => k.trim())
    .filter((k) => k.length > 0);
}

function parseBound(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isNaN(parsed) ? null : parsed;
}

function formToSettings(form: FormState): HardFilterSettings {
  return {
    criteria: {
      min_age: parseBound(form.minAge),
      max_age: parseBound(form.maxAge),
      max_distance: parseBound(form.maxDistance),
      blocked_keywords: parseKeywords(form.blockedKeywords),
      required_keywords: parseKeywords(form.requiredKeywords),
    },
    enabled: form.enabled,
  };
}

/**
 * View/edit the hard-filter criteria (age range, max distance, blocked/
 * required keywords) and the session-level enabled toggle (design doc §7.4,
 * issue #21). Persists via PUT /settings/hard-filter; the same stored values
 * drive `hard_filter_hit` on newly-fetched profiles (issue #20) and the
 * default for GET /draw's `hard_filter` toggle when it's omitted.
 */
export default function SettingsPage() {
  const [loadState, setLoadState] = useState<LoadState>({ status: "loading" });
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [saveError, setSaveError] = useState<string | null>(null);

  // Event-handler version for the retry button: a synchronous reset here is
  // fine since it isn't running inside an effect body.
  const load = () => {
    setLoadState({ status: "loading" });
    api
      .getHardFilterSettings()
      .then((data) => {
        setForm(settingsToForm(data));
        setLoadState({ status: "ready" });
      })
      .catch((err: unknown) => {
        setLoadState({
          status: "error",
          message:
            err instanceof ApiError ? err.message : "Could not load settings.",
        });
      });
  };

  useEffect(() => {
    let cancelled = false;
    api
      .getHardFilterSettings()
      .then((data) => {
        if (cancelled) return;
        setForm(settingsToForm(data));
        setLoadState({ status: "ready" });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setLoadState({
          status: "error",
          message:
            err instanceof ApiError ? err.message : "Could not load settings.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaveState("saving");
    setSaveError(null);
    api
      .updateHardFilterSettings(formToSettings(form))
      .then((saved) => {
        setForm(settingsToForm(saved));
        setSaveState("saved");
      })
      .catch((err: unknown) => {
        setSaveState("error");
        setSaveError(
          err instanceof ApiError ? err.message : "Could not save settings.",
        );
      });
  };

  return (
    <main className={styles.page}>
      <Link href="/" className={styles.back}>
        ← Home
      </Link>
      <h1>Hard-filter settings</h1>
      <p className={styles.intro}>
        Profiles violating any of these criteria are flagged. The toggle
        below controls whether flagged profiles are excluded from the blind
        draw pool — either way, a flagged profile can never resolve to a
        &quot;yes&quot; decision.
      </p>

      {loadState.status === "loading" && (
        <StateMessage kind="loading" title="Loading settings…" />
      )}

      {loadState.status === "error" && (
        <StateMessage
          kind="error"
          title="Couldn't load settings"
          message={loadState.message}
          onRetry={load}
        />
      )}

      {loadState.status === "ready" && (
        <form className={styles.form} onSubmit={handleSubmit}>
          <label className={styles.toggleRow}>
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) =>
                setForm((f) => ({ ...f, enabled: e.target.checked }))
              }
            />
            Hard filter enabled (exclude flagged profiles from the draw pool)
          </label>

          <div className={styles.row}>
            <label className={styles.field}>
              Min age
              <input
                type="number"
                inputMode="numeric"
                value={form.minAge}
                placeholder="unset"
                onChange={(e) =>
                  setForm((f) => ({ ...f, minAge: e.target.value }))
                }
              />
            </label>
            <label className={styles.field}>
              Max age
              <input
                type="number"
                inputMode="numeric"
                value={form.maxAge}
                placeholder="unset"
                onChange={(e) =>
                  setForm((f) => ({ ...f, maxAge: e.target.value }))
                }
              />
            </label>
            <label className={styles.field}>
              Max distance
              <input
                type="number"
                inputMode="numeric"
                value={form.maxDistance}
                placeholder="unset"
                onChange={(e) =>
                  setForm((f) => ({ ...f, maxDistance: e.target.value }))
                }
              />
            </label>
          </div>

          <label className={styles.field}>
            Blocked keywords (comma-separated)
            <input
              type="text"
              value={form.blockedKeywords}
              placeholder="e.g. married, onlyfans"
              onChange={(e) =>
                setForm((f) => ({ ...f, blockedKeywords: e.target.value }))
              }
            />
          </label>

          <label className={styles.field}>
            Required keywords (comma-separated)
            <input
              type="text"
              value={form.requiredKeywords}
              placeholder="leave blank to require nothing"
              onChange={(e) =>
                setForm((f) => ({ ...f, requiredKeywords: e.target.value }))
              }
            />
          </label>

          <div className={styles.actions}>
            <button type="submit" disabled={saveState === "saving"}>
              {saveState === "saving" ? "Saving…" : "Save settings"}
            </button>
            {saveState === "saved" && (
              <span className={styles.saved}>Saved.</span>
            )}
            {saveState === "error" && saveError && (
              <span className={styles.saveError}>{saveError}</span>
            )}
          </div>
        </form>
      )}
    </main>
  );
}

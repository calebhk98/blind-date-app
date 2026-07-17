"use client";

import { useEffect, useState } from "react";
import { api, ApiError, type ModelName } from "@/lib/api";
import styles from "./InferenceBadge.module.css";

interface InferenceBadgeProps {
  model: ModelName;
  targetId: string;
}

// Result is tagged with the (model, targetId) it was fetched for, so
// "loading" can be derived (result missing or stale) instead of being set
// synchronously inside the effect below.
type Result =
  | { key: string; status: "error"; message: string }
  | { key: string; status: "ready"; probability: number; caveat?: string };

/**
 * Displays whatever GET /inference/{model}/{target_id} returns, verbatim.
 *
 * Model boundary (design doc §8.1): no "cold start" vs "well trained"
 * branching lives here — a fresh untrained model and a mature one are
 * rendered through the exact same probability + optional caveat path.
 */
export function InferenceBadge({ model, targetId }: InferenceBadgeProps) {
  const key = `${model}:${targetId}`;
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getInference(model, targetId)
      .then((res) => {
        if (!cancelled) {
          setResult({
            key,
            status: "ready",
            probability: res.probability,
            caveat: res.caveat,
          });
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setResult({
            key,
            status: "error",
            message:
              err instanceof ApiError
                ? err.message
                : "Model prediction unavailable.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [model, targetId, key]);

  if (!result || result.key !== key) {
    return (
      <p className={styles.loading}>Loading {model} model prediction…</p>
    );
  }

  if (result.status === "error") {
    // Non-fatal: the human review flow works fine without a model opinion.
    return (
      <p className={styles.unavailable}>
        {model} model prediction unavailable ({result.message})
      </p>
    );
  }

  const pct = Math.round(result.probability * 100);
  return (
    <div className={styles.badge}>
      <div className={styles.row}>
        <span className={styles.label}>{model} model</span>
        <span className={styles.value}>{pct}%</span>
      </div>
      {result.caveat ? <p className={styles.caveat}>{result.caveat}</p> : null}
    </div>
  );
}

"use client";

import { useState } from "react";
import type { PhotoLabel } from "@/lib/api";
import styles from "./PhotoJudgeCard.module.css";

interface PhotoJudgeCardProps {
  /** An http(s) URL the browser can actually fetch, or null/undefined. */
  photoUrl: string | null | undefined;
  /**
   * Raw path/identifier the backend gave for this photo when photoUrl is
   * unavailable — shown for context/debugging rather than silently hidden.
   */
  rawPath?: string | null;
  disabled?: boolean;
  onJudge: (label: PhotoLabel) => void;
}

/** Shows a single photo (never alongside bio text) with Yes / No / Not-relevant. */
export function PhotoJudgeCard({
  photoUrl,
  rawPath,
  disabled,
  onJudge,
}: PhotoJudgeCardProps) {
  const [broken, setBroken] = useState(false);

  return (
    <div className={styles.card}>
      <div className={styles.photoWrap}>
        {!photoUrl || broken ? (
          <div className={styles.brokenImage}>
            <p>{photoUrl ? "Photo failed to load" : "Preview unavailable"}</p>
            {!photoUrl && rawPath ? (
              <p className={styles.rawPath}>
                Backend returned a non-HTTP path, not a URL: {rawPath}
              </p>
            ) : null}
          </div>
        ) : (
          // Photos come from arbitrary, not-known-ahead-of-time external
          // dating-app domains, so next/image (which requires a static
          // remotePatterns allowlist) isn't a fit here.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={photoUrl}
            alt="Profile photo to judge"
            className={styles.photo}
            onError={() => setBroken(true)}
          />
        )}
      </div>
      <div className={styles.actions}>
        <button
          type="button"
          className={styles.yes}
          disabled={disabled}
          onClick={() => onJudge("yes")}
        >
          Yes
        </button>
        <button
          type="button"
          className={styles.no}
          disabled={disabled}
          onClick={() => onJudge("no")}
        >
          No
        </button>
        <button
          type="button"
          className={styles.notRelevant}
          disabled={disabled}
          onClick={() => onJudge("not_relevant")}
        >
          Not relevant
        </button>
      </div>
    </div>
  );
}

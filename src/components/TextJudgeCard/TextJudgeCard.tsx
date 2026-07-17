"use client";

import type { TextLabel } from "@/lib/api";
import styles from "./TextJudgeCard.module.css";

interface TextJudgeCardProps {
  bioText: string;
  disabled?: boolean;
  onJudge: (label: TextLabel) => void;
}

/** Shows a single bio (never alongside a photo) with Yes / No. */
export function TextJudgeCard({
  bioText,
  disabled,
  onJudge,
}: TextJudgeCardProps) {
  return (
    <div className={styles.card}>
      <div className={styles.bioWrap}>
        <p className={styles.bio}>{bioText || "(No bio text provided)"}</p>
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
      </div>
    </div>
  );
}

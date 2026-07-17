"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import {
  listPendingSwipes,
  removePendingSwipe,
  type PendingSwipe,
} from "@/lib/pendingSwipes";
import { AppBadge } from "@/components/AppBadge/AppBadge";
import { StateMessage } from "@/components/StateMessage/StateMessage";
import styles from "./page.module.css";

type RowStatus = "idle" | "approving" | "error";

export default function SwipeApprovalPage() {
  const [queue, setQueue] = useState<PendingSwipe[]>([]);
  const [rowStatus, setRowStatus] = useState<Record<string, RowStatus>>({});
  const [rowError, setRowError] = useState<Record<string, string>>({});

  useEffect(() => {
    setQueue(listPendingSwipes());
  }, []);

  const handleApprove = async (profileId: string) => {
    setRowStatus((s) => ({ ...s, [profileId]: "approving" }));
    try {
      await api.postSwipeApprove(profileId);
      removePendingSwipe(profileId);
      setQueue(listPendingSwipes());
    } catch (err) {
      setRowStatus((s) => ({ ...s, [profileId]: "error" }));
      setRowError((s) => ({
        ...s,
        [profileId]:
          err instanceof ApiError ? err.message : "Approval failed.",
      }));
    }
  };

  const handleDismiss = (profileId: string) => {
    removePendingSwipe(profileId);
    setQueue(listPendingSwipes());
  };

  return (
    <main className={styles.page}>
      <Link href="/" className={styles.back}>
        ← Home
      </Link>
      <h1>Swipe approvals</h1>
      <p className={styles.intro}>
        Every swipe still needs your sign-off before it executes on the
        source app. This queue tracks decisions resolved during blind draw
        and full-profile review in this browser.
      </p>

      {queue.length === 0 ? (
        <StateMessage
          kind="empty"
          title="Nothing waiting"
          message="Resolve items in Review or the Review Profile queue to populate this list."
        />
      ) : (
        <ul className={styles.list}>
          {queue.map((entry) => (
            <li key={entry.profileId} className={styles.row}>
              <div className={styles.rowInfo}>
                {entry.appId ? <AppBadge appId={entry.appId} /> : null}
                <span className={styles.profileId}>#{entry.profileId}</span>
                <span
                  className={`${styles.decision} ${
                    entry.decision === "yes" ? styles.yes : styles.no
                  }`}
                >
                  {entry.decision === "yes" ? "Yes" : "No"}
                </span>
                <span className={styles.source}>
                  via {entry.source === "draw" ? "blind draw" : "full review"}
                </span>
              </div>
              <div className={styles.rowActions}>
                <button
                  type="button"
                  onClick={() => handleApprove(entry.profileId)}
                  disabled={rowStatus[entry.profileId] === "approving"}
                >
                  {rowStatus[entry.profileId] === "approving"
                    ? "Approving…"
                    : "Approve swipe"}
                </button>
                <button
                  type="button"
                  className={styles.dismiss}
                  onClick={() => handleDismiss(entry.profileId)}
                >
                  Dismiss
                </button>
              </div>
              {rowStatus[entry.profileId] === "error" ? (
                <p className={styles.rowError}>{rowError[entry.profileId]}</p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

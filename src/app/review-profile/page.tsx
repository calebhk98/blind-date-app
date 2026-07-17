"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError, type DashboardResponse } from "@/lib/api";
import { StateMessage } from "@/components/StateMessage/StateMessage";
import styles from "./page.module.css";

export default function ReviewProfileQueuePage() {
  const router = useRouter();
  const [profileId, setProfileId] = useState("");
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [dashboardError, setDashboardError] = useState("");

  useEffect(() => {
    api
      .getDashboard()
      .then(setDashboard)
      .catch((err: unknown) => {
        setDashboardError(
          err instanceof ApiError
            ? err.message
            : "Could not load pending counts.",
        );
      });
  }, []);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = profileId.trim();
    if (trimmed) router.push(`/review-profile/${encodeURIComponent(trimmed)}`);
  };

  return (
    <main className={styles.page}>
      <Link href="/" className={styles.back}>
        ← Home
      </Link>
      <h1>Full-profile review queue</h1>
      <p className={styles.intro}>
        Profiles land here when the blind draw hits a split decision (image
        and text disagree) or every photo was judged not relevant. Continue{" "}
        <Link href="/review">blind drawing</Link> to route more, or open a
        profile directly below.
      </p>

      <form className={styles.form} onSubmit={handleSubmit}>
        <label htmlFor="profile-id">Profile ID</label>
        <div className={styles.formRow}>
          <input
            id="profile-id"
            value={profileId}
            onChange={(e) => setProfileId(e.target.value)}
            placeholder="e.g. 9f2a1c3e"
          />
          <button type="submit" disabled={!profileId.trim()}>
            Open profile
          </button>
        </div>
      </form>

      <section className={styles.snapshot}>
        <h2>Pending snapshot</h2>
        {dashboardError ? (
          <StateMessage
            kind="error"
            title="Pending counts unavailable"
            message={dashboardError}
          />
        ) : dashboard ? (
          <ul className={styles.countList}>
            {Object.entries(dashboard.pending).map(([key, value]) => (
              <li key={key}>
                <span>{key}</span>
                <strong>{value}</strong>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.loadingText}>Loading…</p>
        )}
      </section>
    </main>
  );
}

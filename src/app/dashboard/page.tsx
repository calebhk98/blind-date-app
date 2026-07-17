"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError, type DashboardResponse } from "@/lib/api";
import { StateMessage } from "@/components/StateMessage/StateMessage";
import styles from "./page.module.css";

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: DashboardResponse };

export default function DashboardPage() {
  const [state, setState] = useState<State>({ status: "loading" });

  // Event-handler version for the retry button: a synchronous reset here is
  // fine since it isn't running inside an effect body.
  const reload = () => {
    setState({ status: "loading" });
    api
      .getDashboard()
      .then((data) => setState({ status: "ready", data }))
      .catch((err: unknown) => {
        setState({
          status: "error",
          message:
            err instanceof ApiError
              ? err.message
              : "Could not load the dashboard.",
        });
      });
  };

  useEffect(() => {
    // Mount-only fetch: `state` already initializes to "loading", so there's
    // no synchronous setState here — only the eventual .then/.catch update it.
    let cancelled = false;
    api
      .getDashboard()
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            message:
              err instanceof ApiError
                ? err.message
                : "Could not load the dashboard.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className={styles.page}>
      <Link href="/" className={styles.back}>
        ← Home
      </Link>
      <h1>Dashboard</h1>

      {state.status === "loading" && (
        <StateMessage kind="loading" title="Loading dashboard…" />
      )}

      {state.status === "error" && (
        <StateMessage
          kind="error"
          title="Couldn't load the dashboard"
          message={state.message}
          onRetry={reload}
        />
      )}

      {state.status === "ready" && (
        <>
          <section className={styles.section}>
            <h2>Pending</h2>
            {Object.keys(state.data.pending).length === 0 ? (
              <p className={styles.emptyText}>Nothing pending.</p>
            ) : (
              <div className={styles.grid}>
                {Object.entries(state.data.pending).map(([key, value]) => (
                  <div key={key} className={styles.stat}>
                    <span className={styles.statValue}>{value}</span>
                    <span className={styles.statLabel}>{key}</span>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className={styles.section}>
            <h2>Decisions</h2>
            {Object.keys(state.data.decisions).length === 0 ? (
              <p className={styles.emptyText}>No decisions recorded yet.</p>
            ) : (
              <div className={styles.grid}>
                {Object.entries(state.data.decisions).map(([key, value]) => (
                  <div key={key} className={styles.stat}>
                    <span className={styles.statValue}>{value}</span>
                    <span className={styles.statLabel}>{key}</span>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className={styles.section}>
            <h2>Model accuracy (rolling)</h2>
            <div className={styles.grid}>
              {Object.entries(state.data.rolling_accuracy).map(
                ([model, value]) => (
                  <AccuracyStat key={model} label={model} value={value} />
                ),
              )}
            </div>
          </section>
        </>
      )}
    </main>
  );
}

function AccuracyStat({
  label,
  value,
}: {
  label: string;
  value: number | null;
}) {
  return (
    <div className={styles.stat}>
      <span className={styles.statValue}>
        {value === null ? "—" : `${Math.round(value * 100)}%`}
      </span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  );
}

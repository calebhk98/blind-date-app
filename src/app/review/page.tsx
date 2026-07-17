"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  api,
  ApiError,
  photoImageUrl,
  type DrawItem,
  type JudgeResponse,
  type PhotoLabel,
  type TextLabel,
} from "@/lib/api";
import { addPendingSwipe } from "@/lib/pendingSwipes";
import { PhotoJudgeCard } from "@/components/PhotoJudgeCard/PhotoJudgeCard";
import { TextJudgeCard } from "@/components/TextJudgeCard/TextJudgeCard";
import { AppBadge } from "@/components/AppBadge/AppBadge";
import { StateMessage } from "@/components/StateMessage/StateMessage";
import styles from "./page.module.css";

type Phase = "loading" | "ready" | "judging" | "result" | "empty" | "error";

export default function ReviewPage() {
  const [hardFilter, setHardFilter] = useState(true);
  const [phase, setPhase] = useState<Phase>("loading");
  const [item, setItem] = useState<DrawItem | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [lastResult, setLastResult] = useState<{
    item: DrawItem;
    response: JudgeResponse;
  } | null>(null);

  const loadNext = useCallback(async (filter: boolean) => {
    setPhase("loading");
    setLastResult(null);
    try {
      const next = await api.getDraw(filter);
      if (!next) {
        setItem(null);
        setPhase("empty");
        return;
      }
      setItem(next);
      setPhase("ready");
    } catch (err) {
      setErrorMessage(
        err instanceof ApiError
          ? err.message
          : "Something went wrong loading the next item.",
      );
      setPhase("error");
    }
  }, []);

  useEffect(() => {
    // Mount-only fetch: `phase` already initializes to "loading", so there's
    // no synchronous setState here — only the eventual .then/.catch update
    // state. Filter changes are handled by handleFilterToggle below, which
    // (as a plain event handler, not an effect) is free to call loadNext
    // synchronously.
    let cancelled = false;
    api
      .getDraw(true)
      .then((next) => {
        if (cancelled) return;
        if (!next) {
          setItem(null);
          setPhase("empty");
          return;
        }
        setItem(next);
        setPhase("ready");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setErrorMessage(
          err instanceof ApiError
            ? err.message
            : "Something went wrong loading the next item.",
        );
        setPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleFilterToggle = (value: boolean) => {
    setHardFilter(value);
    loadNext(value);
  };

  const handleJudge = async (label: PhotoLabel | TextLabel) => {
    if (!item) return;
    setPhase("judging");
    try {
      const response = await api.postJudge({
        item_type: item.modality,
        id: item.item_id,
        label,
      });
      if (response.decision) {
        addPendingSwipe({
          profileId: item.profile_id,
          decision: response.decision,
          appId: item.app_id,
          source: "draw",
        });
      }
      setLastResult({ item, response });
      setPhase("result");
    } catch (err) {
      setErrorMessage(
        err instanceof ApiError
          ? err.message
          : "Could not submit that judgment.",
      );
      setPhase("error");
    }
  };

  return (
    <main className={styles.page}>
      <Link href="/" className={styles.back}>
        ← Home
      </Link>
      <h1>Blind draw</h1>
      <p className={styles.intro}>
        Exactly one photo or one bio at a time — never both together — to
        keep photo and text judgments independent of each other.
      </p>

      <label className={styles.filterToggle}>
        <input
          type="checkbox"
          checked={hardFilter}
          onChange={(e) => handleFilterToggle(e.target.checked)}
          disabled={phase === "judging"}
        />
        Apply hard filter
      </label>

      {phase === "loading" && (
        <StateMessage kind="loading" title="Loading next item…" />
      )}

      {phase === "error" && (
        <StateMessage
          kind="error"
          title="Couldn't reach the draw"
          message={errorMessage}
          onRetry={() => loadNext(hardFilter)}
        />
      )}

      {phase === "empty" && (
        <StateMessage
          kind="empty"
          title="Nothing pending"
          message="No un-judged photos or bios are waiting right now."
          onRetry={() => loadNext(hardFilter)}
          retryLabel="Check again"
        />
      )}

      {(phase === "ready" || phase === "judging") && item && (
        <div className={styles.itemWrap}>
          <div className={styles.meta}>
            <AppBadge appId={item.app_id} />
            <span className={styles.kindLabel}>
              {item.modality === "photo" ? "Photo" : "Bio text"}
            </span>
          </div>
          {item.modality === "photo" ? (
            <PhotoJudgeCard
              photoUrl={photoImageUrl(item.item_id)}
              rawPath={item.content.file_path}
              disabled={phase === "judging"}
              onJudge={handleJudge}
            />
          ) : (
            <TextJudgeCard
              bioText={item.content.bio_text ?? ""}
              disabled={phase === "judging"}
              onJudge={handleJudge}
            />
          )}
        </div>
      )}

      {phase === "result" && lastResult && (
        <div className={styles.resultBanner}>
          <p className={styles.resultTitle}>Judgment recorded.</p>
          <ul className={styles.resultList}>
            {lastResult.response.decision ? (
              <li>
                Final decision: <strong>{lastResult.response.decision}</strong>
              </li>
            ) : lastResult.response.route_to_review ? (
              <li>
                Routed to full-profile review
                {lastResult.response.trigger_reason
                  ? ` (${lastResult.response.trigger_reason})`
                  : ""}
                .
              </li>
            ) : (
              <li>Still waiting on the other modality.</li>
            )}
          </ul>
          {lastResult.response.route_to_review ? (
            <Link
              href={`/review-profile/${encodeURIComponent(
                lastResult.item.profile_id,
              )}`}
              className={styles.reviewLink}
            >
              This profile needs full-profile review →
            </Link>
          ) : null}
          <button
            type="button"
            className={styles.nextButton}
            onClick={() => loadNext(hardFilter)}
          >
            Next
          </button>
        </div>
      )}
    </main>
  );
}

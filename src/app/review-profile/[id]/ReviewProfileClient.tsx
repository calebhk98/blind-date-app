"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  api,
  ApiError,
  photoImageUrl,
  type ProfileResponse,
} from "@/lib/api";
import { addPendingSwipe } from "@/lib/pendingSwipes";
import { InferenceBadge } from "@/components/InferenceBadge/InferenceBadge";
import { AppBadge } from "@/components/AppBadge/AppBadge";
import { StateMessage } from "@/components/StateMessage/StateMessage";
import styles from "./ReviewProfileClient.module.css";

// Result is tagged with the profileId it was fetched for, so "loading" can
// be derived (result missing or stale) instead of being set synchronously
// inside the fetch effect below.
type Result =
  | { key: string; status: "error"; message: string }
  | { key: string; status: "ready"; data: ProfileResponse };

type SubmitState = "idle" | "submitting" | "submitted" | "error";

export function ReviewProfileClient({ profileId }: { profileId: string }) {
  const [result, setResult] = useState<Result | null>(null);
  const [submit, setSubmit] = useState<SubmitState>("idle");
  const [submitError, setSubmitError] = useState("");
  const [attemptedDecision, setAttemptedDecision] = useState<
    "yes" | "no" | null
  >(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getProfile(profileId)
      .then((data) => {
        if (!cancelled) setResult({ key: profileId, status: "ready", data });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setResult({
            key: profileId,
            status: "error",
            message:
              err instanceof ApiError
                ? err.message
                : "Could not load this profile.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [profileId]);

  const retryLoad = () => {
    // Event handler, not an effect body — a synchronous reset here is fine.
    setResult(null);
    api
      .getProfile(profileId)
      .then((data) => setResult({ key: profileId, status: "ready", data }))
      .catch((err: unknown) => {
        setResult({
          key: profileId,
          status: "error",
          message:
            err instanceof ApiError
              ? err.message
              : "Could not load this profile.",
        });
      });
  };

  const handleDecision = async (userDecision: "yes" | "no") => {
    setAttemptedDecision(userDecision);
    setSubmit("submitting");
    try {
      await api.postReview(profileId, { user_decision: userDecision });
      addPendingSwipe({
        profileId,
        decision: userDecision,
        appId:
          result && result.status === "ready"
            ? result.data.profile.app_id
            : undefined,
        source: "review",
      });
      setSubmit("submitted");
    } catch (err) {
      setSubmitError(
        err instanceof ApiError ? err.message : "Could not save that decision.",
      );
      setSubmit("error");
    }
  };

  const isLoading = !result || result.key !== profileId;

  return (
    <main className={styles.page}>
      <Link href="/review-profile" className={styles.back}>
        ← Review queue
      </Link>
      <h1>Full-profile review</h1>

      {isLoading && <StateMessage kind="loading" title="Loading profile…" />}

      {!isLoading && result.status === "error" && (
        <StateMessage
          kind="error"
          title="Couldn't load this profile"
          message={result.message}
          onRetry={retryLoad}
        />
      )}

      {!isLoading && result.status === "ready" && (
        <>
          <div className={styles.meta}>
            <AppBadge appId={result.data.profile.app_id} />
            <span className={styles.profileId}>
              #{result.data.profile.profile_id}
            </span>
          </div>

          <p className={styles.bio}>
            {result.data.profile.bio_text || "(No bio text)"}
          </p>

          {result.data.photos.length > 0 ? (
            <div className={styles.photoGrid}>
              {result.data.photos.map((photo, i) => {
                const url = photoImageUrl(photo.photo_id);
                return url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    key={photo.photo_id}
                    src={url}
                    alt={`Profile photo ${i + 1}`}
                    className={styles.photo}
                  />
                ) : (
                  <div key={photo.photo_id} className={styles.photoFallback}>
                    Preview unavailable
                    <span className={styles.rawPath}>{photo.file_path}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className={styles.noPhotos}>No photos on file.</p>
          )}

          {(result.data.profile.image_verdict ||
            result.data.profile.text_verdict) && (
            <div className={styles.verdicts}>
              {result.data.profile.image_verdict ? (
                <span>Image verdict: {result.data.profile.image_verdict}</span>
              ) : null}
              {result.data.profile.text_verdict ? (
                <span>Text verdict: {result.data.profile.text_verdict}</span>
              ) : null}
            </div>
          )}

          <InferenceBadge model="combined" targetId={profileId} />

          {submit === "submitted" && attemptedDecision ? (
            <StateMessage
              kind="info"
              title={`Recorded: ${attemptedDecision === "yes" ? "Yes" : "No"}`}
              message="Added to the swipe-approval queue."
            />
          ) : (
            <div className={styles.actions}>
              <button
                type="button"
                className={styles.yes}
                disabled={submit === "submitting"}
                onClick={() => handleDecision("yes")}
              >
                Yes
              </button>
              <button
                type="button"
                className={styles.no}
                disabled={submit === "submitting"}
                onClick={() => handleDecision("no")}
              >
                No
              </button>
            </div>
          )}

          {submit === "error" && attemptedDecision ? (
            <StateMessage
              kind="error"
              title="Couldn't save decision"
              message={submitError}
              onRetry={() => handleDecision(attemptedDecision)}
            />
          ) : null}
        </>
      )}
    </main>
  );
}

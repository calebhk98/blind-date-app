import styles from "./StateMessage.module.css";

interface StateMessageProps {
  kind?: "loading" | "error" | "empty" | "info";
  title: string;
  message?: string;
  onRetry?: () => void;
  retryLabel?: string;
}

/** Shared loading / error / empty / info panel used across every review page. */
export function StateMessage({
  kind = "info",
  title,
  message,
  onRetry,
  retryLabel = "Try again",
}: StateMessageProps) {
  return (
    <div
      className={`${styles.wrap} ${styles[kind]}`}
      role={kind === "error" ? "alert" : "status"}
    >
      <p className={styles.title}>{title}</p>
      {message ? <p className={styles.message}>{message}</p> : null}
      {onRetry ? (
        <button type="button" className={styles.retry} onClick={onRetry}>
          {retryLabel}
        </button>
      ) : null}
    </div>
  );
}

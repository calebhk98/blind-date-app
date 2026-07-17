import styles from "./AppBadge.module.css";

/** Small pill showing which source app an item/profile came from. */
export function AppBadge({ appId }: { appId: string }) {
  return <span className={styles.badge}>{appId}</span>;
}

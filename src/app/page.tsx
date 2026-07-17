import Link from "next/link";
import styles from "./page.module.css";

const NAV_ITEMS = [
  {
    href: "/review",
    title: "Blind draw",
    description:
      "Judge one photo or bio at a time — never both together — to keep judgments unbiased.",
  },
  {
    href: "/review-profile",
    title: "Full-profile review",
    description: "Resolve profiles routed here by a split decision.",
  },
  {
    href: "/swipe",
    title: "Swipe approvals",
    description: "Approve every swipe yourself before it executes on the app.",
  },
  {
    href: "/dashboard",
    title: "Dashboard",
    description: "Pending counts, decision totals, and rolling model accuracy.",
  },
  {
    href: "/settings",
    title: "Settings",
    description: "Edit hard-filter criteria and the draw-pool toggle.",
  },
];

export default function Home() {
  return (
    <main className={styles.page}>
      <div className={styles.header}>
        <h1>Blind Date review</h1>
        <p>Personal dating-app aggregator — human review UI.</p>
      </div>
      <nav className={styles.grid}>
        {NAV_ITEMS.map((item) => (
          <Link key={item.href} href={item.href} className={styles.card}>
            <h2>{item.title}</h2>
            <p>{item.description}</p>
          </Link>
        ))}
      </nav>
    </main>
  );
}

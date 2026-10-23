import Link from "next/link";
import ThemeToggle from "./ThemeToggle";
import { CLIENT } from "@/lib/client";

/** Northwind Mutual's mark — a compass rose, north-weighted.
 *
 * The CLIENT's identity, not ours. Drawn inline so it follows the theme.
 */
export function Mark({ className = "h-7 w-7" }) {
  return (
    <svg viewBox="0 0 32 32" className={className} role="img"
         aria-label={CLIENT.name}>
      <circle cx="16" cy="16" r="12.5" fill="none" stroke="currentColor"
              strokeWidth="1.6" />
      <path d="M16 4.5 19.2 14 16 16 12.8 14Z" fill="currentColor" />
      <path d="M16 27.5 12.8 18 16 16 19.2 18Z" fill="currentColor" opacity="0.4" />
      <circle cx="16" cy="16" r="1.6" fill="currentColor" />
    </svg>
  );
}

export function TopNav({ current }) {
  const tabs = [
    { href: "/", label: "Overview" },
    { href: "/claims", label: "Claims" },
    { href: "/policy", label: "Policy wording" },
    { href: "/internals", label: "Admin" },
  ];
  return (
    <header className="border-b border-line bg-paper sticky top-0 z-20">
      <div className="mx-auto max-w-[1600px] px-5 h-14 flex items-center gap-6">
        <Link href="/" className="flex items-center gap-2.5 shrink-0"
              style={{ color: "var(--client-mark)" }}>
          <Mark />
          <span className="leading-tight">
            <span className="block font-serif text-ink text-base font-semibold
                             tracking-tight">
              {CLIENT.name}
            </span>
            <span className="block text-xs text-muted -mt-0.5">{CLIENT.system}</span>
          </span>
        </Link>
        <nav className="flex items-center gap-1 flex-1">
          {tabs.map((t) => {
            const active = current === t.href;
            return (
              <Link key={t.href} href={t.href}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  active ? "bg-accent text-paper font-semibold"
                         : "text-muted hover:bg-tint hover:text-ink"}`}>
                {t.label}
              </Link>
            );
          })}
        </nav>
        <ThemeToggle />
      </div>
    </header>
  );
}

export function Page({ children, current }) {
  return (
    <>
      <TopNav current={current} />
      <main className="mx-auto max-w-[1600px] px-5 py-7">{children}</main>
    </>
  );
}

export function Crumb({ items }) {
  return (
    <nav className="text-sm text-muted mb-3 flex flex-wrap items-center gap-1.5">
      {items.map((it, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <span className="text-line">/</span>}
          {it.href ? <Link href={it.href} className="hover:text-accent">{it.label}</Link>
                   : <span className="text-ink font-semibold">{it.label}</span>}
        </span>
      ))}
    </nav>
  );
}

export function Panel({ title, sub, right, tone, vendor, children, className = "" }) {
  return (
    <section className={`card ${vendor ? "border-accent/40" : ""} ${className}`}>
      <div className={`flex items-start justify-between gap-4 px-5 pt-4 pb-3
                       border-b ${vendor ? "border-accent/25 bg-tint/40" : "border-line"}`}>
        <div>
          <h2 className="font-serif text-base font-semibold leading-tight">{title}</h2>
          {sub && <p className="text-sm text-muted mt-0.5">{sub}</p>}
        </div>
        <div className="shrink-0 flex items-center gap-2">
          {tone && (
            <span className={`chip ${tone === "code"
              ? "border-accent/50 text-accent" : "border-line"}`}>
              {tone === "code" ? "deterministic" : "model judgment"}
            </span>
          )}
          {right}
        </div>
      </div>
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}

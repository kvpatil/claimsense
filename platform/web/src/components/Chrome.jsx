import Link from "next/link";
import ThemeToggle from "./ThemeToggle";

/** The mark: a shield with a reading line through it.
 *
 * Drawn inline rather than linked so it inherits `currentColor` and follows
 * the theme. An <img> cannot; that is the whole reason Fintor had to ship two
 * logo files and pick between them server-side.
 */
export function Mark({ className = "h-7 w-7" }) {
  return (
    <svg viewBox="0 0 32 32" className={className} role="img" aria-label="ClaimSense">
      <path d="M16 2.5 4.5 7v9.2c0 6.6 4.7 11.6 11.5 13.3 6.8-1.7 11.5-6.7 11.5-13.3V7L16 2.5Z"
            fill="currentColor" opacity="0.14" />
      <path d="M16 2.5 4.5 7v9.2c0 6.6 4.7 11.6 11.5 13.3 6.8-1.7 11.5-6.7 11.5-13.3V7L16 2.5Z"
            fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M10 15.5h5.2M10 19h9" stroke="currentColor" strokeWidth="1.6"
            strokeLinecap="round" />
      <circle cx="19.4" cy="14.2" r="3.4" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="m22 16.8 2.6 2.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function TopNav({ current }) {
  const tabs = [
    { href: "/", label: "Overview" },
    { href: "/claims", label: "Claims" },
    { href: "/policy", label: "Policy corpus" },
    { href: "/internals", label: "Internals" },
  ];
  return (
    <header className="border-b border-line bg-paper sticky top-0 z-20">
      <div className="mx-auto max-w-[1600px] px-5 h-14 flex items-center gap-6">
        <Link href="/" className="flex items-center gap-2.5 text-accent shrink-0">
          <Mark />
          <span className="font-serif text-ink text-lg font-semibold tracking-tight">
            ClaimSense
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
        {/* Stated, not implied. Everything this product outputs is a
            recommendation, and the chrome should say so on every screen. */}
        <span className="chip border-accent text-accent hidden md:inline-flex">
          Recommends · never decides
        </span>
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

/** A labelled section. `tone="code"` marks a panel whose content is
 *  deterministic, so the boundary is visible on screen and not only in docs. */
export function Panel({ title, sub, right, tone, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      <div className="flex items-start justify-between gap-4 px-5 pt-4 pb-3 border-b border-line">
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

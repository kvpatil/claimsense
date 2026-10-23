"use client";

import { useEffect, useState } from "react";

/** Light / dark / follow-the-system.
 *
 * Three states, not two. A binary toggle has to pick a default and is then
 * wrong for whoever wanted the other one; "system" is the honest third option
 * and it is the initial state.
 *
 * The chosen value is written to <html data-theme>, which globals.css scopes
 * its token blocks to. Removing the attribute hands control back to the media
 * query — which is why "system" deletes rather than setting a value.
 */
const ORDER = ["system", "light", "dark"];
const ICON = { system: "◐", light: "☀", dark: "☾" };

export default function ThemeToggle() {
  const [mode, setMode] = useState("system");

  useEffect(() => {
    const saved = localStorage.getItem("claimsense-theme") ?? "system";
    setMode(saved);
    apply(saved);
  }, []);

  function apply(next) {
    const root = document.documentElement;
    if (next === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", next);
  }

  function cycle() {
    const next = ORDER[(ORDER.indexOf(mode) + 1) % ORDER.length];
    setMode(next);
    apply(next);
    localStorage.setItem("claimsense-theme", next);
  }

  return (
    <button onClick={cycle} aria-label={`Theme: ${mode}. Click to change.`}
      title={`Theme: ${mode}`}
      className="h-8 w-8 rounded-lg border border-line text-muted hover:text-accent
                 hover:border-accent transition-colors text-sm shrink-0">
      {ICON[mode]}
    </button>
  );
}

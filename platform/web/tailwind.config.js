/** ClaimSense design tokens.
 *
 * The palette is Fintor's, carried over from the sibling capstone
 * (finnie-personal-finance-agent/src/web_app/theme.py:753-771). What came
 * across is the ~20 colour tokens and two typographic decisions; none of the
 * Streamlit workarounds did, because none of them are needed here.
 *
 * Every colour resolves through a CSS custom property declared in
 * globals.css, so light and dark are one definition each rather than a
 * `dark:` variant on every element. The contrast ratios are recorded beside
 * the values there — measured, not assumed.
 */
module.exports = {
  content: ["./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "rgb(var(--ink) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        line: "rgb(var(--line) / <alpha-value>)",
        paper: "rgb(var(--paper) / <alpha-value>)",
        ground: "rgb(var(--ground) / <alpha-value>)",
        note: "rgb(var(--note) / <alpha-value>)",
        accent: "rgb(var(--accent) / <alpha-value>)",
        tint: "rgb(var(--tint) / <alpha-value>)",
        // Reserved status colours. Never a series hue, never decorative.
        up: "rgb(var(--up) / <alpha-value>)",
        down: "rgb(var(--down) / <alpha-value>)",
        warn: "rgb(var(--warn) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["Inter Tight", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        serif: ["Source Serif 4", "Georgia", "serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: {
        // Nothing below xs. Fintor's small sizes drifted to 11.5px by being
        // hand-picked one rule at a time; a floor is what stops that.
        xs: ["0.8125rem", { lineHeight: "1.15rem" }],
        sm: ["0.875rem", { lineHeight: "1.3rem" }],
        base: ["0.9375rem", { lineHeight: "1.5rem" }],
      },
      borderRadius: { card: "12px" },
    },
  },
  plugins: [],
};

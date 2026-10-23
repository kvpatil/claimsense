import "./globals.css";

export const metadata = {
  title: "ClaimSense",
  description: "Claims adjudication co-pilot — recommends, never decides.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen">{children}</body>
    </html>
  );
}

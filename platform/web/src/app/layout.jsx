import "./globals.css";

import { CLIENT } from "@/lib/client";

export const metadata = {
  // The browser tab says the CLIENT's system, because that is whose portal
  // this is. ClaimSense is a panel inside it, not the application.
  title: `${CLIENT.system} — ${CLIENT.name}`,
  description: `Claims adjudication for ${CLIENT.name}.`,
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen">{children}</body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "InsightAI — Conversational BI Dashboard",
  description:
    "Generate interactive business intelligence dashboards using natural language. No SQL or technical skills required.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

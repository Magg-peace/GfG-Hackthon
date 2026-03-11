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
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet" />
      </head>
      <body className="bg-[#F8FAFC] antialiased">{children}</body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SIH26034 - Legal Metrology Compliance",
  description: "Intelligent Legal Metrology Compliance Platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#1e3a5f" />
      </head>
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        {children}
      </body>
    </html>
  );
}

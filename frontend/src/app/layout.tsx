import type { Metadata, Viewport } from "next";
import "./globals.css";
import { SerwistProvider } from "./serwist";

export const metadata: Metadata = {
  title: "SIH26034 - Legal Metrology Compliance",
  description: "Intelligent Legal Metrology Compliance Platform",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "SIH26034",
  },
};

export const viewport: Viewport = {
  themeColor: "#1e3a5f",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#1e3a5f" />
      </head>
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        <SerwistProvider swUrl="/sw.js">{children}</SerwistProvider>
      </body>
    </html>
  );
}

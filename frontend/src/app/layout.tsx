import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { SerwistProvider } from "./serwist";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "ScanCheck — Product Compliance Intelligence",
  description:
    "AI-powered product label compliance inspection and legal metrology verification platform",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "ScanCheck",
  },
};

export const viewport: Viewport = {
  themeColor: "#0b111e",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <head>
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#0b111e" />
      </head>
      <body className="min-h-screen bg-slate-50 text-slate-900 font-sans antialiased selection:bg-brand-500/20 selection:text-brand-900">
        <SerwistProvider swUrl="/serwist/sw.js">{children}</SerwistProvider>
      </body>
    </html>
  );
}

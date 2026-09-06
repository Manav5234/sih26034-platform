import Link from "next/link";

import { getServerApiUrl } from "@/lib/config";

async function getHealth() {
  const apiUrl = getServerApiUrl();
  const res = await fetch(`${apiUrl}/health`, {
    cache: "no-store",
  });
  if (!res.ok) return { status: "error", service: "unreachable" };
  return res.json();
}

export default async function Home() {
  const health = await getHealth();

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg">
        <h1 className="mb-2 text-xl font-bold text-slate-800">
          SIH26034
        </h1>
        <p className="mb-6 text-sm text-slate-500">
          Legal Metrology Compliance Platform
        </p>

        <div className="flex items-center gap-3 mb-6">
          <span
            className={`h-3 w-3 rounded-full ${
              health.status === "ok" ? "bg-green-500" : "bg-red-500"
            }`}
          />
          <span className="text-sm font-medium">
            {health.status === "ok"
              ? `Backend: ${health.service}`
              : "Backend unreachable"}
          </span>
        </div>

        <Link
          href="/login"
          className="block w-full rounded-lg bg-blue-600 px-3 py-2 text-center text-sm font-medium text-white hover:bg-blue-700"
        >
          Officer Login
        </Link>
      </div>
    </main>
  );
}

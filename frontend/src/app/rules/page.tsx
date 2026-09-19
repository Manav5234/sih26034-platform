import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";

import { getServerApiUrl } from "@/lib/config";

interface Rule {
  rule_id: string;
  source_document: string;
  clause: string;
  applicability: string;
  required_declaration: string;
  validation_conditions: unknown;
  measurement_requirements: unknown;
  exceptions: string[];
  effective_date: string;
  evidence_requirements: string[];
}

interface RuleSet {
  id: string;
  source: string;
  rule_version: string;
  effective_from: string;
  effective_to: string | null;
  jurisdiction: string;
  rules: Rule[];
}

async function getRules(token: string, effectiveDate?: string, jurisdiction?: string): Promise<RuleSet | null> {
  const params = new URLSearchParams();
  if (effectiveDate) params.set("effective_date", effectiveDate);
  if (jurisdiction) params.set("jurisdiction", jurisdiction);
  const res = await fetch(`${getServerApiUrl()}/rules?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}

export default async function RulesPage({
  searchParams,
}: {
  searchParams: Promise<{ effective_date?: string; jurisdiction?: string }>;
}) {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  if (!token) redirect("/login");

  const params = await searchParams;
  const data = await getRules(token, params.effective_date, params.jurisdiction);

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-xl font-bold text-slate-800">Legal Metrology Rules</h1>
          <div className="flex gap-2">
            <Link href="/dashboard" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
              Dashboard
            </Link>
          </div>
        </div>

        {!data ? (
          <div className="rounded-xl bg-white p-8 shadow text-center">
            <p className="text-sm text-slate-400">No active ruleset found for today.</p>
            <p className="mt-1 text-xs text-slate-300">
              Rules become available when a ruleset is loaded into the system.
            </p>
          </div>
        ) : (
          <>
            {/* Ruleset metadata */}
            <div className="mb-6 rounded-xl bg-white p-5 shadow">
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-xs text-slate-500">Source</p>
                  <p className="mt-0.5 text-sm font-medium text-slate-800">{data.source}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Version</p>
                  <p className="mt-0.5 text-sm font-medium text-slate-800">{data.rule_version}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Jurisdiction</p>
                  <p className="mt-0.5 text-sm font-medium text-slate-800">{data.jurisdiction}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Effective From</p>
                  <p className="mt-0.5 text-sm font-medium text-slate-800">{data.effective_from}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Effective To</p>
                  <p className="mt-0.5 text-sm font-medium text-slate-800">{data.effective_to || "—"}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Rules Count</p>
                  <p className="mt-0.5 text-sm font-medium text-slate-800">{data.rules.length}</p>
                </div>
              </div>
            </div>

            {/* Rules table */}
            <div className="overflow-x-auto rounded-xl bg-white shadow">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50">
                    <th className="px-4 py-3 font-medium text-slate-600">Rule ID</th>
                    <th className="px-4 py-3 font-medium text-slate-600">Source Document</th>
                    <th className="px-4 py-3 font-medium text-slate-600">Clause</th>
                    <th className="px-4 py-3 font-medium text-slate-600">Required Declaration</th>
                    <th className="px-4 py-3 font-medium text-slate-600">Applicability</th>
                    <th className="px-4 py-3 font-medium text-slate-600">Exceptions</th>
                    <th className="px-4 py-3 font-medium text-slate-600">Evidence Requirements</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rules.map((rule) => (
                    <tr key={rule.rule_id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                      <td className="px-4 py-3 font-mono text-xs text-slate-800">{rule.rule_id}</td>
                      <td className="px-4 py-3 text-slate-600 text-xs">{rule.source_document}</td>
                      <td className="px-4 py-3 text-slate-700">{rule.clause}</td>
                      <td className="px-4 py-3 text-slate-700">{rule.required_declaration}</td>
                      <td className="px-4 py-3 text-slate-600 text-xs">{rule.applicability}</td>
                      <td className="px-4 py-3 text-slate-600 text-xs">
                        {rule.exceptions.length > 0 ? rule.exceptions.join("; ") : "—"}
                      </td>
                      <td className="px-4 py-3 text-slate-600 text-xs">
                        {rule.evidence_requirements.length > 0 ? rule.evidence_requirements.join("; ") : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="mt-4 text-xs text-slate-400 text-center">
              {data.rules.length} rule{data.rules.length !== 1 ? "s" : ""} in active ruleset
            </p>
          </>
        )}
      </div>
    </main>
  );
}

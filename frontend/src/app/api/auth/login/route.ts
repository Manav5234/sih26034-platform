import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const { token } = await req.json();
  if (!token) return NextResponse.json({ error: "missing token" }, { status: 400 });

  // ponytail: cookie Secure flag driven by ENVIRONMENT env var.
  // Set ENVIRONMENT=production in deployed environments (HTTPS).
  // Local dev over HTTP defaults to false.
  const isProduction = process.env.ENVIRONMENT === "production";

  const res = NextResponse.json({ ok: true });
  res.cookies.set("access_token", token, {
    httpOnly: true,
    secure: isProduction,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 8, // 8 hours
  });
  return res;
}

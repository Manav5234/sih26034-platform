import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const { token } = await req.json();
  if (!token) return NextResponse.json({ error: "missing token" }, { status: 400 });

  const res = NextResponse.json({ ok: true });
  res.cookies.set("access_token", token, {
    httpOnly: true,
    secure: false, // set true in production with HTTPS
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 8, // 8 hours
  });
  return res;
}

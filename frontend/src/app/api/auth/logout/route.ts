import { NextResponse } from "next/server";

export async function POST() {
  const res = NextResponse.json({ ok: true });
  res.cookies.set("access_token", "", { httpOnly: true, maxAge: 0, path: "/" });
  res.headers.set("Location", "/login");
  return res;
}

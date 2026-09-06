/** @type {import('next').NextConfig} */
const nextConfig = {
  // ponytail: standalone only needed for Docker build, not Vercel
  ...(process.env.VERCEL ? {} : { output: "standalone" }),
}

module.exports = nextConfig

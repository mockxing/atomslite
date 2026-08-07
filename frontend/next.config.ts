import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  // Proxy API + SSE to the backend in production (Vercel).
  // Set BACKEND_URL (e.g. https://atoms-backend.up.railway.app) in Vercel env.
  // Locally you can also run the backend and set BACKEND_URL=http://localhost:8000.
  async rewrites() {
    const backend = process.env.BACKEND_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;

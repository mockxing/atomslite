import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  // In production the /api/* proxy to the Railway backend is configured in
  // vercel.json (rewrites). Locally you can run the backend on :8000 and set
  // NEXT_PUBLIC_API_URL or use the dev proxy.
};

export default nextConfig;

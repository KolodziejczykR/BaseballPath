import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Only use custom distDir in local environment, let Vercel use default '.next'
  distDir: process.env.VERCEL ? undefined : ".next-local",
  webpack: (config, { dev }) => {
    // Stabilize local dev in environments where webpack snapshot cache fails.
    if (dev) {
      config.cache = false;
    }
    return config;
  },
};

export default nextConfig;

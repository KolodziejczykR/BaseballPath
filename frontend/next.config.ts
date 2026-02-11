import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: ".next-local",
  webpack: (config, { dev }) => {
    // Stabilize local dev in environments where webpack snapshot cache fails.
    if (dev) {
      config.cache = false;
    }
    return config;
  },
};

export default nextConfig;

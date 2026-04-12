import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

export default function nextConfig(phase: string): NextConfig {
  const isDevServer = phase === PHASE_DEVELOPMENT_SERVER;

  return {
    // Keep dev and production outputs isolated to avoid chunk/manifest collisions.
    distDir: isDevServer ? ".next-dev" : ".next",
    async redirects() {
      return [
        {
          source: "/waitlist",
          destination: "/prelaunch",
          permanent: true,
        },
        {
          source: "/waitlist/:path+",
          destination: "/prelaunch",
          permanent: true,
        },
        {
          source: "/dashboard",
          destination: "/predict",
          permanent: false,
        },
        {
          source: "/goals/:path*",
          destination: "/predict",
          permanent: false,
        },
        {
          source: "/goals",
          destination: "/predict",
          permanent: false,
        },
        {
          source: "/plans/:path*",
          destination: "/account",
          permanent: false,
        },
        {
          source: "/plans",
          destination: "/account",
          permanent: false,
        },
      ];
    },
    experimental: {
      // Work around a Next 15 dev-server issue where Segment Explorer can break
      // the React client manifest and cause random module-not-found 500s.
      devtoolSegmentExplorer: false,
      // Avoid stale server component module references during heavy HMR cycles.
      serverComponentsHmrCache: false,
    },
    webpack: (config, { dev }) => {
      // Stabilize local dev in environments where webpack snapshot cache fails.
      if (dev) {
        config.cache = false;
      }
      return config;
    },
  };
}

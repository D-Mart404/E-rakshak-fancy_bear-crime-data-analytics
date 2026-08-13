import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Hide the default Next.js corner indicator in the UI.
  devIndicators: false,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8001/api/:path*",
      },
    ];
  },
};

export default nextConfig;

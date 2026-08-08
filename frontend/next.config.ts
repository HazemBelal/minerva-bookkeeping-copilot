import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Next's built-in gzip compression buffers proxied chunked responses
  // (e.g. /sse/* through the rewrite below) until enough data accumulates,
  // which defeats SSE. A reverse proxy in front of the real deployment can
  // compress everything else; this route never should.
  compress: false,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" },
      { source: "/sse/:path*", destination: "http://127.0.0.1:8000/sse/:path*" },
      { source: "/shots/:path*", destination: "http://127.0.0.1:8000/shots/:path*" },
    ];
  },
};

export default nextConfig;

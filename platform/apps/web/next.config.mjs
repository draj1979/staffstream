/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: false,
  },
  // Produces a self-contained .next/standalone/ with only the deps this
  // app actually needs traced in — the Dockerfile copies just that,
  // instead of shipping the full node_modules tree into the image.
  output: "standalone",
};

export default nextConfig;

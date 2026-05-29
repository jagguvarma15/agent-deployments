/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The backend agent URL is exposed to the browser via NEXT_PUBLIC_AGENT_URL.
  // The /api/agent route proxies to it server-side so the browser never
  // needs cross-origin permission.
};

module.exports = nextConfig;

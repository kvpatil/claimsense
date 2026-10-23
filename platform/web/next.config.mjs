/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The console is read-mostly and every page reflects live claim state, so
  // nothing here is safe to pre-render at build time.
  output: "standalone",
};
export default nextConfig;

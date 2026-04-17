/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow fetch to local FastAPI backend
  async rewrites() {
    return []
  },
}

module.exports = nextConfig

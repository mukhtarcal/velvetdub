import type { NextConfig } from 'next'

// Everything binds to localhost only. The API runs on 8765 (`uv run vd serve`); the web app
// forwards /api to it, the way the old Vite proxy did.
const API = process.env.VELVETDUB_API ?? 'http://127.0.0.1:8765'

const nextConfig: NextConfig = {
  // cacheComponents stays off (the default): it keeps old pages mounted after you leave them,
  // which would leave a film playing out of sight.
  images: { unoptimized: true },
  turbopack: {
    rules: { '*.css': { loaders: ['@tailwindcss/turbopack'], as: '*.css' } },
  },
  experimental: {
    // A film upload is one long streamed request. The default 30 s proxy timeout would cut it off.
    proxyTimeout: 6 * 60 * 60 * 1000,
  },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${API}/api/:path*` }]
  },
}

export default nextConfig

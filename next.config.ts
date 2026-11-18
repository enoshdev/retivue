import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      {
        source: '/dashboard',
        destination: '/app',
        permanent: false,
      },
      {
        source: '/screenings',
        destination: '/app/screenings',
        permanent: false,
      },
      {
        source: '/screenings/:path*',
        destination: '/app/screenings/:path*',
        permanent: false,
      },
      {
        source: '/patients',
        destination: '/app/patients',
        permanent: false,
      },
      {
        source: '/patients/:path*',
        destination: '/app/patients/:path*',
        permanent: false,
      },
      {
        source: '/reports',
        destination: '/app/reports',
        permanent: false,
      },
      {
        source: '/reports/:path*',
        destination: '/app/reports/:path*',
        permanent: false,
      },
      {
        source: '/review/:path*',
        destination: '/app/screenings/:path*',
        permanent: false,
      },
    ];
  },
};

export default nextConfig;

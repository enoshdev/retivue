import type { Metadata, Viewport } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'RETIVUE — AI-Assisted Retinal Screening | See Risk Earlier',
  description:
    'Retivue helps screen retinal images for signs associated with diabetic retinopathy and makes the visual evidence behind each screening result easier to understand.',
  icons: {
    icon: '/icon.svg',
    shortcut: '/icon.svg',
    apple: '/icon.svg',
  },
  keywords: [
    'Diabetic Retinopathy',
    'Retinal Screening',
    'Explainable AI',
    'Tele-ophthalmology',
    'SIH26038',
    'Rural Health Screening',
    'MedTech AI',
  ],
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#4a5320',
};

import { ClientProviders } from '@/components/providers/ClientProviders';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full antialiased">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Playfair+Display:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap"
        />
      </head>
      <body className="min-h-full flex flex-col bg-[#fbfbf9] text-[#171913]">
        <ClientProviders>{children}</ClientProviders>
      </body>
    </html>
  );
}

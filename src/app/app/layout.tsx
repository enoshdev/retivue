import React from 'react';
import { AppLayout } from '@/layouts/AppLayout';
import { AuthGuard } from '@/components/auth/AuthGuard';

export default function ApplicationRootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <AppLayout>{children}</AppLayout>
    </AuthGuard>
  );
}

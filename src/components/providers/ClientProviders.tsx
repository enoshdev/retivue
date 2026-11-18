'use client';

import React from 'react';
import { ClinicalProvider } from '@/context/ClinicalContext';

export function ClientProviders({ children }: { children: React.ReactNode }) {
  return (
    <ClinicalProvider>
      {children}
    </ClinicalProvider>
  );
}

'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useClinical } from '@/context/ClinicalContext';
import { RetivueLogo } from '@/components/brand/RetivueLogo';
import { ShieldCheck } from 'lucide-react';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, isLoadingAuth } = useClinical();

  useEffect(() => {
    if (!isLoadingAuth && !isAuthenticated) {
      router.replace('/login');
    }
  }, [isAuthenticated, isLoadingAuth, router]);

  if (isLoadingAuth) {
    return (
      <div className="min-h-screen bg-[#faf9f5] flex flex-col items-center justify-center p-6 text-center select-none">
        <div className="space-y-4 max-w-sm w-full flex flex-col items-center">
          <RetivueLogo size="lg" variant="olive" href="/" />
          <div className="space-y-1.5 pt-2">
            <h2 className="font-serif text-lg text-[#1c1d1a]">Verifying Clinical Session</h2>
            <p className="text-xs text-[#5a5d52]">Connecting to Retivue secure infrastructure...</p>
          </div>
          <div className="w-36 h-1 bg-[#e8e4d8] rounded-full overflow-hidden relative">
            <div className="h-full bg-[#4a5320] w-1/2 rounded-full animate-pulse" />
          </div>
          <div className="flex items-center gap-1.5 text-[10px] text-[#7a7d72] pt-4">
            <ShieldCheck size={13} className="text-[#6f7d3e]" />
            <span>21 CFR § 886.1100 Protected Clinical Environment</span>
          </div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}


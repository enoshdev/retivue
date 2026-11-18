'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function StaffManagementRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/app');
  }, [router]);

  return (
    <div className="p-12 text-center bg-white border border-[#e8e4d8] rounded-2xl max-w-lg mx-auto my-12 shadow-xs select-none">
      <h2 className="text-base font-bold font-serif text-[#1c1d1a] mb-1">
        Unified Clinical Account
      </h2>
      <p className="text-xs text-[#7a7d72] mb-5 leading-relaxed">
        RETIVUE operates under a unified clinical practitioner workspace. Role hierarchies have been streamlined into a single clinical workflow. Redirecting to dashboard...
      </p>
      <Link
        href="/app"
        className="inline-flex items-center gap-1.5 bg-[#4a5320] text-white text-xs font-semibold px-4 py-2 rounded-full no-underline hover:bg-[#3e461a] transition-colors"
      >
        <ArrowLeft size={13} />
        <span>Return to Dashboard</span>
      </Link>
    </div>
  );
}

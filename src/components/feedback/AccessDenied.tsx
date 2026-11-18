import React from 'react';
import Link from 'next/link';
import { ShieldX, ArrowLeft } from 'lucide-react';
import { UserRole } from '@/types/clinical';

interface AccessDeniedProps {
  requiredRole?: UserRole | string;
  userRole?: UserRole;
  className?: string;
}

export function AccessDenied({
  requiredRole = 'CLINIC_ADMIN',
  userRole = 'INDEPENDENT_DOCTOR',
  className = '',
}: AccessDeniedProps) {
  const formatRole = (r: string) => {
    if (r === 'INDEPENDENT_DOCTOR') return 'Independent Ophthalmologist';
    if (r === 'CLINIC_ADMIN') return 'Clinic Administrator';
    if (r === 'TECHNICIAN') return 'Vision Technician';
    return r;
  };

  return (
    <div
      className={`p-10 text-center flex flex-col items-center justify-center bg-white border border-slate-200 rounded-lg max-w-lg mx-auto my-12 ${className}`}
    >
      <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-700 mb-3 border border-slate-200">
        <ShieldX size={24} />
      </div>
      <h3 className="text-base font-semibold text-slate-900 mb-1">
        Access Restricted
      </h3>
      <p className="text-xs text-slate-600 mb-4 leading-relaxed">
        This section requires <strong>{formatRole(requiredRole)}</strong> permissions. Your active account is currently operating under the <strong>{formatRole(userRole)}</strong> profile.
      </p>

      <div className="flex items-center gap-3">
        <Link
          href="/app"
          className="inline-flex items-center gap-1.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold px-4 py-2 rounded transition-colors no-underline"
        >
          <ArrowLeft size={13} />
          <span>Return to Dashboard</span>
        </Link>
      </div>
    </div>
  );
}


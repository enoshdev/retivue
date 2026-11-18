'use client';

import React from 'react';
import Link from 'next/link';
import { RetivueLogo } from '@/components/brand/RetivueLogo';

export function PublicFooter() {
  return (
    <footer className="w-full bg-[#f5f3ec] border-t border-[#e8e4d8] pt-14 pb-10 text-[#4a4c44]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">
        {/* Top Tier: Logo & Links */}
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 pb-6 border-b border-[#e2ddd1]">
          <div>
            <RetivueLogo size="md" variant="olive" href="/" />
            <p className="mt-2.5 text-xs text-[#7a7d72] max-w-sm leading-relaxed">
              Clinical decision-support and retinal screening platform engineered for ophthalmologists, eye hospitals, and tele-screening workflows.
            </p>
          </div>

          <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs font-medium text-[#4a4c44]">
            <Link href="/research" className="hover:text-[#1c1d1a] transition-colors">
              Technology & CADe
            </Link>
            <Link href="/telemedicine" className="hover:text-[#1c1d1a] transition-colors">
              Telemedicine Workflow
            </Link>
            <Link href="/about" className="hover:text-[#1c1d1a] transition-colors">
              About Retivue
            </Link>
            <Link href="/login" className="hover:text-[#1c1d1a] transition-colors">
              Clinician Portal
            </Link>
            <Link href="/signup" className="hover:text-[#1c1d1a] transition-colors">
              Register Practice
            </Link>
          </div>
        </div>

        {/* Bottom Tier: Clinical Disclaimer & Copyright */}
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 text-[11px] text-[#7a7d72] leading-relaxed font-mono">
          <p className="max-w-3xl">
            <span className="font-semibold text-[#4a4c44]">Clinical Notice (21 CFR § 886.1100):</span> Retivue CADe is an adjunct screening tool, not a standalone diagnostic device. Final diagnostic staging, referral decision, and management plan remain the exclusive professional responsibility of the reading ophthalmologist.
          </p>

          <p className="shrink-0 text-right md:text-left">
            © {new Date().getFullYear()} RETIVUE Systems.
          </p>
        </div>
      </div>
    </footer>
  );
}

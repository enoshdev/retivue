import React from 'react';
import { ShieldAlert } from 'lucide-react';

interface CdsDisclaimerBannerProps {
  compact?: boolean;
  className?: string;
}

export function CdsDisclaimerBanner({
  compact = false,
  className = '',
}: CdsDisclaimerBannerProps) {
  if (compact) {
    return (
      <div
        className={`bg-[#1c1d1a] text-[#edebe1] text-[11px] font-mono px-4 py-1.5 flex items-center justify-between border-b border-[#2e3129] ${className}`}
      >
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[#dee9a6] animate-pulse" />
          <span className="font-semibold text-white tracking-wide">CLINICAL DECISION SUPPORT (CDS)</span>
          <span className="hidden md:inline text-[#a8aba0]">
            • RetiVue is an auxiliary research screening tool, not an autonomous diagnostic device.
          </span>
        </div>
        <span className="text-[10px] text-[#8e9185] font-mono hidden sm:inline">
          PROTOCOL ETDRS-7F // RESEARCH DECISION SUPPORT
        </span>
      </div>
    );
  }

  return (
    <div
      className={`p-4 bg-[#f5f3ec] border border-[#e8e4d8] rounded-2xl text-xs flex items-start gap-3.5 ${className}`}
    >
      <ShieldAlert size={18} className="text-[#4a5320] shrink-0 mt-0.5" />
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-[#1c1d1a] tracking-wide uppercase text-[11px] font-mono">
            Clinical Decision Support (CDS) Notice
          </span>
          <span className="text-[10px] font-mono text-[#4a5320] bg-[#f2f4e8] border border-[#d8debe] px-2 py-0.5 rounded-full">
            Research Prototype — Independent Sign-Off Required
          </span>
        </div>
        <p className="text-[#5a5d52] text-xs leading-relaxed">
          RetiVue is designed as an auxiliary decision-support tool to assist trained healthcare staff. It does NOT possess regulatory marketing clearance or clinical certification for autonomous diagnosis. Final diagnostic grading, triage, and management decisions remain the exclusive responsibility of qualified, credentialed healthcare professionals.
        </p>
      </div>
    </div>
  );
}


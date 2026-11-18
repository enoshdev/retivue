'use client';

import React from 'react';
import Link from 'next/link';
import { PublicLayout } from '@/layouts/PublicLayout';
import {
  MapPin,
  Camera,
  Cpu,
  UserCheck,
  Hospital,
  ArrowRight,
  WifiOff,
  Clock,
  Shield,
} from 'lucide-react';

export default function TelemedicinePage() {
  const workflowNodes = [
    {
      step: '01',
      title: 'Local Screening Center',
      subtitle: 'Primary Health Centre (PHC) / Vision Camp',
      icon: MapPin,
      desc: 'Patient presents at local community camp or vision centre. Certified vision technician captures non-mydriatic fundus images without requiring pharmacologic pupil dilation.',
    },
    {
      step: '02',
      title: 'Retinal Image Acquisition',
      subtitle: 'Instant Quality Verification',
      icon: Camera,
      desc: 'Image is instantly evaluated on edge hardware. If blurred or glare-obscured, technician recaptures the scan immediately while patient is still seated.',
    },
    {
      step: '03',
      title: 'Retivue AI Screening',
      subtitle: 'Biomarker Extraction & Staging',
      icon: Cpu,
      desc: 'Deep learning pipeline traces microaneurysms and hemorrhages. Generates ICDR risk staging and explainable evidence overlays within seconds.',
    },
    {
      step: '04',
      title: 'Clinical Adjudication',
      subtitle: 'Reading Ophthalmologist Review',
      icon: UserCheck,
      desc: 'Ophthalmologist inspects bilateral captures, reviews optical quality metrics, confirms or overrides the AI suggestion, and signs the clinical encounter.',
    },
    {
      step: '05',
      title: 'Tertiary Hospital Referral',
      subtitle: 'Specialty Vitreoretinal Unit Hand-off',
      icon: Hospital,
      desc: 'High-risk severe and proliferative cases receive prioritized referrals with complete pre-screening documentation transmitted to tertiary vitreoretinal surgeons.',
    },
  ];

  return (
    <PublicLayout>
      <div className="py-20 md:py-28 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 select-none">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-mono uppercase tracking-widest text-[#6f7d3e] block mb-2 font-semibold">
            COMMUNITY-TO-TERTIARY WORKFLOW
          </span>
          <h1 className="font-serif text-3xl sm:text-4xl md:text-5xl text-[#1c1d1a] leading-tight">
            Tele-Ophthalmology Network Architecture
          </h1>
          <p className="mt-4 text-sm sm:text-base text-[#4a4c44] font-sans leading-relaxed">
            Bridging rural vision centers with metropolitan retinal specialists through structured clinical hand-offs.
          </p>
        </div>

        {/* Workflow Diagram */}
        <div className="space-y-4">
          {workflowNodes.map((node) => {
            const Icon = node.icon;
            return (
              <div
                key={node.step}
                className="p-6 bg-white border border-[#e8e4d8] rounded-2xl flex flex-col sm:flex-row items-start sm:items-center gap-5 shadow-xs"
              >
                <div className="w-12 h-12 rounded-full bg-[#4a5320] text-white flex items-center justify-center shrink-0 font-serif font-bold text-sm shadow-2xs">
                  {node.step}
                </div>
                <div className="flex-1 space-y-1">
                  <div className="text-[10px] font-mono uppercase text-[#7a7d72] font-semibold">
                    {node.subtitle}
                  </div>
                  <h3 className="text-base font-semibold text-[#1c1d1a] flex items-center gap-2">
                    <Icon size={16} className="text-[#4a5320]" />
                    <span>{node.title}</span>
                  </h3>
                  <p className="text-xs sm:text-sm text-[#5a5d52] leading-relaxed">
                    {node.desc}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Technical Advantages */}
        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-6 bg-white border border-[#e8e4d8] rounded-2xl space-y-3 text-xs shadow-xs">
            <div className="w-10 h-10 rounded-full bg-[#f2f4e8] border border-[#d8debe] flex items-center justify-center text-[#4a5320]">
              <WifiOff size={18} />
            </div>
            <h4 className="font-semibold text-sm text-[#1c1d1a]">Edge & Offline Resilient</h4>
            <p className="text-xs text-[#5a5d52] leading-relaxed">
              Designed to execute in rural mobile vans where internet connectivity is intermittent.
            </p>
          </div>

          <div className="p-6 bg-white border border-[#e8e4d8] rounded-2xl space-y-3 text-xs shadow-xs">
            <div className="w-10 h-10 rounded-full bg-[#f2f4e8] border border-[#d8debe] flex items-center justify-center text-[#4a5320]">
              <Clock size={18} />
            </div>
            <h4 className="font-semibold text-sm text-[#1c1d1a]">Rapid Triage Hand-Off</h4>
            <p className="text-xs text-[#5a5d52] leading-relaxed">
              Reduces specialist review time from weeks to hours by structuring findings beforehand.
            </p>
          </div>

          <div className="p-6 bg-white border border-[#e8e4d8] rounded-2xl space-y-3 text-xs shadow-xs">
            <div className="w-10 h-10 rounded-full bg-[#f2f4e8] border border-[#d8debe] flex items-center justify-center text-[#4a5320]">
              <Shield size={18} />
            </div>
            <h4 className="font-semibold text-sm text-[#1c1d1a]">Clinical Responsibility</h4>
            <p className="text-xs text-[#5a5d52] leading-relaxed">
              Full audit trail compliance maintaining certified clinician ownership of final decisions.
            </p>
          </div>
        </div>

        {/* Footer CTA */}
        <div className="mt-14 p-8 bg-[#f5f3ec] border border-[#e8e4d8] text-[#1c1d1a] rounded-2xl flex flex-col sm:flex-row items-center justify-between gap-5 shadow-xs">
          <div>
            <h4 className="font-serif text-lg font-bold text-[#1c1d1a]">Experience the Tele-Screening Portal</h4>
            <p className="text-xs text-[#5a5d52] mt-1">
              Review live case adjudication queues and patient screening records.
            </p>
          </div>
          <Link
            href="/app"
            className="inline-flex items-center gap-2 bg-[#4a5320] hover:bg-[#3e461a] text-white px-6 py-3 rounded-full text-xs font-semibold no-underline transition-all shadow-sm hover:shadow shrink-0"
          >
            <span>Launch Clinical Portal</span>
            <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    </PublicLayout>
  );
}

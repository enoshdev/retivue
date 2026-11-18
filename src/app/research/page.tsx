'use client';

import React from 'react';
import Link from 'next/link';
import { PublicLayout } from '@/layouts/PublicLayout';
import {
  ShieldCheck,
  Cpu,
  Layers,
  ArrowRight,
  Eye,
} from 'lucide-react';

export default function ResearchPage() {
  const sections = [
    {
      id: 'quality',
      title: 'Image Quality Assessment',
      subtitle: 'Pre-flight ISO 10940 Optical Evaluation',
      icon: ShieldCheck,
      content:
        'A major failure point in community screening programs is the propagation of ungradeable images into automated classifiers. Retivue implements a multi-metric quality filter that validates fundus captures before clinical inference.',
      points: [
        'Frequency-domain focus analysis (gradient MTF sharpness thresholds)',
        'Luminance uniformity mapping detecting peripheral falloff and illumination glare',
        'Centering verification ensuring optic disc and fovea reside within diagnostic field',
        'Automated detection of anterior segment artifacts (pupillary vignette, motion blur)',
      ],
    },
    {
      id: 'structures',
      title: 'Retinal Structure Analysis',
      subtitle: 'Anatomical Landmark Segmentation',
      icon: Eye,
      content:
        'Accurate diabetic retinopathy staging requires contextualizing lesions relative to anatomical landmarks. The segmentation pipeline maps the optic disc, cup-to-disc ratio, foveal avascular zone (FAZ), and primary vascular tree.',
      points: [
        'Vessel caliber tracking and arteriolar-to-venular ratio (AVR)',
        'Optic disc margin localization for peripapillary lesion exclusion',
        'Foveal center triangulation determining proximity of macular-threatening edema',
      ],
    },
    {
      id: 'lesions',
      title: 'Lesion Analysis',
      subtitle: 'Pathology Biomarker Quantification',
      icon: Cpu,
      content:
        'Retivue identifies individual microvascular pathologies corresponding to the International Clinical Diabetic Retinopathy (ICDR) scale and Early Treatment Diabetic Retinopathy Study (ETDRS) severity levels.',
      points: [
        'Microaneurysm (MA) detection down to capillary resolution',
        'Blot and flame hemorrhage segmentation with 4-2-1 rule verification',
        'Hard exudate cluster mapping for macular edema risk scoring',
        'Cotton wool spots (soft exudates) indicating localized retinal ischemia',
      ],
    },
    {
      id: 'explainability',
      title: 'Explainable AI (XAI)',
      subtitle: 'Evidence-Based Attribution without Black Boxes',
      icon: Layers,
      content:
        'Rather than outputting opaque numeric scores, Retivue equips ophthalmologists with visual evidence overlays that localize anatomical regions responsible for model attention.',
      points: [
        'Grad-CAM and Integrated Gradients saliency heatmaps',
        'Lesion coordinate callouts with per-finding confidence ranges',
        'Clinically verifiable attribution aligned with standard medical imaging protocols',
      ],
    },
  ];

  return (
    <PublicLayout>
      <div className="py-20 md:py-28 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 select-none">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <span className="text-xs font-mono uppercase tracking-widest text-[#6f7d3e] block mb-2 font-semibold">
            METHODOLOGY & ALGORITHMIC VALIDATION
          </span>
          <h1 className="font-serif text-3xl sm:text-4xl md:text-5xl text-[#1c1d1a] leading-tight">
            Scientific Foundation & CADe Architecture
          </h1>
          <p className="mt-4 text-sm sm:text-base text-[#4a4c44] font-sans leading-relaxed">
            Engineered around verifiable optical quality, anatomical contextualization, and clinical explainability.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {sections.map((sec) => {
            const Icon = sec.icon;
            return (
              <div
                key={sec.id}
                className="p-6 sm:p-8 bg-white border border-[#e8e4d8] rounded-2xl space-y-4 shadow-xs"
              >
                <div className="flex items-center gap-3.5">
                  <div className="w-11 h-11 rounded-full bg-[#f2f4e8] border border-[#d8debe] flex items-center justify-center text-[#4a5320] shrink-0">
                    <Icon size={20} />
                  </div>
                  <div>
                    <span className="text-[10px] font-mono uppercase text-[#7a7d72] block font-semibold">
                      {sec.subtitle}
                    </span>
                    <h3 className="font-serif text-base text-[#1c1d1a]">
                      {sec.title}
                    </h3>
                  </div>
                </div>

                <p className="text-xs sm:text-sm text-[#5a5d52] leading-relaxed">
                  {sec.content}
                </p>

                <ul className="space-y-1.5 text-[11px] font-mono text-[#5a5d52] border-t border-[#e8e4d8] pt-3">
                  {sec.points.map((pt, idx) => (
                    <li key={idx} className="flex items-start gap-1.5">
                      <span className="text-[#4a5320] font-bold">•</span>
                      <span>{pt}</span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>

        <div className="mt-14 p-8 bg-[#f5f3ec] border border-[#e8e4d8] rounded-2xl flex flex-col sm:flex-row items-center justify-between gap-5 text-xs shadow-xs">
          <div className="space-y-1">
            <div className="font-bold text-[#1c1d1a] font-mono uppercase">
              21 CFR § 886.1100 Advisory Compliance
            </div>
            <p className="text-[#5a5d52]">
              RetiVue algorithm outputs are formatted for human-in-the-loop clinical adjudication.
            </p>
          </div>
          <Link
            href="/app"
            className="inline-flex items-center gap-2 bg-[#4a5320] hover:bg-[#3e461a] text-white px-6 py-3 rounded-full font-semibold no-underline transition-all shadow-sm hover:shadow shrink-0"
          >
            <span>Open Clinical Portal</span>
            <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    </PublicLayout>
  );
}

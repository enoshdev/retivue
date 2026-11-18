'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { RetivueLogo } from '@/components/brand/RetivueLogo';
import { useClinical } from '@/context/ClinicalContext';
import {
  LayoutDashboard,
  Users,
  PlusCircle,
  Layers,
  FileText,
  Settings,
  ArrowUpRight,
  UserCheck,
} from 'lucide-react';

export function AppSidebar() {
  const pathname = usePathname();
  const { currentUser } = useClinical();

  // Unified 6-Item Navigation
  const navItems = [
    { name: 'Dashboard', href: '/app', icon: LayoutDashboard },
    { name: 'Patients', href: '/app/patients', icon: Users },
    { name: 'New Screening', href: '/app/screenings/new', icon: PlusCircle },
    { name: 'Screening History', href: '/app/screenings', icon: Layers },
    { name: 'Reports', href: '/app/reports', icon: FileText },
    { name: 'Settings', href: '/app/settings', icon: Settings },
  ];

  const checkIsActive = (href: string) => {
    if (href === '/app') return pathname === '/app';
    if (href === '/app/screenings/new') return pathname === '/app/screenings/new';
    if (href === '/app/screenings') {
      return (
        pathname === '/app/screenings' ||
        (pathname.startsWith('/app/screenings/') && pathname !== '/app/screenings/new')
      );
    }
    if (href === '/app/patients') {
      return pathname.startsWith('/app/patients');
    }
    if (href === '/app/reports') {
      return pathname.startsWith('/app/reports');
    }
    if (href === '/app/settings') {
      return pathname.startsWith('/app/settings');
    }
    return pathname.startsWith(href);
  };

  return (
    <aside className="hidden md:flex w-64 bg-[#f7f6f1] border-r border-[#e8e4d8] flex-col justify-between h-screen sticky top-0 shrink-0 select-none">
      <div className="p-4 flex flex-col gap-4">
        {/* Brand Lockup */}
        <div className="pb-3 border-b border-[#e8e4d8]">
          <RetivueLogo size="sm" variant="olive" href="/app" />
          <div className="mt-3 px-3 py-1.5 bg-white border border-[#e8e4d8] rounded-full text-[11px] font-mono text-[#5a5d52] flex items-center justify-between shadow-2xs">
            <span className="truncate">{currentUser.facility}</span>
          </div>
        </div>

        {/* Unified Practitioner Identity Card */}
        <div className="px-4 py-3 bg-white rounded-2xl border border-[#e8e4d8] shadow-2xs">
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-[#7a7d72] font-semibold">
            <UserCheck size={13} className="text-[#4a5320]" />
            <span>CLINICAL OPERATOR</span>
          </div>
          <div className="text-xs font-semibold text-[#1c1d1a] mt-1 truncate">
            {currentUser.name}
          </div>
          <div className="text-[11px] text-[#6f7d3e] truncate mt-0.5 font-mono">
            {currentUser.registrationNumber ? `Reg #${currentUser.registrationNumber}` : currentUser.email}
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="flex flex-col gap-1.5 pt-1">
          {navItems.map((item) => {
            const isActive = checkIsActive(item.href);
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3.5 py-2.5 rounded-full text-xs font-medium transition-all no-underline ${
                  isActive
                    ? 'bg-[#4a5320] text-white font-semibold shadow-xs'
                    : 'text-[#4a4c44] hover:bg-[#edeae0] hover:text-[#1c1d1a]'
                }`}
              >
                <Icon
                  size={16}
                  strokeWidth={isActive ? 2 : 1.75}
                  className={isActive ? 'text-white' : 'text-[#7a7d72]'}
                />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer Info & Public Link */}
      <div className="p-4 pt-2 border-t border-[#e8e4d8] mt-auto">
        <div className="py-2">
          <div className="text-[10px] font-mono text-[#7a7d72]">
            RETIVUE CADe v4.8.1
          </div>
          <div className="text-[10px] text-[#5a5d52] mt-0.5">
            Non-Diagnostic Screening Decision Support
          </div>
        </div>
        <Link
          href="/"
          className="flex items-center justify-between text-xs text-[#4a4c44] hover:text-[#1c1d1a] py-1.5 text-[11px] transition-colors no-underline font-medium"
        >
          <span>Public Site Overview</span>
          <ArrowUpRight size={13} className="text-[#7a7d72]" />
        </Link>
      </div>
    </aside>
  );
}

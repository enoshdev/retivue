'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useClinical } from '@/context/ClinicalContext';
import { CdsDisclaimerBanner } from '@/components/clinical/CdsDisclaimerBanner';
import {
  PlusCircle,
  Menu,
  X,
  Layers,
  Users,
  FileText,
  Settings,
  LayoutDashboard,
  LogOut,
  ChevronDown,
} from 'lucide-react';

export function AppHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const { currentUser, logout, notification, clearNotification, setNotification } = useClinical();

  const getSectionTitle = () => {
    if (pathname === '/app') return 'Clinical Dashboard';
    if (pathname.startsWith('/app/screenings/new')) return 'New Retinal Screening';
    if (pathname.startsWith('/app/screenings/')) return 'Clinical Review Workspace';
    if (pathname.startsWith('/app/screenings')) return 'Screening History';
    if (pathname.startsWith('/app/patients/new')) return 'Register New Patient';
    if (pathname.startsWith('/app/patients/')) return 'Patient Record';
    if (pathname.startsWith('/app/patients')) return 'Patient Directory';
    if (pathname.startsWith('/app/reports/')) return 'Clinical Encounter Report';
    if (pathname.startsWith('/app/reports')) return 'Clinical Reports';
    if (pathname.startsWith('/app/referrals')) return 'Specialist Referrals';
    if (pathname.startsWith('/app/settings')) return 'Settings';
    return 'Screening Console';
  };

  const handleLogout = async () => {
    setUserDropdownOpen(false);
    setMobileMenuOpen(false);
    try {
      await logout();
      setNotification({
        type: 'info',
        message: 'Signed out of Retivue clinical session.',
      });
      router.push('/login');
    } catch {
      router.push('/login');
    }
  };

  const mobileNavItems = [
    { name: 'Dashboard', href: '/app', icon: LayoutDashboard },
    { name: 'Patients', href: '/app/patients', icon: Users },
    { name: 'New Screening', href: '/app/screenings/new', icon: PlusCircle },
    { name: 'Screening History', href: '/app/screenings', icon: Layers },
    { name: 'Reports', href: '/app/reports', icon: FileText },
    { name: 'Settings', href: '/app/settings', icon: Settings },
  ];

  return (
    <>
      {/* Top Universal CDS Disclaimer Banner */}
      <CdsDisclaimerBanner compact />

      {/* Ephemeral Notification Toast */}
      {notification && (
        <div
          className={`px-4 py-2 text-xs font-mono flex items-center justify-between border-b transition-all ${
            notification.type === 'success'
              ? 'bg-emerald-50 text-emerald-900 border-emerald-200'
              : notification.type === 'error'
              ? 'bg-rose-50 text-rose-900 border-rose-200'
              : 'bg-[#f2f4e8] text-[#4a5320] border-[#d8debe]'
          }`}
        >
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                notification.type === 'success'
                  ? 'bg-emerald-600'
                  : notification.type === 'error'
                  ? 'bg-rose-600'
                  : 'bg-[#4a5320]'
              }`}
            />
            <span>{notification.message}</span>
          </div>
          <button
            type="button"
            onClick={clearNotification}
            className="text-slate-500 hover:text-slate-800 text-[11px] cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Console Header */}
      <header className="h-14 w-full bg-[#faf9f5]/95 backdrop-blur-md border-b border-[#e8e4d8] px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30 select-none">
        {/* Left: Mobile hamburger + Context breadcrumb */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setMobileMenuOpen(true)}
            className="md:hidden p-1.5 -ml-1 text-[#4a4c44] hover:text-[#1c1d1a] transition-colors"
            aria-label="Open Navigation Menu"
          >
            <Menu size={18} />
          </button>

          <span className="text-[11px] font-mono uppercase tracking-wider text-[#7a7d72] hidden sm:inline">
            RETIVUE PLATFORM
          </span>
          <span className="text-[#d8debe] hidden sm:inline">/</span>
          <h2 className="text-xs font-semibold text-[#1c1d1a] truncate">
            {getSectionTitle()}
          </h2>
        </div>

        {/* Right Controls: User Profile + Action */}
        <div className="flex items-center gap-3">
          {/* New Screening Quick Action */}
          <Link
            href="/app/screenings/new"
            className="hidden sm:inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-[#4a5320] hover:bg-[#3e461a] text-white text-xs font-semibold shadow-2xs transition-all no-underline"
          >
            <PlusCircle size={14} />
            <span>New Screening</span>
          </Link>

          {/* Unified User Profile Dropdown */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setUserDropdownOpen(!userDropdownOpen)}
              className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-white hover:bg-[#f5f3ec] border border-[#e8e4d8] text-xs text-[#1c1d1a] transition-colors cursor-pointer shadow-2xs"
            >
              <div className="w-6 h-6 rounded-full bg-[#f2f4e8] text-[#4a5320] border border-[#d8debe] flex items-center justify-center font-serif text-[11px] font-bold">
                {currentUser.avatarInitials}
              </div>
              <span className="font-semibold text-xs hidden md:inline truncate max-w-[140px]">
                {currentUser.name}
              </span>
              <ChevronDown size={13} className="text-[#7a7d72]" />
            </button>

            {userDropdownOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-white border border-[#e8e4d8] rounded-2xl shadow-lg p-2 z-50 animate-in fade-in zoom-in-95 duration-100">
                <div className="px-3 py-2 border-b border-[#e8e4d8] mb-1">
                  <div className="text-xs font-semibold text-[#1c1d1a] truncate">
                    {currentUser.name}
                  </div>
                  <div className="text-[11px] text-[#7a7d72] truncate font-mono">
                    {currentUser.email}
                  </div>
                  <div className="text-[10px] text-[#4a5320] font-mono mt-0.5 truncate">
                    {currentUser.facility}
                  </div>
                </div>

                <Link
                  href="/app/settings"
                  onClick={() => setUserDropdownOpen(false)}
                  className="flex items-center gap-2 px-3 py-2 text-xs text-[#4a4c44] hover:text-[#1c1d1a] hover:bg-[#f5f3ec] rounded-xl transition-colors no-underline"
                >
                  <Settings size={14} />
                  <span>Account & Settings</span>
                </Link>

                <Link
                  href="/app/screenings"
                  onClick={() => setUserDropdownOpen(false)}
                  className="flex items-center gap-2 px-3 py-2 text-xs text-[#4a4c44] hover:text-[#1c1d1a] hover:bg-[#f5f3ec] rounded-xl transition-colors no-underline"
                >
                  <Layers size={14} />
                  <span>Screening History</span>
                </Link>

                <div className="border-t border-[#e8e4d8] my-1 pt-1">
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs text-rose-600 hover:bg-rose-50 rounded-xl transition-colors cursor-pointer text-left font-medium"
                  >
                    <LogOut size={14} />
                    <span>Sign Out</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Mobile Navigation Drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          />

          <div className="relative flex-1 flex flex-col max-w-xs w-full bg-[#f7f6f1] border-r border-[#e8e4d8] p-5 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-[#e8e4d8]">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-full bg-[#4a5320] text-white flex items-center justify-center font-serif text-sm font-bold">
                  R
                </div>
                <span className="font-serif font-bold text-base text-[#1c1d1a]">RETIVUE</span>
              </div>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                className="p-1.5 text-[#7a7d72] hover:text-[#1c1d1a]"
              >
                <X size={18} />
              </button>
            </div>

            <nav className="flex flex-col gap-1.5 py-4">
              {mobileNavItems.map((item) => {
                const isActive = pathname === item.href;
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={`flex items-center gap-3 px-3.5 py-2.5 rounded-full text-xs font-medium no-underline ${
                      isActive
                        ? 'bg-[#4a5320] text-white font-semibold'
                        : 'text-[#4a4c44] hover:bg-[#edeae0]'
                    }`}
                  >
                    <Icon size={16} />
                    <span>{item.name}</span>
                  </Link>
                );
              })}
            </nav>

            <div className="mt-auto border-t border-[#e8e4d8] pt-4">
              <button
                type="button"
                onClick={handleLogout}
                className="flex items-center gap-2 text-xs text-rose-700 font-semibold px-2 py-2"
              >
                <LogOut size={15} />
                <span>Sign Out</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

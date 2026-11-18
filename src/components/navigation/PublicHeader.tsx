'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { RetivueLogo } from '@/components/brand/RetivueLogo';
import { ArrowRight, Menu, X } from 'lucide-react';

export function PublicHeader() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const pathname = usePathname();

  const navLinks = [
    { label: 'Overview', href: '/' },
    { label: 'How it works', href: '/how-it-works' },
    { label: 'Technology', href: '/research' },
    { label: 'Telemedicine', href: '/telemedicine' },
    { label: 'About', href: '/about' },
  ];

  return (
    <header className="sticky top-0 z-50 w-full bg-[#faf9f5]/95 backdrop-blur-md border-b border-[#e8e4d8] transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-18 flex items-center justify-between">
        {/* Left: Retivue Brand */}
        <div className="flex md:flex-1 items-center justify-start">
          <RetivueLogo size="md" variant="olive" href="/" />
        </div>

        {/* Center: Desktop Navigation */}
        <nav className="hidden md:flex items-center justify-center gap-8 lg:gap-10 shrink-0">
          {navLinks.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`text-xs transition-colors no-underline py-1 ${
                  isActive
                    ? 'text-[#1c1d1a] font-bold underline underline-offset-8 decoration-[#4a5320]'
                    : 'text-[#4a4c44] hover:text-[#1c1d1a] font-medium'
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        {/* Right: Actions */}
        <div className="hidden md:flex md:flex-1 items-center justify-end gap-5">
          <Link
            href="/login"
            className="text-xs font-semibold text-[#4a4c44] hover:text-[#1c1d1a] transition-colors no-underline shrink-0"
          >
            Clinical Portal
          </Link>
          <Link
            href="/app"
            className="inline-flex items-center gap-1.5 bg-[#4a5320] hover:bg-[#3e461a] text-white text-xs font-semibold px-5 py-2.5 rounded-full transition-all duration-200 shadow-xs hover:shadow no-underline shrink-0"
          >
            <span>Start Screening</span>
            <ArrowRight size={13} />
          </Link>
        </div>

        {/* Mobile Hamburger */}
        <div className="flex items-center md:hidden gap-2">
          <Link
            href="/app"
            className="inline-flex items-center gap-1 bg-[#4a5320] text-white text-[11px] font-semibold px-3 py-1.5 rounded-full no-underline"
          >
            <span>Screening</span>
          </Link>
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-1.5 text-[#4a4c44] hover:text-[#1c1d1a] focus:outline-none"
            aria-label="Toggle Mobile Menu"
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-[#e8e4d8] bg-[#faf9f5] px-4 py-5 space-y-4 shadow-md">
          <nav className="flex flex-col gap-2">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className="text-xs font-medium text-[#4a4c44] hover:text-[#1c1d1a] py-1.5 no-underline"
              >
                {link.label}
              </Link>
            ))}
          </nav>
          <div className="pt-3 border-t border-[#e8e4d8] flex flex-col gap-2.5">
            <Link
              href="/login"
              onClick={() => setMobileMenuOpen(false)}
              className="text-xs text-center py-2 text-[#4a4c44] font-semibold no-underline"
            >
              Clinical Portal
            </Link>
            <Link
              href="/app"
              onClick={() => setMobileMenuOpen(false)}
              className="text-xs text-center py-2.5 bg-[#4a5320] text-white font-semibold rounded-full no-underline"
            >
              Start Screening
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}

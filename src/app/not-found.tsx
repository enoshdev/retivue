'use client';

import React from 'react';
import Link from 'next/link';
import { RetivueLogo } from '@/components/brand/RetivueLogo';
import { ArrowLeft, Home, Compass } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between p-6 sm:p-10 select-none">
      <div className="max-w-md w-full mx-auto flex items-center justify-between">
        <RetivueLogo size="md" variant="dark" href="/" />
        <Link
          href="/"
          className="text-xs text-slate-500 hover:text-slate-800 transition-colors font-medium no-underline"
        >
          ← Return to Home
        </Link>
      </div>

      <div className="max-w-md w-full mx-auto bg-white border border-slate-200/90 rounded-2xl p-8 sm:p-10 text-center space-y-5 shadow-sm my-8">
        <div className="w-14 h-14 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-700 mx-auto">
          <Compass size={24} strokeWidth={1.75} />
        </div>

        <div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold block">
            HTTP 404 • ROUTE UNRESOLVED
          </span>
          <h1 className="text-xl font-bold text-slate-900 mt-1">
            Clinical Resource Not Found
          </h1>
          <p className="text-xs text-slate-500 mt-1 leading-relaxed">
            The requested clinical workspace, patient record, or route does not exist or has been relocated within the registry.
          </p>
        </div>

        <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-2.5">
          <Link
            href="/app"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-semibold transition-all shadow-xs hover:shadow no-underline"
          >
            <Home size={14} />
            <span>Launch Clinical Console</span>
          </Link>
          <Link
            href="/"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 px-4 py-2.5 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-xl text-xs font-medium transition-colors no-underline"
          >
            <ArrowLeft size={13} />
            <span>Public Site</span>
          </Link>
        </div>
      </div>

      <div className="max-w-md w-full mx-auto text-center text-[11px] font-mono text-slate-400">
        RETIVUE CADe v4.8.1 • Clinical Decision Support Systems
      </div>
    </div>
  );
}


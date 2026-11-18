'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { RetivueLogo } from '@/components/brand/RetivueLogo';
import { Mail, CheckCircle2 } from 'lucide-react';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setSubmitted(true);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between p-6 sm:p-10 select-none">
      <div className="max-w-md w-full mx-auto flex items-center justify-between">
        <RetivueLogo size="md" variant="dark" href="/" />
        <Link
          href="/login"
          className="text-xs text-slate-500 hover:text-slate-800 transition-colors font-medium no-underline"
        >
          ← Back to Sign In
        </Link>
      </div>

      <div className="max-w-md w-full mx-auto bg-white border border-slate-200/90 rounded-2xl p-8 sm:p-10 space-y-6 shadow-sm my-8">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold block">
            CREDENTIAL RECOVERY
          </span>
          <h1 className="text-2xl font-bold text-slate-900 mt-1">
            Reset Password
          </h1>
          <p className="text-xs text-slate-500 mt-1 leading-relaxed">
            Enter your institutional email address to receive password reset and verification instructions.
          </p>
        </div>

        {submitted ? (
          <div className="p-4 bg-emerald-50 border border-emerald-200/80 rounded-xl text-xs text-emerald-900 space-y-2">
            <div className="flex items-center gap-2 font-bold">
              <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
              <span>Password Recovery Instructions Dispatched</span>
            </div>
            <p className="text-[11px] text-emerald-800 leading-relaxed">
              If an authorized account is associated with <strong>{email}</strong>, a secure reset token has been sent. Please check your institutional inbox.
            </p>
            <div className="pt-2">
              <Link
                href="/login"
                className="text-xs font-semibold text-emerald-900 underline"
              >
                Return to Login
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 text-xs">
            <div>
              <label className="block text-[11px] font-mono uppercase text-slate-500 font-semibold mb-1">
                Institutional Email
              </label>
              <div className="relative">
                <Mail size={14} className="absolute left-3.5 top-2.5 text-slate-400" />
                <input
                  type="email"
                  required
                  placeholder="doctor@hospital.org"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-10 pr-3 py-2 bg-slate-50/70 border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-800 transition-all font-mono text-xs"
                />
              </div>
            </div>

            <button
              type="submit"
              className="w-full py-2.5 px-4 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-semibold transition-all shadow-xs hover:shadow cursor-pointer"
            >
              Send Reset Link
            </button>
          </form>
        )}
      </div>

      <div className="max-w-md w-full mx-auto text-center text-[11px] font-mono text-slate-400">
        RETIVUE CADe v4.8.1 • 21 CFR § 886.1100 Compliant Screening Interface
      </div>
    </div>
  );
}


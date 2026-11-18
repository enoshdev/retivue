'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { RetivueLogo } from '@/components/brand/RetivueLogo';
import { useClinical } from '@/context/ClinicalContext';
import { ApiError } from '@/lib/api';
import {
  ArrowRight,
  AlertTriangle,
  ShieldCheck,
  User,
  Mail,
  Lock,
  Building2,
  FileCheck2,
  Loader2,
} from 'lucide-react';

export default function SignupPage() {
  const router = useRouter();
  const { registerUser, isAuthenticated, isLoadingAuth, setNotification } = useClinical();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [facilityName, setFacilityName] = useState('');
  const [registrationNumber, setRegistrationNumber] = useState('');
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // If already authenticated with a valid session, redirect directly into the platform
  useEffect(() => {
    if (!isLoadingAuth && isAuthenticated) {
      router.replace('/app');
    }
  }, [isAuthenticated, isLoadingAuth, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!fullName.trim() || !email.trim() || !password.trim()) {
      setErrorMsg('Please complete all required fields (Name, Email, Password).');
      return;
    }

    if (password.length < 8) {
      setErrorMsg('Password must be at least 8 characters long.');
      return;
    }

    if (!termsAccepted) {
      setErrorMsg('You must review and accept the Clinical Decision Support governance terms.');
      return;
    }

    setIsSubmitting(true);
    try {
      await registerUser({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        facility_name: facilityName.trim() || undefined,
        registration_number: registrationNumber.trim() || undefined,
      });

      setNotification({
        type: 'success',
        message: `Account created for ${fullName.trim()}. Welcome to Retivue.`,
      });
      router.push('/app');
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setErrorMsg(err.message);
      } else if (err instanceof Error) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg('Registration failed. Please check your information and try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#faf9f5] flex flex-col justify-between p-6 sm:p-10 select-none">
      {/* Top Header */}
      <div className="max-w-lg w-full mx-auto flex items-center justify-between">
        <RetivueLogo size="md" variant="olive" href="/" />
        <Link
          href="/login"
          className="text-xs text-[#7a7d72] hover:text-[#1c1d1a] transition-colors font-medium no-underline"
        >
          Sign In Instead →
        </Link>
      </div>

      {/* Main Registration Card */}
      <div className="max-w-lg w-full mx-auto bg-white border border-[#e8e4d8] rounded-2xl p-8 sm:p-10 space-y-6 shadow-xs my-8">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-[#6f7d3e] font-semibold block">
            CLINICAL PLATFORM ONBOARDING
          </span>
          <h1 className="font-serif text-2xl sm:text-3xl text-[#1c1d1a] mt-1">
            Create Retivue Account
          </h1>
          <p className="text-xs text-[#5a5d52] mt-1.5 leading-relaxed">
            Register to screen retinal fundus images for diabetic retinopathy and access decision-support tools.
          </p>
        </div>

        {errorMsg && (
          <div className="p-3.5 bg-rose-50 border border-rose-200/80 rounded-xl text-xs text-rose-800 flex items-center gap-2.5">
            <AlertTriangle size={15} className="text-rose-600 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Unified Registration Form */}
        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div className="space-y-1.5">
            <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold">
              Full Legal / Professional Name *
            </label>
            <div className="relative">
              <User size={15} className="absolute left-3.5 top-3 text-[#7a7d72]" />
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Dr. Full Name or Practitioner Name"
                className="w-full pl-10 pr-3.5 py-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a] placeholder:text-[#a8aba0] focus:outline-none focus:border-[#4a5320] transition-colors"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold">
              Professional Email Address *
            </label>
            <div className="relative">
              <Mail size={15} className="absolute left-3.5 top-3 text-[#7a7d72]" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@clinic-or-hospital.org"
                className="w-full pl-10 pr-3.5 py-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a] placeholder:text-[#a8aba0] focus:outline-none focus:border-[#4a5320] transition-colors"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold">
              Create Password * (min 8 characters)
            </label>
            <div className="relative">
              <Lock size={15} className="absolute left-3.5 top-3 text-[#7a7d72]" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full pl-10 pr-3.5 py-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a] placeholder:text-[#a8aba0] focus:outline-none focus:border-[#4a5320] transition-colors"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            <div className="space-y-1.5">
              <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold">
                Facility / Practice Name (Optional)
              </label>
              <div className="relative">
                <Building2 size={15} className="absolute left-3.5 top-3 text-[#7a7d72]" />
                <input
                  type="text"
                  value={facilityName}
                  onChange={(e) => setFacilityName(e.target.value)}
                  placeholder="e.g. Eye Center / Clinic"
                  className="w-full pl-10 pr-3.5 py-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a] placeholder:text-[#a8aba0] focus:outline-none focus:border-[#4a5320] transition-colors"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold">
                Medical / License # (Optional)
              </label>
              <div className="relative">
                <FileCheck2 size={15} className="absolute left-3.5 top-3 text-[#7a7d72]" />
                <input
                  type="text"
                  value={registrationNumber}
                  onChange={(e) => setRegistrationNumber(e.target.value)}
                  placeholder="e.g. MED-74829"
                  className="w-full pl-10 pr-3.5 py-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a] placeholder:text-[#a8aba0] focus:outline-none focus:border-[#4a5320] transition-colors"
                />
              </div>
            </div>
          </div>

          {/* Terms & Governance */}
          <div className="pt-2">
            <label className="flex items-start gap-2.5 text-xs text-[#5a5d52] cursor-pointer">
              <input
                type="checkbox"
                checked={termsAccepted}
                onChange={(e) => setTermsAccepted(e.target.checked)}
                className="mt-0.5 rounded text-[#4a5320] focus:ring-[#4a5320]"
              />
              <span>
                I acknowledge that RETIVUE CADe is an adjunct clinical screening aid (21 CFR § 886.1100). Final medical interpretation, diagnosis, and referral decisions remain the exclusive professional responsibility of qualified clinicians.
              </span>
            </label>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full mt-4 py-3 px-4 bg-[#4a5320] hover:bg-[#3e461a] disabled:opacity-60 text-white text-xs font-semibold rounded-full flex items-center justify-center gap-2 transition-all shadow-xs cursor-pointer"
          >
            {isSubmitting ? (
              <span className="flex items-center gap-2">
                <Loader2 size={14} className="animate-spin" />
                Creating Account...
              </span>
            ) : (
              <>
                <span>Create Retivue Account</span>
                <ArrowRight size={14} />
              </>
            )}
          </button>
        </form>

        <div className="text-center pt-2">
          <p className="text-xs text-[#5a5d52]">
            Already have an account?{' '}
            <Link
              href="/login"
              className="text-[#4a5320] hover:underline font-semibold no-underline"
            >
              Sign In Instead →
            </Link>
          </p>
        </div>
      </div>

      {/* Footer */}
      <div className="max-w-lg w-full mx-auto text-center">
        <div className="flex items-center justify-center gap-1.5 text-[11px] text-[#7a7d72]">
          <ShieldCheck size={14} className="text-[#6f7d3e]" />
          <span>Non-Diagnostic Clinical Decision Support Platform</span>
        </div>
      </div>
    </div>
  );
}

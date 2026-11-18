'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { RetivueLogo } from '@/components/brand/RetivueLogo';
import { useClinical } from '@/context/ClinicalContext';
import { ApiError } from '@/lib/api';
import {
  Lock,
  Mail,
  Eye,
  EyeOff,
  ArrowRight,
  AlertCircle,
  ShieldCheck,
  Loader2,
} from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const { login, isAuthenticated, isLoadingAuth, setNotification } = useClinical();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [oauthNotice, setOauthNotice] = useState<string | null>(null);

  // If already authenticated with a valid session, redirect directly into the platform
  useEffect(() => {
    if (!isLoadingAuth && isAuthenticated) {
      router.replace('/app');
    }
  }, [isAuthenticated, isLoadingAuth, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage(null);

    if (!email.trim() || !password.trim()) {
      setErrorMessage('Please enter both your email address and password.');
      setIsLoading(false);
      return;
    }

    try {
      await login({
        email: email.trim(),
        password,
      });
      setNotification({
        type: 'success',
        message: 'Signed in successfully. Welcome to Retivue.',
      });
      router.push('/app');
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message);
      } else if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Authentication failed. Please check your credentials.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleOAuthClick = () => {
    setOauthNotice('Federated enterprise SSO is reserved for integrated hospital networks. Please use your email credentials.');
  };

  return (
    <div className="min-h-screen bg-[#faf9f5] flex flex-col justify-between p-6 sm:p-10 select-none">
      {/* Top Header */}
      <div className="max-w-md w-full mx-auto flex items-center justify-between">
        <RetivueLogo size="md" variant="olive" href="/" />
        <Link
          href="/"
          className="text-xs text-[#7a7d72] hover:text-[#1c1d1a] transition-colors font-medium no-underline"
        >
          ← Return to Public Site
        </Link>
      </div>

      {/* Main Login Card */}
      <div className="max-w-md w-full mx-auto bg-white border border-[#e8e4d8] rounded-2xl p-8 sm:p-10 space-y-6 shadow-xs my-8">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-[#6f7d3e] font-semibold block">
            RETIVUE PLATFORM ACCESS
          </span>
          <h1 className="font-serif text-2xl sm:text-3xl text-[#1c1d1a] mt-1">
            Sign In to Retivue
          </h1>
          <p className="text-xs text-[#5a5d52] mt-1.5 leading-relaxed">
            Enter your account credentials to access the diabetic retinopathy screening and review platform.
          </p>
        </div>

        {/* OAuth Notice */}
        {oauthNotice && (
          <div className="p-4 bg-[#f2f4e8] border border-[#d8debe] rounded-2xl text-xs text-[#4a5320] flex items-start gap-2.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#4a5320] mt-1.5 shrink-0" />
            <p className="text-[11px] leading-relaxed">{oauthNotice}</p>
          </div>
        )}

        {/* Error Message */}
        {errorMessage && (
          <div className="p-3.5 bg-rose-50 border border-rose-200/80 rounded-xl text-xs text-rose-800 flex items-center gap-2.5">
            <AlertCircle size={15} className="text-rose-600 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Google SSO Button */}
        <button
          type="button"
          onClick={handleOAuthClick}
          className="w-full py-3 px-4 bg-white hover:bg-[#f5f3ec] border border-[#e8e4d8] rounded-full text-[#1c1d1a] text-xs font-semibold flex items-center justify-center gap-2.5 transition-all shadow-2xs cursor-pointer"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
            />
          </svg>
          <span>Continue with Google</span>
        </button>

        <div className="relative flex items-center justify-center">
          <div className="border-t border-[#e8e4d8] w-full" />
          <span className="bg-white px-3 text-[10px] font-mono uppercase text-[#7a7d72] tracking-wider absolute">
            OR EMAIL
          </span>
        </div>

        {/* Credentials Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold">
              Email Address *
            </label>
            <div className="relative">
              <Mail size={15} className="absolute left-3.5 top-3 text-[#7a7d72]" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@institution.org"
                className="w-full pl-10 pr-3.5 py-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a] placeholder:text-[#a8aba0] focus:outline-none focus:border-[#4a5320] transition-colors"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="block text-[11px] font-mono uppercase text-[#7a7d72] font-semibold">
                Password *
              </label>
              <Link
                href="/forgot-password"
                className="text-[11px] text-[#6f7d3e] hover:text-[#4a5320] transition-colors no-underline"
              >
                Forgot password?
              </Link>
            </div>
            <div className="relative">
              <Lock size={15} className="absolute left-3.5 top-3 text-[#7a7d72]" />
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full pl-10 pr-10 py-2.5 bg-[#faf9f5] border border-[#e8e4d8] rounded-xl text-xs text-[#1c1d1a] placeholder:text-[#a8aba0] focus:outline-none focus:border-[#4a5320] transition-colors"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3.5 top-3 text-[#7a7d72] hover:text-[#1c1d1a]"
              >
                {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full mt-2 py-3 px-4 bg-[#4a5320] hover:bg-[#3e461a] disabled:opacity-60 text-white text-xs font-semibold rounded-full flex items-center justify-center gap-2 transition-all shadow-xs cursor-pointer"
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <Loader2 size={14} className="animate-spin" />
                Signing In...
              </span>
            ) : (
              <>
                <span>Sign In to Platform</span>
                <ArrowRight size={14} />
              </>
            )}
          </button>
        </form>

        <div className="text-center pt-2">
          <p className="text-xs text-[#5a5d52]">
            Don&apos;t have an account?{' '}
            <Link
              href="/signup"
              className="text-[#4a5320] hover:underline font-semibold no-underline"
            >
              Create Account →
            </Link>
          </p>
        </div>
      </div>

      {/* Footer Disclaimer */}
      <div className="max-w-md w-full mx-auto text-center space-y-2">
        <div className="flex items-center justify-center gap-1.5 text-[11px] text-[#7a7d72]">
          <ShieldCheck size={14} className="text-[#6f7d3e]" />
          <span>Clinical Decision Support Platform • 21 CFR § 886.1100 Compliant</span>
        </div>
      </div>
    </div>
  );
}

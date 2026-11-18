'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function NewRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/app/screenings/new');
  }, [router]);
  return null;
}

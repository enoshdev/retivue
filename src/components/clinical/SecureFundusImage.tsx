'use client';

import React, { useEffect, useState } from 'react';
import { screeningApi } from '@/lib/api';
import { Loader2, AlertTriangle } from 'lucide-react';

interface SecureFundusImageProps {
  screeningId: string;
  eye: 'OD' | 'OS';
  /** Cache-busting key (e.g. uploaded image id or sha256) so replacements immediately re-fetch */
  versionKey?: string;
  alt: string;
  className?: string;
  style?: React.CSSProperties;
}

export function SecureFundusImage({
  screeningId,
  eye,
  versionKey = '',
  alt,
  className = 'w-full h-full object-contain',
  style,
}: SecureFundusImageProps) {
  const requestKey = `${screeningId}:${eye}:${versionKey}`;
  const [result, setResult] = useState<{
    key: string;
    blobUrl: string | null;
    error: string | null;
  }>({ key: '', blobUrl: null, error: null });

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;

    screeningApi
      .fetchImageBlobUrl(screeningId, eye)
      .then((url) => {
        objectUrl = url;
        if (active) {
          setResult({ key: requestKey, blobUrl: url, error: null });
        } else {
          URL.revokeObjectURL(url);
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setResult({
            key: requestKey,
            blobUrl: null,
            error: err instanceof Error ? err.message : `Unable to load ${eye} image.`,
          });
        }
      });

    return () => {
      active = false;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [screeningId, eye, requestKey]);

  const loading = result.key !== requestKey;

  if (loading) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-[#8e9185] text-xs font-mono p-4">
        <Loader2 size={20} className="animate-spin text-[#dee9a6]" />
        <span>Streaming secured {eye} image...</span>
      </div>
    );
  }

  if (result.error || !result.blobUrl) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-rose-300 text-xs p-4 text-center">
        <AlertTriangle size={20} className="text-rose-400 shrink-0" />
        <span className="max-w-xs">{result.error || `Secured ${eye} image unavailable.`}</span>
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={result.blobUrl} alt={alt} className={className} style={style} />
  );
}

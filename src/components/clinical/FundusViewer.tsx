'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  AiExplanationResponse,
  clinicalWorkflowApi,
  screeningApi,
} from '@/lib/api';
import {
  Layers,
  Eye,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Download,
  Columns,
  Sparkles,
  Loader2,
  AlertCircle,
  Info,
} from 'lucide-react';

export type ViewerMode = 'ORIGINAL' | 'OVERLAY' | 'HEATMAP' | 'SPLIT';

const DR_CLASSES = [
  { grade: 0, label: 'No DR', fullName: 'Class 0: No DR' },
  { grade: 1, label: 'Mild', fullName: 'Class 1: Mild NPDR' },
  { grade: 2, label: 'Moderate', fullName: 'Class 2: Moderate NPDR' },
  { grade: 3, label: 'Severe', fullName: 'Class 3: Severe NPDR' },
  { grade: 4, label: 'Proliferative', fullName: 'Class 4: Proliferative DR' },
];

interface FundusViewerProps {
  screeningId: string;
  eye: 'OD' | 'OS';
  patientRef?: string;
  imageSrc?: string | null;
  explanation?: AiExplanationResponse | null;
  probabilities?: Record<string, number>;
  predictedGrade?: number | null;
  predictedLabel?: string | null;
  gradable?: boolean;
  qualityReason?: string | null;
  onExplanationUpdate?: (explanation: AiExplanationResponse) => void;
  className?: string;
}

export function FundusViewer({
  screeningId,
  eye,
  patientRef = '',
  imageSrc = null,
  explanation = null,
  probabilities = {},
  predictedGrade = null,
  predictedLabel = null,
  gradable = true,
  qualityReason = null,
  onExplanationUpdate,
  className = '',
}: FundusViewerProps) {
  const [activeMode, setActiveMode] = useState<ViewerMode>('OVERLAY');
  
  // Selected target class handling
  const defaultTargetClass =
    explanation?.target_class ??
    (predictedGrade !== null && predictedGrade !== undefined ? predictedGrade : 0);
  const [customTargetClass, setCustomTargetClass] = useState<number | null>(null);
  const selectedTargetClass = customTargetClass !== null ? customTargetClass : defaultTargetClass;

  const [opacity, setOpacity] = useState<number>(75);
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [cursorPos, setCursorPos] = useState<{ x: number; y: number } | null>(null);

  // Original image fallback loading
  const [fetchedImageBlob, setFetchedImageBlob] = useState<string | null>(null);
  const effectiveImageSrc = imageSrc || fetchedImageBlob;

  // Live artifact blob URLs
  const [overlayBlobUrl, setOverlayBlobUrl] = useState<string | null>(null);
  const [heatmapBlobUrl, setHeatmapBlobUrl] = useState<string | null>(null);
  const [fetchedExplanation, setFetchedExplanation] = useState<AiExplanationResponse | null>(null);
  const currentExplanation = fetchedExplanation || explanation;

  const [loadingArtifacts, setLoadingArtifacts] = useState<boolean>(false);
  const [isRegenerating, setIsRegenerating] = useState<boolean>(false);
  const [artifactError, setArtifactError] = useState<string | null>(null);

  const prevBlobUrlsRef = useRef<{ overlay?: string; heatmap?: string }>({});

  // Persistent callback ref to avoid infinite re-render loops
  const onExplanationUpdateRef = useRef(onExplanationUpdate);
  useEffect(() => {
    onExplanationUpdateRef.current = onExplanationUpdate;
  }, [onExplanationUpdate]);

  // Load fallback image blob if imageSrc not provided
  useEffect(() => {
    if (imageSrc || !screeningId || !eye) {
      return;
    }
    let active = true;
    let url: string | null = null;
    screeningApi
      .fetchImageBlobUrl(screeningId, eye)
      .then((bUrl) => {
        if (!active) {
          URL.revokeObjectURL(bUrl);
          return;
        }
        url = bUrl;
        setFetchedImageBlob(bUrl);
      })
      .catch(() => {
        if (active) setFetchedImageBlob(null);
      });

    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [screeningId, eye, imageSrc]);

  // Load overlay and heatmap blobs whenever screeningId, eye, or selectedTargetClass changes
  useEffect(() => {
    let active = true;

    if (!screeningId || !gradable) {
      return;
    }

    const loadArtifacts = async () => {
      setLoadingArtifacts(true);
      setArtifactError(null);

      // Clean up previous blob URLs
      if (prevBlobUrlsRef.current.overlay) {
        URL.revokeObjectURL(prevBlobUrlsRef.current.overlay);
        prevBlobUrlsRef.current.overlay = undefined;
      }
      if (prevBlobUrlsRef.current.heatmap) {
        URL.revokeObjectURL(prevBlobUrlsRef.current.heatmap);
        prevBlobUrlsRef.current.heatmap = undefined;
      }

      try {
        const expl = await clinicalWorkflowApi.getExplanation(screeningId, eye, selectedTargetClass);
        if (!active) return;

        if (expl) {
          setFetchedExplanation(expl);
          if (onExplanationUpdateRef.current) {
            onExplanationUpdateRef.current(expl);
          }

          if (expl.status === 'completed' && expl.has_overlay) {
            const [oUrl, hUrl] = await Promise.all([
              clinicalWorkflowApi.fetchExplanationImageBlobUrl(screeningId, eye, 'overlay', selectedTargetClass),
              clinicalWorkflowApi.fetchExplanationImageBlobUrl(screeningId, eye, 'heatmap', selectedTargetClass),
            ]);
            if (!active) return;
            prevBlobUrlsRef.current = { overlay: oUrl, heatmap: hUrl };
            setOverlayBlobUrl(oUrl);
            setHeatmapBlobUrl(hUrl);
          } else if (expl.status === 'unavailable_ungradable') {
            setArtifactError('Grad-CAM explainability is not available because the retinal scan failed quality grading.');
          } else {
            setArtifactError('Explanation generation incomplete for this target class.');
          }
        } else {
          setOverlayBlobUrl(null);
          setHeatmapBlobUrl(null);
          setArtifactError('No explanation artifact generated for this class yet. Click "Generate Grad-CAM" to produce one.');
        }
      } catch (err) {
        if (!active) return;
        setOverlayBlobUrl(null);
        setHeatmapBlobUrl(null);
        setArtifactError(err instanceof Error ? err.message : 'Unable to load Grad-CAM explanation artifacts.');
      } finally {
        if (active) setLoadingArtifacts(false);
      }
    };

    loadArtifacts();

    return () => {
      active = false;
    };
  }, [screeningId, eye, selectedTargetClass, gradable]);

  // Handle on-demand explanation generation for the selected class
  const handleRegenerate = async (targetClassToGen: number) => {
    if (isRegenerating || !screeningId) return;
    setIsRegenerating(true);
    setArtifactError(null);

    try {
      const updatedExpl = await clinicalWorkflowApi.regenerateExplanation(screeningId, eye, targetClassToGen);
      setFetchedExplanation(updatedExpl);
      if (onExplanationUpdate) {
        onExplanationUpdate(updatedExpl);
      }

      if (updatedExpl.has_overlay) {
        const [oUrl, hUrl] = await Promise.all([
          clinicalWorkflowApi.fetchExplanationImageBlobUrl(screeningId, eye, 'overlay', targetClassToGen),
          clinicalWorkflowApi.fetchExplanationImageBlobUrl(screeningId, eye, 'heatmap', targetClassToGen),
        ]);
        if (prevBlobUrlsRef.current.overlay) URL.revokeObjectURL(prevBlobUrlsRef.current.overlay);
        if (prevBlobUrlsRef.current.heatmap) URL.revokeObjectURL(prevBlobUrlsRef.current.heatmap);
        prevBlobUrlsRef.current = { overlay: oUrl, heatmap: hUrl };
        setOverlayBlobUrl(oUrl);
        setHeatmapBlobUrl(hUrl);
      }
    } catch (err) {
      setArtifactError(err instanceof Error ? err.message : 'Failed to generate Grad-CAM explanation.');
    } finally {
      setIsRegenerating(false);
    }
  };

  const handleDownload = () => {
    const downloadSrc = activeMode === 'HEATMAP' ? heatmapBlobUrl : (overlayBlobUrl || effectiveImageSrc);
    if (!downloadSrc) return;

    const link = document.createElement('a');
    link.href = downloadSrc;
    const kind = activeMode === 'HEATMAP' ? 'heatmap' : (activeMode === 'ORIGINAL' ? 'original' : 'gradcam_overlay');
    link.download = `RETIVUE_${screeningId.slice(0, 8)}_${eye}_${kind}_class${selectedTargetClass}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.round(((e.clientX - rect.left) / rect.width) * 100);
    const y = Math.round(((e.clientY - rect.top) / rect.height) * 100);
    setCursorPos({ x, y });
  };

  if (!effectiveImageSrc && !loadingArtifacts) {
    return (
      <div className={`flex flex-col items-center justify-center bg-[#0d0e11] border border-[#262a30] rounded-2xl p-12 text-center text-[#8e9298] ${className}`}>
        <Eye size={36} className="text-[#6f7d3e] opacity-60 mb-3" />
        <p className="text-sm font-serif text-[#edebe1]">No Retinal Image Available for {eye === 'OD' ? 'Right Eye (OD)' : 'Left Eye (OS)'}</p>
        <p className="text-xs text-[#8e9298] mt-1 max-w-sm">Upload a valid fundus image to view original scan and Grad-CAM explainability.</p>
      </div>
    );
  }

  return (
    <div className={`relative flex flex-col bg-[#050506] border border-[#262a30] rounded-2xl overflow-hidden shadow-2xl select-none ${className}`}>
      {/* 1. Clinical Telemetry Bar */}
      <div className="flex flex-wrap items-center justify-between px-4 py-2.5 bg-[#0d0e11] border-b border-[#262a30] text-xs font-mono gap-2">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#1c1f24] text-[#f4f5f6] font-semibold border border-[#262a30]">
            <span className={`w-2 h-2 rounded-full ${gradable ? 'bg-emerald-400' : 'bg-rose-400'} animate-pulse`} />
            {eye === 'OD' ? 'RIGHT EYE (OD)' : 'LEFT EYE (OS)'}
          </span>
          {patientRef && <span className="text-[#8e9298] hidden sm:inline">REF: {patientRef}</span>}
          {predictedGrade !== null && predictedGrade !== undefined && (
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#4a5320]/40 text-[#dee9a6] border border-[#4a5320]">
              PREDICTED: {predictedLabel?.replace(/_/g, ' ') || `Grade ${predictedGrade}`}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 text-[#8e9298]">
          <span className="hidden md:inline text-[11px]">
            {cursorPos ? `COORD: ${cursorPos.x}%, ${cursorPos.y}%` : 'COORD: --%, --%'}
          </span>
          <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-[#1c1f24] border border-[#262a30] text-[#dee9a6]">
            {activeMode === 'SPLIT' ? 'SIDE-BY-SIDE' : activeMode}
          </span>
        </div>
      </div>

      {/* 2. Target Class Explanatory Selector */}
      <div className="px-4 py-2 bg-[#0a0b0e] border-b border-[#262a30] flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-[#8e9298] flex items-center gap-1">
            <Sparkles size={12} className="text-[#dee9a6]" />
            Target Class:
          </span>
          <div className="inline-flex rounded-lg bg-[#14161a] p-0.5 border border-[#262a30]">
            {DR_CLASSES.map((cls) => {
              const isSelected = selectedTargetClass === cls.grade;
              const isPredicted = predictedGrade === cls.grade;
              const probVal = probabilities[`class_${cls.grade}_${cls.label.toLowerCase().replace(/ /g, '_')}`] ??
                probabilities[Object.keys(probabilities).find(k => k.startsWith(`class_${cls.grade}`)) || ''];
              const pct = probVal !== undefined ? (probVal * 100).toFixed(0) : null;

              return (
                <button
                  key={cls.grade}
                  type="button"
                  onClick={() => {
                    setCustomTargetClass(cls.grade);
                  }}
                  className={`px-2.5 py-1 text-[11px] font-mono rounded transition-all cursor-pointer flex items-center gap-1 ${
                    isSelected
                      ? 'bg-[#4a5320] text-white font-bold shadow-xs'
                      : 'text-[#8e9298] hover:text-[#f4f5f6] hover:bg-[#1f2329]'
                  }`}
                  title={`${cls.fullName}${pct !== null ? ` (${pct}%)` : ''}`}
                >
                  <span>{cls.label}</span>
                  {pct !== null && (
                    <span className={`text-[9px] px-1 rounded ${isSelected ? 'bg-black/30 text-white' : 'text-[#8e9298]'}`}>
                      {pct}%
                    </span>
                  )}
                  {isPredicted && (
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" title="Model's Predicted Class" />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Regenerate or Status indicator */}
        <div className="flex items-center gap-2">
          {loadingArtifacts && (
            <span className="flex items-center gap-1.5 text-[11px] text-[#dee9a6] font-mono">
              <Loader2 size={12} className="animate-spin" />
              Loading Grad-CAM...
            </span>
          )}

          {!loadingArtifacts && (!overlayBlobUrl || !currentExplanation || currentExplanation.target_class !== selectedTargetClass) && gradable && (
            <button
              type="button"
              onClick={() => handleRegenerate(selectedTargetClass)}
              disabled={isRegenerating}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-[#262a30] hover:bg-[#343a42] text-xs font-mono text-[#f4f5f6] rounded border border-[#3e444e] transition-colors cursor-pointer disabled:opacity-50"
            >
              {isRegenerating ? (
                <>
                  <Loader2 size={11} className="animate-spin text-[#dee9a6]" />
                  <span>Computing...</span>
                </>
              ) : (
                <>
                  <Sparkles size={11} className="text-[#dee9a6]" />
                  <span>Generate Class {selectedTargetClass} CAM</span>
                </>
              )}
            </button>
          )}

          {overlayBlobUrl && (
            <button
              type="button"
              onClick={handleDownload}
              className="inline-flex items-center gap-1 px-2.5 py-1 bg-[#1c1f24] hover:bg-[#262a30] text-[11px] font-mono text-[#8e9298] hover:text-[#f4f5f6] rounded border border-[#262a30] transition-colors cursor-pointer"
              title="Download Artifact"
            >
              <Download size={11} />
              <span>Export</span>
            </button>
          )}
        </div>
      </div>

      {/* 3. Retinal Viewport */}
      <div
        className="relative aspect-square max-h-[540px] w-full flex items-center justify-center bg-[#050506] overflow-hidden select-none cursor-crosshair"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setCursorPos(null)}
      >
        {!gradable ? (
          <div className="p-8 text-center space-y-2 max-w-md">
            <AlertCircle size={32} className="text-amber-400 mx-auto opacity-80" />
            <h4 className="text-sm font-serif font-bold text-amber-200">Quality Ungradable</h4>
            <p className="text-xs text-[#8e9298]">
              {qualityReason || 'Image quality did not pass automated clarity/gradability checks. Grad-CAM generation is suppressed.'}
            </p>
          </div>
        ) : activeMode === 'SPLIT' ? (
          // Side-by-Side Split View
          <div
            className="w-full h-full grid grid-cols-2 gap-1 p-2 transition-transform duration-200"
            style={{ transform: `scale(${zoomLevel})` }}
          >
            <div className="relative w-full h-full flex flex-col items-center justify-center bg-black rounded-lg overflow-hidden border border-[#262a30]">
              <span className="absolute top-2 left-2 z-10 px-2 py-0.5 rounded bg-black/75 text-[10px] font-mono text-white border border-white/20">
                ORIGINAL SCAN
              </span>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={effectiveImageSrc || ''} alt="Original Fundus" className="w-full h-full object-contain pointer-events-none" />
            </div>

            <div className="relative w-full h-full flex flex-col items-center justify-center bg-black rounded-lg overflow-hidden border border-[#262a30]">
              <span className="absolute top-2 left-2 z-10 px-2 py-0.5 rounded bg-black/75 text-[10px] font-mono text-[#dee9a6] border border-[#dee9a6]/30">
                GRAD-CAM OVERLAY (CLASS {selectedTargetClass})
              </span>
              {overlayBlobUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={overlayBlobUrl} alt="Grad-CAM Overlay" className="w-full h-full object-contain pointer-events-none" />
              ) : (
                <div className="text-xs text-[#8e9298] flex items-center justify-center gap-1.5">
                  {loadingArtifacts ? <Loader2 size={14} className="animate-spin text-[#dee9a6]" /> : <span>Overlay unavailable</span>}
                </div>
              )}
            </div>
          </div>
        ) : (
          // Single Viewport (ORIGINAL / OVERLAY / HEATMAP)
          <div
            className="relative w-full h-full flex items-center justify-center transition-transform duration-200"
            style={{ transform: `scale(${zoomLevel})` }}
          >
            {/* Base Image: Original Retinal Scan */}
            {(activeMode === 'ORIGINAL' || activeMode === 'OVERLAY' || (activeMode === 'HEATMAP' && !heatmapBlobUrl)) && effectiveImageSrc && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={effectiveImageSrc}
                alt="Retinal Fundus Scan"
                className="w-full h-full object-contain pointer-events-none"
              />
            )}

            {/* Pure Transparent Heatmap Layer */}
            {activeMode === 'HEATMAP' && heatmapBlobUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={heatmapBlobUrl}
                alt="Grad-CAM Heatmap"
                className="w-full h-full object-contain pointer-events-none"
              />
            )}

            {/* Blended Grad-CAM Heatmap Layer on top of Base */}
            {activeMode === 'OVERLAY' && heatmapBlobUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={heatmapBlobUrl}
                alt="Grad-CAM Transparent Heatmap Layer"
                style={{ opacity: opacity / 100 }}
                className="absolute inset-0 w-full h-full object-contain pointer-events-none transition-opacity duration-150"
              />
            )}

            {/* Fallback pre-rendered overlay if heatmap layer not separate */}
            {activeMode === 'OVERLAY' && !heatmapBlobUrl && overlayBlobUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={overlayBlobUrl}
                alt="Grad-CAM Overlay"
                style={{ opacity: opacity / 100 }}
                className="absolute inset-0 w-full h-full object-contain pointer-events-none transition-opacity duration-150"
              />
            )}

            {/* Loading Indicator */}
            {loadingArtifacts && !overlayBlobUrl && (
              <div className="absolute inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center">
                <div className="bg-[#0d0e11]/90 border border-[#262a30] rounded-xl px-4 py-3 flex items-center gap-2.5 text-xs font-mono text-[#f4f5f6]">
                  <Loader2 size={16} className="animate-spin text-[#dee9a6]" />
                  <span>Loading Grad-CAM features...</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Viewport Floating Zoom Controls */}
        <div className="absolute bottom-3 right-3 flex items-center gap-1 bg-[#0d0e11]/90 border border-[#262a30] rounded-lg p-1 backdrop-blur-sm z-20">
          <button
            type="button"
            onClick={() => setZoomLevel((z) => Math.min(z + 0.25, 2.5))}
            className="p-1.5 text-[#8e9298] hover:text-[#f4f5f6] hover:bg-[#1c1f24] rounded transition-colors cursor-pointer"
            title="Zoom In"
            aria-label="Zoom In"
          >
            <ZoomIn size={14} />
          </button>
          <span className="text-[11px] font-mono text-[#8e9298] px-1.5 select-none">
            {Math.round(zoomLevel * 100)}%
          </span>
          <button
            type="button"
            onClick={() => setZoomLevel((z) => Math.max(z - 0.25, 0.75))}
            className="p-1.5 text-[#8e9298] hover:text-[#f4f5f6] hover:bg-[#1c1f24] rounded transition-colors cursor-pointer"
            title="Zoom Out"
            aria-label="Zoom Out"
          >
            <ZoomOut size={14} />
          </button>
          <button
            type="button"
            onClick={() => setZoomLevel(1)}
            className="p-1.5 text-[#8e9298] hover:text-[#f4f5f6] hover:bg-[#1c1f24] rounded transition-colors cursor-pointer"
            title="Reset Zoom"
            aria-label="Reset Zoom"
          >
            <RotateCcw size={13} />
          </button>
        </div>
      </div>

      {/* 4. Bottom Controls: Mode Tabs & Opacity Slider */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 bg-[#0d0e11] border-t border-[#262a30]">
        {/* Mode Tabs */}
        <div className="inline-flex p-1 rounded-lg bg-[#14161a] border border-[#262a30] text-xs font-medium">
          <button
            type="button"
            onClick={() => setActiveMode('ORIGINAL')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all cursor-pointer ${
              activeMode === 'ORIGINAL'
                ? 'bg-[#4a5320] text-white shadow-sm font-semibold'
                : 'text-[#8e9298] hover:text-[#f4f5f6]'
            }`}
          >
            <Eye size={13} />
            <span>Original Scan</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveMode('OVERLAY')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all cursor-pointer ${
              activeMode === 'OVERLAY'
                ? 'bg-[#4a5320] text-white shadow-sm font-semibold'
                : 'text-[#8e9298] hover:text-[#f4f5f6]'
            }`}
          >
            <Layers size={13} />
            <span>Grad-CAM Overlay</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveMode('HEATMAP')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all cursor-pointer ${
              activeMode === 'HEATMAP'
                ? 'bg-[#4a5320] text-white shadow-sm font-semibold'
                : 'text-[#8e9298] hover:text-[#f4f5f6]'
            }`}
          >
            <Sparkles size={13} />
            <span>Pure Heatmap</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveMode('SPLIT')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all cursor-pointer ${
              activeMode === 'SPLIT'
                ? 'bg-[#4a5320] text-white shadow-sm font-semibold'
                : 'text-[#8e9298] hover:text-[#f4f5f6]'
            }`}
          >
            <Columns size={13} />
            <span>Side-by-Side</span>
          </button>
        </div>

        {/* Heatmap Opacity Slider (visible in Overlay mode) */}
        {activeMode === 'OVERLAY' && (
          <div className="flex items-center gap-2.5 text-xs font-mono text-[#8e9298]">
            <span className="text-[11px]">Heatmap Opacity:</span>
            <input
              type="range"
              min={10}
              max={100}
              step={5}
              value={opacity}
              onChange={(e) => setOpacity(Number(e.target.value))}
              className="w-24 accent-[#dee9a6] cursor-pointer"
            />
            <span className="w-8 text-right font-bold text-[#f4f5f6]">{opacity}%</span>
          </div>
        )}
      </div>

      {/* 5. Clinical Safety & Provenance Footer Banner */}
      <div className="px-4 py-2 bg-[#090a0d] border-t border-[#1c1f24] text-[10px] text-[#8e9298] flex items-center justify-between gap-3">
        <div className="flex items-center gap-1.5 leading-snug">
          <Info size={12} className="text-[#6f7d3e] shrink-0" />
          <span>
            <strong>Clinical Safety:</strong> Grad-CAM highlights convolutional feature attention (layer <code>{currentExplanation?.model_layer || 'features[8]'}</code>), not biological lesion segmentations. Independent clinician confirmation is mandatory.
          </span>
        </div>
        {currentExplanation?.checkpoint_sha256 && (
          <span className="font-mono text-[#7a7d72] shrink-0 hidden md:inline">
            SHA: {currentExplanation.checkpoint_sha256.slice(0, 10)}...
          </span>
        )}
      </div>

      {artifactError && (
        <div className="px-4 py-1.5 bg-amber-950/40 border-t border-amber-900/50 text-[11px] text-amber-200/90 font-mono flex items-center gap-2">
          <AlertCircle size={12} className="text-amber-400 shrink-0" />
          <span>{artifactError}</span>
        </div>
      )}
    </div>
  );
}

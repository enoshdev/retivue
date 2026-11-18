export * from './clinical';

// Backwards compatibility types
export type ScreeningStatus =
  | 'NON_REFERABLE'
  | 'REFERABLE_DR'
  | 'REQUIRES_RECAPTURE'
  | 'PENDING_REVIEW'
  | 'WAITING_ANALYSIS';

export interface ExplainabilityData {
  primaryAttributionRegion: string;
  fovealZoneInvolved: boolean;
  evidenceSummary: string;
  modelArchitecture: string;
  receptiveFieldResolution: string;
}

export interface ScreeningRecord {
  id: string;
  patientRef?: string;
  patientAge?: number;
  patientGender?: 'Male' | 'Female' | 'Other';
  eye: 'OD' | 'OS';
  screeningDate: string;
  clinicName?: string;
  operatorName?: string;
  cameraModel?: string;
  rawImage: string;
  quality: import('./clinical').ImageQualityAssessment;
  grade?: import('./clinical').DRGrade;
  gradeLabel?: string;
  etdrsLevel?: number;
  confidence?: number;
  status: ScreeningStatus;
  lesions: import('./clinical').LesionFinding[];
  explainability?: ExplainabilityData;
  scenarioId?: 'demo-abnormal' | 'demo-normal';
  scenario?: unknown;
  referralRecommendation?: string;
  followUpWindow?: string;
  clinicalNotes?: string;
}

export type ExplainabilityMode = 'ORIGINAL' | 'ATTENTION' | 'EVIDENCE';

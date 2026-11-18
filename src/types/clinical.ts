export type UserRole = 'CLINICIAN' | 'USER' | 'INDEPENDENT_DOCTOR' | 'CLINIC_ADMIN' | 'TECHNICIAN';

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  facility?: string;
  registrationNumber?: string;
  avatarInitials: string;
}

export type EyeLaterality = 'OD' | 'OS';

export type ImageSuitability = 'WAITING' | 'SUITABLE' | 'NEEDS_IMPROVEMENT' | 'UNGRADEABLE';

export type DRGrade = 'NO_DR' | 'MILD_NPDR' | 'MODERATE_NPDR' | 'SEVERE_NPDR' | 'PDR' | 'PENDING';

export type ScreeningCaseStatus =
  | 'AWAITING_UPLOAD'
  | 'QUALITY_CHECK'
  | 'AWAITING_REVIEW'
  | 'REVIEWED'
  | 'REFERRED'
  | 'RECAPTURE_REQUIRED';

export type CaseUrgency = 'ROUTINE' | 'ELEVATED' | 'URGENT';

export type ReferralUrgency = 'IMMEDIATE_48H' | 'WITHIN_2_WEEKS' | 'STANDARD_SURVEILLANCE';

export type ReferralStatus = 'DISPATCHED' | 'ACCEPTED' | 'APPOINTMENT_SCHEDULED' | 'COMPLETED';

export type FollowUpWindow =
  | 'URGENT_SPECIALIST'
  | 'THREE_MONTHS'
  | 'SIX_MONTHS'
  | 'TWELVE_MONTHS'
  | 'NO_REFERRAL';

export interface QualityMetric {
  name: string;
  status: 'OPTIMAL' | 'ACCEPTABLE' | 'DEGRADED' | 'PENDING';
  detail: string;
}

export interface ImageQualityAssessment {
  overallSuitability: ImageSuitability;
  focus: QualityMetric;
  illumination: QualityMetric;
  fieldOfView: QualityMetric;
  mediaOpacity: QualityMetric;
  artifactsDetected: string[];
  reasons: string[];
  recommendation: string;
}

export interface LesionFinding {
  id: string;
  type:
    | 'MICROANEURYSM'
    | 'HEMORRHAGE'
    | 'HARD_EXUDATE'
    | 'COTTON_WOOL_SPOT'
    | 'VENOUS_BEADING'
    | 'NEOVASCULARIZATION';
  label: string;
  count: number;
  density: 'LOW' | 'MODERATE' | 'HIGH';
  quadrant: string;
  clinicalSignificance: string;
  etdrsCriterion: string;
}

export interface EyeImageDetail {
  eye: EyeLaterality;
  eyeLabel: string; // 'Right Eye (OD)' or 'Left Eye (OS)'
  imageUrl: string;
  filename: string;
  uploadStatus: 'UPLOADED' | 'EMPTY' | 'FAILED';
  fileSize?: string;
  quality: ImageQualityAssessment;
  lesions?: LesionFinding[];
  aiSuggestedGrade?: DRGrade;
  aiGradeLabel?: string;
  aiConfidence?: string;
  aiEvidenceSummary?: string;
  explainabilityImageUrl?: string;
  enhancedImageUrl?: string;
  structuresIdentified?: string[];
}

export interface PatientRecord {
  id: string; // e.g. "PT-9428-103B"
  mrn: string; // "MRN-084-291"
  fullName: string;
  age: number;
  gender: 'Male' | 'Female' | 'Other';
  contactNumber: string;
  diabetesType: 'Type 1' | 'Type 2' | 'Gestational' | 'Unknown';
  diabetesDurationYears: number;
  recentHbA1c?: string;
  consentGiven: boolean;
  consentStatus?: string;
  consentDate: string;
  registeredAt: string;
  registeredBy: string;
  clinicId?: string;
  clinicName?: string;
  screeningCount: number;
  lastScreeningDate?: string;
  lastScreeningStatus?: ScreeningCaseStatus;
  notes?: string;
}

export interface ClinicalAdjudication {
  doctorName: string;
  doctorRegistrationNumber: string;
  decision: 'ACCEPTED' | 'OVERRIDDEN' | 'PENDING';
  confirmedGrade: DRGrade;
  overrideRationale?: string;
  findings: {
    csmeSuspected: boolean;
    venousBeading: boolean;
    irma: boolean;
    macularInvolvementClearOfFAZ: boolean;
    vitreoretinalSurgeryConsultIndicated: boolean;
  };
  referralWindow: FollowUpWindow;
  clinicalNotes: string;
  signedAt?: string;
  isDraft: boolean;
}

export interface OverallAiSuggestion {
  icdrGrade: DRGrade;
  icdrLabel: string;
  etdrsLevel: number;
  isReferable: boolean;
  confidencePercent: number;
  confidenceInterval: string;
  modelVersion: string;
  regulatoryNotice: string;
}

export interface ScreeningCase {
  id: string; // e.g. "RV-2026-0042"
  patientId: string;
  patient: PatientRecord;
  screeningDate: string;
  clinicId?: string;
  clinicName?: string;
  technicianName?: string;
  assignedDoctorName?: string;
  cameraModel: string;
  status: ScreeningCaseStatus;
  urgency: CaseUrgency;
  odEye?: EyeImageDetail;
  osEye?: EyeImageDetail;
  overallAiSuggestion?: OverallAiSuggestion;
  adjudication?: ClinicalAdjudication;
}

export interface StaffMember {
  id: string;
  fullName: string;
  email: string;
  role: 'OPHTHALMOLOGIST' | 'CLINIC_ADMIN' | 'VISION_TECHNICIAN';
  status: 'ACTIVE' | 'INVITED' | 'INACTIVE';
  assignedFacility: string;
  licenseOrRegistration?: string;
  activeCasesCount: number;
  joinedDate: string;
}

export interface ReferralRecord {
  id: string;
  caseId: string;
  patientId: string;
  patientName: string;
  referringDoctor: string;
  targetFacility: string;
  referralDate: string;
  urgency: ReferralUrgency;
  indication: string;
  status: ReferralStatus;
  notes?: string;
}


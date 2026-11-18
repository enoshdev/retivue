import { ImageQualityAssessment, DRGrade } from '@/types/screening';

export interface EyeAnalysisOutput {
  eye: 'OS' | 'OD'; // OS = Left Eye, OD = Right Eye
  eyeLabel: string; // 'Left Eye (OS)' or 'Right Eye (OD)'
  originalImage: string;
  enhancedImage: string;
  structureImage: string;
  explainabilityImage: string;
  filename: string;
  fileSize: string;
  uploadStatus: 'UPLOADED' | 'PENDING';
  quality: ImageQualityAssessment;
  grade: DRGrade;
  gradeLabel: string;
  etdrsLevel: number;
  severityLabel: string;
  screeningResult: string;
  resultType: 'ABNORMAL' | 'NORMAL';
  evidenceList: string[];
  aiSummary: string;
  whyThisResult: string;
  confidenceScore: string;
  structuresIdentified: string[];
  fovealZoneInvolved: boolean;
  primaryAttributionRegion: string;
}

export interface DemoScreeningScenario {
  id: string;
  accountId: 'demo-abnormal' | 'demo-normal';
  accountTitle: string;
  patientName: string;
  patientAge: number;
  screeningDate: string;
  datasetSource: string;
  clinicName: string;
  operatorName: string;
  cameraModel: string;
  overallStatus: 'REQUIRES_PROFESSIONAL_REVIEW' | 'ROUTINE_PERIODIC_SCREENING';
  overallStatusLabel: string;
  overallSummary: string;
  leftEye: EyeAnalysisOutput;
  rightEye: EyeAnalysisOutput;
}

// Visual asset references (utilizing high-resolution medical vector fundus models)
export const RETINA_ASSETS = {
  // Demo Patient A (Left eye abnormal, Right eye normal)
  patientA: {
    left: {
      original: '/retina-moderate-npdr.svg',
      enhanced: '/retina-enhanced-abnormal.svg',
      structure: '/retina-structure-abnormal.svg',
      explainability: '/retina-explainability-abnormal.svg',
    },
    right: {
      original: '/retina-normal.svg',
      enhanced: '/retina-enhanced-normal.svg',
      structure: '/retina-structure-normal.svg',
      explainability: '/retina-explainability-normal.svg',
    },
  },
  // Demo Patient B (Both eyes no abnormality)
  patientB: {
    left: {
      original: '/retina-normal.svg',
      enhanced: '/retina-enhanced-normal.svg',
      structure: '/retina-structure-normal.svg',
      explainability: '/retina-explainability-normal.svg',
    },
    right: {
      original: '/retina-normal.svg',
      enhanced: '/retina-enhanced-normal.svg',
      structure: '/retina-structure-normal.svg',
      explainability: '/retina-explainability-normal.svg',
    },
  },
};

export const DEMO_SCENARIO_ABNORMAL: DemoScreeningScenario = {
  id: 'RV-DEMO-001',
  accountId: 'demo-abnormal',
  accountTitle: 'Demo Account 01 — Abnormal Screening',
  patientName: 'Demo Patient A',
  patientAge: 58,
  screeningDate: '2026-09-26T09:30:00Z',
  datasetSource: 'Messidor-2 & DDR Public Benchmark (Simulated Demo Attribution)',
  clinicName: 'District Community Screening Station #04',
  operatorName: 'Clinical Vision Technician R. Sharma',
  cameraModel: 'Non-Mydriatic 45° Fundus Camera (ISO 10940 Compliant)',
  overallStatus: 'REQUIRES_PROFESSIONAL_REVIEW',
  overallStatusLabel: 'Requires Professional Review',
  overallSummary:
    'Simulated screening identifies localized microvascular abnormalities consistent with Moderate NPDR (Level 2) in the left eye, and no significant abnormalities in the right eye. Prompt stereoscopic evaluation and ophthalmological triage recommended.',
  leftEye: {
    eye: 'OS',
    eyeLabel: 'Left Eye (OS)',
    originalImage: RETINA_ASSETS.patientA.left.original,
    enhancedImage: RETINA_ASSETS.patientA.left.enhanced,
    structureImage: RETINA_ASSETS.patientA.left.structure,
    explainabilityImage: RETINA_ASSETS.patientA.left.explainability,
    filename: 'demo_patient_a_left_eye.jpg',
    fileSize: '3.4 MB',
    uploadStatus: 'UPLOADED',
    quality: {
      overallSuitability: 'SUITABLE',
      focus: { name: 'Focus', status: 'OPTIMAL', detail: 'Sharp vessel bifurcations and disc margin' },
      illumination: { name: 'Illumination', status: 'OPTIMAL', detail: 'Uniform 45° non-mydriatic illumination' },
      fieldOfView: { name: 'Field of View', status: 'OPTIMAL', detail: 'Optic disc and fovea encompassed' },
      mediaOpacity: { name: 'Media Opacity', status: 'OPTIMAL', detail: 'Clear optical media without corneal haze' },
      artifactsDetected: [],
      reasons: ['Image is suitable for diabetic retinopathy screening'],
      recommendation: 'Image quality meets ISO 10940 standards for automated pre-screening.',
    },
    grade: 'MODERATE_NPDR',
    gradeLabel: 'Moderate Non-Proliferative Diabetic Retinopathy',
    etdrsLevel: 2,
    severityLabel: 'Moderate NPDR / Level 2',
    screeningResult: 'Abnormal retinal findings detected',
    resultType: 'ABNORMAL',
    evidenceList: [
      'Microaneurysm-like evidence (18 localized clusters)',
      'Small hemorrhage-like regions (temporal blot hemorrhages)',
      'Retinal vascular changes (venular tortuosity along superior/inferior arcades)',
      'Hard lipid exudate rings outside immediate foveal center',
    ],
    aiSummary:
      'The simulated analysis identifies localized retinal regions that correspond to lesion-like evidence. These areas contributed to the screening classification and are highlighted in the explainability view.',
    whyThisResult:
      'The simulated model output is influenced by localized lesion-like regions visible in the evidence map, together with the overall retinal appearance.',
    confidenceScore: '92.4% (Simulated confidence)',
    structuresIdentified: [
      'Optic disc margin and physiological cup',
      'Superior & inferior temporal vascular arcades',
      'Macular zone and foveal reflex',
      'Focal microaneurysm clusters (quadrants II and III)',
    ],
    fovealZoneInvolved: false,
    primaryAttributionRegion: 'Superior & inferior temporal arcades, posterior pole',
  },
  rightEye: {
    eye: 'OD',
    eyeLabel: 'Right Eye (OD)',
    originalImage: RETINA_ASSETS.patientA.right.original,
    enhancedImage: RETINA_ASSETS.patientA.right.enhanced,
    structureImage: RETINA_ASSETS.patientA.right.structure,
    explainabilityImage: RETINA_ASSETS.patientA.right.explainability,
    filename: 'demo_patient_a_right_eye.jpg',
    fileSize: '3.1 MB',
    uploadStatus: 'UPLOADED',
    quality: {
      overallSuitability: 'SUITABLE',
      focus: { name: 'Focus', status: 'OPTIMAL', detail: 'Sharp vessel arborization' },
      illumination: { name: 'Illumination', status: 'OPTIMAL', detail: 'Uniform exposure across macula' },
      fieldOfView: { name: 'Field of View', status: 'OPTIMAL', detail: 'Full 45° posterior pole capture' },
      mediaOpacity: { name: 'Media Opacity', status: 'OPTIMAL', detail: 'Unobstructed fundus view' },
      artifactsDetected: [],
      reasons: ['Image is suitable for diabetic retinopathy screening'],
      recommendation: 'Image quality is optimal for screening.',
    },
    grade: 'NO_DR',
    gradeLabel: 'No Diabetic Retinopathy Detected',
    etdrsLevel: 0,
    severityLabel: 'Level 0 (No DR Detected)',
    screeningResult: 'No significant abnormality detected',
    resultType: 'NORMAL',
    evidenceList: [
      'Normal retinal vascular branching and caliber',
      'Preserved physiological cup-to-disc ratio (0.35)',
      'No significant microvascular lesions detected in the analyzed image',
    ],
    aiSummary:
      'The simulated screening workflow did not identify significant lesion-like evidence associated with diabetic retinopathy in the analyzed right eye image.',
    whyThisResult:
      'The simulated analysis did not identify significant lesion-like regions and produced a low-evidence screening result.',
    confidenceScore: '96.8% (Simulated confidence)',
    structuresIdentified: [
      'Optic nerve head and neuroretinal rim',
      'Normal arteriolar-to-venular ratio (2:3)',
      'Clear foveal avascular zone',
      'Uniform background pigmentary luminance',
    ],
    fovealZoneInvolved: false,
    primaryAttributionRegion: 'Diffuse baseline retinal background',
  },
};

export const DEMO_SCENARIO_NORMAL: DemoScreeningScenario = {
  id: 'RV-DEMO-002',
  accountId: 'demo-normal',
  accountTitle: 'Demo Account 02 — No Detected Abnormality',
  patientName: 'Demo Patient B',
  patientAge: 46,
  screeningDate: '2026-09-26T08:45:00Z',
  datasetSource: 'IDRiD & Kaggle EyePACS Benchmark (Simulated Demo Attribution)',
  clinicName: 'Mobile Screening Van Alpha-2',
  operatorName: 'Health Worker A. Patel',
  cameraModel: 'Portable Handheld Non-Mydriatic Fundus Scope',
  overallStatus: 'ROUTINE_PERIODIC_SCREENING',
  overallStatusLabel: 'Routine Periodic Screening',
  overallSummary:
    'No diabetic-retinopathy-related abnormality detected in this simulated screening for either eye. Patient should maintain routine glycemic monitoring and schedule annual periodic screening as recommended by community protocol.',
  leftEye: {
    eye: 'OS',
    eyeLabel: 'Left Eye (OS)',
    originalImage: RETINA_ASSETS.patientB.left.original,
    enhancedImage: RETINA_ASSETS.patientB.left.enhanced,
    structureImage: RETINA_ASSETS.patientB.left.structure,
    explainabilityImage: RETINA_ASSETS.patientB.left.explainability,
    filename: 'demo_patient_b_left_eye.jpg',
    fileSize: '3.2 MB',
    uploadStatus: 'UPLOADED',
    quality: {
      overallSuitability: 'SUITABLE',
      focus: { name: 'Focus', status: 'OPTIMAL', detail: 'Crisp microvascular details' },
      illumination: { name: 'Illumination', status: 'OPTIMAL', detail: 'Even lighting without pupillary shadow' },
      fieldOfView: { name: 'Field of View', status: 'OPTIMAL', detail: 'Adequate nasal and temporal coverage' },
      mediaOpacity: { name: 'Media Opacity', status: 'OPTIMAL', detail: 'Clear ocular media' },
      artifactsDetected: [],
      reasons: ['Image is suitable for diabetic retinopathy screening'],
      recommendation: 'Image is suitable for screening.',
    },
    grade: 'NO_DR',
    gradeLabel: 'No Diabetic Retinopathy Detected',
    etdrsLevel: 0,
    severityLabel: 'Level 0 (No DR Detected)',
    screeningResult: 'No diabetic-retinopathy-related abnormality detected in this simulated screening',
    resultType: 'NORMAL',
    evidenceList: [
      'Normal retinal vascular architecture and caliber',
      'Distinct optic disc margin and cup-to-disc ratio (0.32)',
      'Clear macula and preserved foveal avascular zone',
      'No microaneurysms, hemorrhages, or exudates identified',
    ],
    aiSummary:
      'The simulated screening workflow did not identify significant lesion-like evidence associated with diabetic retinopathy in the analyzed image.',
    whyThisResult:
      'The simulated analysis did not identify significant lesion-like regions and produced a low-evidence screening result.',
    confidenceScore: '97.5% (Simulated confidence)',
    structuresIdentified: [
      'Optic disc rim and central retinal artery/vein',
      'Macular center and foveal light reflex',
      'Primary arcade bifurcation tree',
      'Uniform chorioretinal pigment epithelium',
    ],
    fovealZoneInvolved: false,
    primaryAttributionRegion: 'Diffuse baseline background (low activation)',
  },
  rightEye: {
    eye: 'OD',
    eyeLabel: 'Right Eye (OD)',
    originalImage: RETINA_ASSETS.patientB.right.original,
    enhancedImage: RETINA_ASSETS.patientB.right.enhanced,
    structureImage: RETINA_ASSETS.patientB.right.structure,
    explainabilityImage: RETINA_ASSETS.patientB.right.explainability,
    filename: 'demo_patient_b_right_eye.jpg',
    fileSize: '2.9 MB',
    uploadStatus: 'UPLOADED',
    quality: {
      overallSuitability: 'SUITABLE',
      focus: { name: 'Focus', status: 'OPTIMAL', detail: 'Sharp vessel bifurcation' },
      illumination: { name: 'Illumination', status: 'OPTIMAL', detail: 'Balanced luminance across aperture' },
      fieldOfView: { name: 'Field of View', status: 'OPTIMAL', detail: 'Centered 45° macular field' },
      mediaOpacity: { name: 'Media Opacity', status: 'OPTIMAL', detail: 'Completely clear optical pathway' },
      artifactsDetected: [],
      reasons: ['Image is suitable for diabetic retinopathy screening'],
      recommendation: 'Image is suitable for screening.',
    },
    grade: 'NO_DR',
    gradeLabel: 'No Diabetic Retinopathy Detected',
    etdrsLevel: 0,
    severityLabel: 'Level 0 (No DR Detected)',
    screeningResult: 'No diabetic-retinopathy-related abnormality detected in this simulated screening',
    resultType: 'NORMAL',
    evidenceList: [
      'Uniform vascular caliber across all four quadrants',
      'Absence of microaneurysm leakage or blot hemorrhages',
      'Sharp optic nerve margins and normal cup excavation',
      'Intact foveal depression without macular edema signs',
    ],
    aiSummary:
      'The simulated screening workflow did not identify significant lesion-like evidence associated with diabetic retinopathy in the analyzed image.',
    whyThisResult:
      'The simulated analysis did not identify significant lesion-like regions and produced a low-evidence screening result.',
    confidenceScore: '98.2% (Simulated confidence)',
    structuresIdentified: [
      'Optic nerve head and temporal neuroretinal margin',
      'Superior/inferior temporal vascular arcades',
      'Foveal avascular zone',
      'Peripheral retinal quadrants',
    ],
    fovealZoneInvolved: false,
    primaryAttributionRegion: 'Diffuse baseline background (low activation)',
  },
};

export const DEMO_SCENARIOS = {
  abnormal: DEMO_SCENARIO_ABNORMAL,
  normal: DEMO_SCENARIO_NORMAL,
};

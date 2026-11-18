import { mockScreenings } from '@/data/mockScreenings';
import {
  ScreeningRecord,
  ImageQualityAssessment,
} from '@/types/screening';
import {
  DemoScreeningScenario,
  DEMO_SCENARIO_ABNORMAL,
  DEMO_SCENARIO_NORMAL,
} from '@/data/demoScenarios';

// Live in-memory screening store for active session (initialized with controlled demo records)
let screeningsStore: ScreeningRecord[] = [...mockScreenings];

export const screeningService = {
  getAll: async (): Promise<ScreeningRecord[]> => {
    return [...screeningsStore];
  },

  getById: async (id: string): Promise<ScreeningRecord | null> => {
    const record = screeningsStore.find((s) => s.id === id);
    return record ? { ...record } : null;
  },

  getDemoScenario: (type: 'abnormal' | 'normal' | 'demo-abnormal' | 'demo-normal'): DemoScreeningScenario => {
    if (type === 'normal' || type === 'demo-normal') {
      return { ...DEMO_SCENARIO_NORMAL };
    }
    return { ...DEMO_SCENARIO_ABNORMAL };
  },

  search: async (
    query: string,
    gradeFilter?: string,
    statusFilter?: string
  ): Promise<ScreeningRecord[]> => {
    let results = [...screeningsStore];

    if (query.trim()) {
      const q = query.toLowerCase();
      results = results.filter(
        (s) =>
          s.id.toLowerCase().includes(q) ||
          (s.patientRef && s.patientRef.toLowerCase().includes(q)) ||
          (s.clinicName && s.clinicName.toLowerCase().includes(q)) ||
          (s.gradeLabel && s.gradeLabel.toLowerCase().includes(q))
      );
    }

    if (gradeFilter && gradeFilter !== 'ALL') {
      results = results.filter((s) => s.grade === gradeFilter);
    }

    if (statusFilter && statusFilter !== 'ALL') {
      results = results.filter((s) => s.status === statusFilter);
    }

    return results;
  },

  assessQuality: async (imageSource: string): Promise<ImageQualityAssessment> => {
    if (!imageSource) {
      return {
        overallSuitability: 'WAITING',
        focus: { name: 'Focus', status: 'PENDING', detail: 'Waiting for image upload' },
        illumination: { name: 'Illumination', status: 'PENDING', detail: 'Waiting for image upload' },
        fieldOfView: { name: 'Field of View', status: 'PENDING', detail: 'Waiting for image upload' },
        mediaOpacity: { name: 'Media Opacity', status: 'PENDING', detail: 'Waiting for image upload' },
        artifactsDetected: [],
        reasons: [],
        recommendation: 'Waiting for image analysis.',
      };
    }

    if (imageSource.includes('ungradeable')) {
      return {
        overallSuitability: 'UNGRADEABLE',
        focus: { name: 'Focus', status: 'DEGRADED', detail: 'Significant blur; vessel edges not resolvable' },
        illumination: { name: 'Illumination', status: 'DEGRADED', detail: 'Glare or illumination obstruction across field' },
        fieldOfView: { name: 'Field of View', status: 'DEGRADED', detail: 'Disc or macula clipped at margin' },
        mediaOpacity: { name: 'Media Opacity', status: 'DEGRADED', detail: 'Cataract or corneal haze detected' },
        artifactsDetected: ['Motion Blur', 'Pupillary Vignetting'],
        reasons: [
          'Image sharpness below minimum diagnostic threshold',
          'Key anatomical landmarks obscured',
        ],
        recommendation: 'A reliable screening result cannot be generated from this image. Recapture required.',
      };
    }

    // Suitable capture
    return {
      overallSuitability: 'SUITABLE',
      focus: { name: 'Focus', status: 'OPTIMAL', detail: 'Sharp vessel bifurcations clearly resolvable' },
      illumination: { name: 'Illumination', status: 'OPTIMAL', detail: 'Even luminance across diagnostic field' },
      fieldOfView: { name: 'Field of View', status: 'OPTIMAL', detail: 'Optic disc and macular center encompassed' },
      mediaOpacity: { name: 'Media Opacity', status: 'OPTIMAL', detail: 'Transparent optical media' },
      artifactsDetected: [],
      reasons: ['Image is suitable for diabetic retinopathy screening'],
      recommendation: 'Image is suitable for screening.',
    };
  },

  create: async (newRecord: Omit<ScreeningRecord, 'id' | 'screeningDate'>): Promise<ScreeningRecord> => {
    const id = `RET-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`;
    const record: ScreeningRecord = {
      ...newRecord,
      id,
      screeningDate: new Date().toISOString(),
    };
    screeningsStore = [record, ...screeningsStore];
    return record;
  },
};

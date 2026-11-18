'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';
import { ScreeningRecord, ImageQualityAssessment, EyeLaterality } from '@/types/screening';
import {
  DemoScreeningScenario,
  DEMO_SCENARIO_ABNORMAL,
  DEMO_SCENARIO_NORMAL,
} from '@/data/demoScenarios';
import { screeningService } from '@/services/screeningService';

interface ScreeningContextType {
  // Demo Scenario State
  activeScenario: DemoScreeningScenario;
  setActiveScenario: (scenario: DemoScreeningScenario) => void;
  switchDemoAccount: (accountId: 'demo-abnormal' | 'demo-normal') => void;

  // Dual Eye Upload State (Section 3 & 4)
  leftEyeImage: string;
  leftEyeFilename: string;
  leftEyeStatus: 'UPLOADED' | 'EMPTY';
  leftEyeQuality: ImageQualityAssessment | null;
  rightEyeImage: string;
  rightEyeFilename: string;
  rightEyeStatus: 'UPLOADED' | 'EMPTY';
  rightEyeQuality: ImageQualityAssessment | null;

  setLeftEye: (image: string, filename?: string) => void;
  setRightEye: (image: string, filename?: string) => void;
  clearLeftEye: () => void;
  clearRightEye: () => void;
  loadDemoPreset: (scenarioId: 'demo-abnormal' | 'demo-normal') => void;

  // Legacy & Active View helpers
  currentScreening: ScreeningRecord | null;
  setCurrentScreening: (record: ScreeningRecord | null) => void;
  activeImage: string;
  setActiveImage: (url: string) => void;
  patientRef: string;
  setPatientRef: (ref: string) => void;
  patientAge: string;
  setPatientAge: (age: string) => void;
  patientGender: 'Male' | 'Female' | 'Other' | '';
  setPatientGender: (gender: 'Male' | 'Female' | 'Other' | '') => void;
  eye: EyeLaterality;
  setEye: (eye: EyeLaterality) => void;
  cameraModel: string;
  setCameraModel: (model: string) => void;
  clinicName: string;
  setClinicName: (clinic: string) => void;
  operatorName: string;
  setOperatorName: (operator: string) => void;
  currentQuality: ImageQualityAssessment | null;
  setCurrentQuality: (q: ImageQualityAssessment | null) => void;

  // History & Actions
  allScreenings: ScreeningRecord[];
  refreshScreenings: () => Promise<void>;
  selectRecordById: (id: string) => void;
  resetFlow: () => void;
}

const ScreeningContext = createContext<ScreeningContextType | undefined>(undefined);

export function ScreeningProvider({ children }: { children: React.ReactNode }) {
  // Default to Demo Account 01 (Abnormal Screening) with full scenario available
  const [activeScenario, setActiveScenarioState] = useState<DemoScreeningScenario>(DEMO_SCENARIO_ABNORMAL);

  // Dual Eye state initialized with current active scenario images
  const [leftEyeImage, setLeftEyeImage] = useState<string>(DEMO_SCENARIO_ABNORMAL.leftEye.originalImage);
  const [leftEyeFilename, setLeftEyeFilename] = useState<string>(DEMO_SCENARIO_ABNORMAL.leftEye.filename);
  const [leftEyeStatus, setLeftEyeStatus] = useState<'UPLOADED' | 'EMPTY'>('UPLOADED');
  const [leftEyeQuality, setLeftEyeQuality] = useState<ImageQualityAssessment | null>(DEMO_SCENARIO_ABNORMAL.leftEye.quality);

  const [rightEyeImage, setRightEyeImage] = useState<string>(DEMO_SCENARIO_ABNORMAL.rightEye.originalImage);
  const [rightEyeFilename, setRightEyeFilename] = useState<string>(DEMO_SCENARIO_ABNORMAL.rightEye.filename);
  const [rightEyeStatus, setRightEyeStatus] = useState<'UPLOADED' | 'EMPTY'>('UPLOADED');
  const [rightEyeQuality, setRightEyeQuality] = useState<ImageQualityAssessment | null>(DEMO_SCENARIO_ABNORMAL.rightEye.quality);

  // Legacy single-eye compatibility
  const [currentScreening, setCurrentScreening] = useState<ScreeningRecord | null>(null);
  const [activeImage, setActiveImage] = useState<string>(DEMO_SCENARIO_ABNORMAL.leftEye.originalImage);
  const [patientRef, setPatientRef] = useState<string>(DEMO_SCENARIO_ABNORMAL.patientName);
  const [patientAge, setPatientAge] = useState<string>(String(DEMO_SCENARIO_ABNORMAL.patientAge));
  const [patientGender, setPatientGender] = useState<'Male' | 'Female' | 'Other' | ''>('Female');
  const [eye, setEye] = useState<EyeLaterality>('OS');
  const [cameraModel, setCameraModel] = useState<string>(DEMO_SCENARIO_ABNORMAL.cameraModel);
  const [clinicName, setClinicName] = useState<string>(DEMO_SCENARIO_ABNORMAL.clinicName);
  const [operatorName, setOperatorName] = useState<string>(DEMO_SCENARIO_ABNORMAL.operatorName);
  const [currentQuality, setCurrentQuality] = useState<ImageQualityAssessment | null>(DEMO_SCENARIO_ABNORMAL.leftEye.quality);
  const [allScreenings, setAllScreenings] = useState<ScreeningRecord[]>([]);

  const refreshScreenings = async () => {
    const list = await screeningService.getAll();
    setAllScreenings(list);
    // If no current screening, initialize with the active scenario's record
    if (!currentScreening && list.length > 0) {
      setCurrentScreening(list[0]);
    }
  };

  useEffect(() => {
    let isMounted = true;
    screeningService.getAll().then((list) => {
      if (isMounted) {
        setAllScreenings(list);
        if (list.length > 0) {
          setCurrentScreening((prev) => prev ?? list[0]);
        }
      }
    });
    return () => {
      isMounted = false;
    };
  }, []);

  const switchDemoAccount = (accountId: 'demo-abnormal' | 'demo-normal') => {
    const scenario = accountId === 'demo-normal' ? DEMO_SCENARIO_NORMAL : DEMO_SCENARIO_ABNORMAL;
    setActiveScenarioState(scenario);

    // Sync dual eye state to the selected scenario
    setLeftEyeImage(scenario.leftEye.originalImage);
    setLeftEyeFilename(scenario.leftEye.filename);
    setLeftEyeStatus('UPLOADED');
    setLeftEyeQuality(scenario.leftEye.quality);

    setRightEyeImage(scenario.rightEye.originalImage);
    setRightEyeFilename(scenario.rightEye.filename);
    setRightEyeStatus('UPLOADED');
    setRightEyeQuality(scenario.rightEye.quality);

    setActiveImage(scenario.leftEye.originalImage);
    setPatientRef(scenario.patientName);
    setPatientAge(String(scenario.patientAge));
    setClinicName(scenario.clinicName);
    setOperatorName(scenario.operatorName);
    setCameraModel(scenario.cameraModel);

    // Update currentScreening to match
    const matchingRecord = allScreenings.find((s) => s.id === scenario.id);
    if (matchingRecord) {
      setCurrentScreening(matchingRecord);
    }
  };

  const loadDemoPreset = (scenarioId: 'demo-abnormal' | 'demo-normal') => {
    switchDemoAccount(scenarioId);
  };

  const setLeftEye = (image: string, filename: string = 'left_eye_capture.jpg') => {
    setLeftEyeImage(image);
    setLeftEyeFilename(filename);
    setLeftEyeStatus('UPLOADED');
    setLeftEyeQuality({
      overallSuitability: 'SUITABLE',
      focus: { name: 'Focus', status: 'OPTIMAL', detail: 'Sharp vessel bifurcation' },
      illumination: { name: 'Illumination', status: 'OPTIMAL', detail: 'Uniform 45° illumination' },
      fieldOfView: { name: 'Field of View', status: 'OPTIMAL', detail: 'Optic disc & macula encompassed' },
      mediaOpacity: { name: 'Media Opacity', status: 'OPTIMAL', detail: 'Clear media' },
      artifactsDetected: [],
      reasons: ['Image is suitable for screening'],
      recommendation: 'Suitable for automated screening analysis.',
    });
    setActiveImage(image);
  };

  const setRightEye = (image: string, filename: string = 'right_eye_capture.jpg') => {
    setRightEyeImage(image);
    setRightEyeFilename(filename);
    setRightEyeStatus('UPLOADED');
    setRightEyeQuality({
      overallSuitability: 'SUITABLE',
      focus: { name: 'Focus', status: 'OPTIMAL', detail: 'Sharp vessel arborization' },
      illumination: { name: 'Illumination', status: 'OPTIMAL', detail: 'Even background luminance' },
      fieldOfView: { name: 'Field of View', status: 'OPTIMAL', detail: 'Centered 45° macular field' },
      mediaOpacity: { name: 'Media Opacity', status: 'OPTIMAL', detail: 'Clear media' },
      artifactsDetected: [],
      reasons: ['Image is suitable for screening'],
      recommendation: 'Suitable for automated screening analysis.',
    });
  };

  const clearLeftEye = () => {
    setLeftEyeImage('');
    setLeftEyeFilename('');
    setLeftEyeStatus('EMPTY');
    setLeftEyeQuality(null);
  };

  const clearRightEye = () => {
    setRightEyeImage('');
    setRightEyeFilename('');
    setRightEyeStatus('EMPTY');
    setRightEyeQuality(null);
  };

  const selectRecordById = (id: string) => {
    const record = allScreenings.find((s) => s.id === id);
    if (record) {
      setCurrentScreening(record);
      if (record.id === 'RV-DEMO-002') {
        setActiveScenarioState(DEMO_SCENARIO_NORMAL);
      } else {
        setActiveScenarioState(DEMO_SCENARIO_ABNORMAL);
      }
    }
  };

  const resetFlow = () => {
    clearLeftEye();
    clearRightEye();
    setActiveImage('');
    setCurrentQuality(null);
  };

  return (
    <ScreeningContext.Provider
      value={{
        activeScenario,
        setActiveScenario: setActiveScenarioState,
        switchDemoAccount,

        leftEyeImage,
        leftEyeFilename,
        leftEyeStatus,
        leftEyeQuality,
        rightEyeImage,
        rightEyeFilename,
        rightEyeStatus,
        rightEyeQuality,

        setLeftEye,
        setRightEye,
        clearLeftEye,
        clearRightEye,
        loadDemoPreset,

        currentScreening,
        setCurrentScreening,
        activeImage,
        setActiveImage,
        patientRef,
        setPatientRef,
        patientAge,
        setPatientAge,
        patientGender,
        setPatientGender,
        eye,
        setEye,
        cameraModel,
        setCameraModel,
        clinicName,
        setClinicName,
        operatorName,
        setOperatorName,
        currentQuality,
        setCurrentQuality,

        allScreenings,
        refreshScreenings,
        selectRecordById,
        resetFlow,
      }}
    >
      {children}
    </ScreeningContext.Provider>
  );
}

export function useScreening() {
  const context = useContext(ScreeningContext);
  if (!context) {
    throw new Error('useScreening must be used within a ScreeningProvider');
  }
  return context;
}

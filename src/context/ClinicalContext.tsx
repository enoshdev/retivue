'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { UserRole, PatientRecord } from '@/types/clinical';
import {
  authApi,
  patientApi,
  screeningApi,
  SafeUser,
  ApiPatient,
  ApiScreening,
  ScreeningLifecycleStatus,
  PatientCreatePayload,
  PatientUpdatePayload,
  ScreeningCreatePayload,
  RegisterPayload,
  LoginPayload,
  UpdateProfilePayload,
} from '@/lib/api';

export interface ActiveUser {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  facility: string;
  registrationNumber?: string;
  avatarInitials: string;
}

function computeInitials(name: string): string {
  if (!name) return 'RT';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

function userToActiveUser(user: SafeUser | null): ActiveUser {
  if (!user) {
    return {
      id: '',
      name: 'Unauthenticated User',
      email: '',
      role: 'CLINICIAN',
      facility: '',
      registrationNumber: undefined,
      avatarInitials: '??',
    };
  }

  return {
    id: user.id,
    name: user.full_name,
    email: user.email,
    role: 'CLINICIAN',
    facility: user.facility_name || 'Independent Clinical Practice',
    registrationNumber: user.registration_number || undefined,
    avatarInitials: computeInitials(user.full_name),
  };
}

export function apiPatientToRecord(p: ApiPatient): PatientRecord {
  let age = 50;
  if (p.date_of_birth) {
    const birthYear = new Date(p.date_of_birth).getFullYear();
    if (!isNaN(birthYear)) {
      age = Math.max(1, new Date().getFullYear() - birthYear);
    }
  }

  let gender: 'Male' | 'Female' | 'Other' = 'Other';
  if (p.sex) {
    const s = p.sex.toLowerCase();
    if (s === 'male') gender = 'Male';
    else if (s === 'female') gender = 'Female';
  }

  return {
    id: p.id,
    mrn: p.patient_code || p.id.slice(0, 8).toUpperCase(),
    fullName: p.full_name,
    age,
    gender,
    contactNumber: p.contact_number || 'N/A',
    diabetesType: (p.diabetes_type as 'Type 1' | 'Type 2' | 'Gestational' | 'Unknown') || 'Type 2',
    diabetesDurationYears: p.diabetes_duration_years || 0,
    recentHbA1c: p.recent_hba1c || 'Not tested',
    consentGiven: p.active_consent?.consent_status === 'granted',
    consentStatus: p.active_consent?.consent_status || 'missing',
    consentDate: p.active_consent?.captured_at ? p.active_consent.captured_at.split('T')[0] : 'N/A',
    registeredAt: p.created_at,
    registeredBy: 'Attending Clinician',
    clinicName: 'Clinical Screening Unit',
    screeningCount: p.screening_count ?? 0,
    notes: p.notes || undefined,
  };
}

interface ClinicalContextType {
  // Real Database User & Session
  user: SafeUser | null;
  currentUser: ActiveUser;
  isAuthenticated: boolean;
  isLoadingAuth: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  registerUser: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<SafeUser | null>;
  updateCurrentUser: (updates: {
    name?: string;
    full_name?: string;
    facility?: string;
    facility_name?: string;
    registrationNumber?: string;
    registration_number?: string;
  }) => Promise<void>;

  currentRole: UserRole;
  switchRole: (role: UserRole) => void;

  // Real Database Patients Collection
  patients: PatientRecord[];
  patientsLoading: boolean;
  patientsTotal: number;
  refreshPatients: (searchQuery?: string) => Promise<PatientRecord[]>;
  getPatientById: (id: string) => PatientRecord | undefined;
  fetchPatientById: (id: string) => Promise<PatientRecord | null>;
  addPatient: (patient: Omit<PatientRecord, 'id' | 'screeningCount' | 'registeredAt'>) => Promise<PatientRecord>;
  updatePatient: (id: string, updates: PatientUpdatePayload) => Promise<PatientRecord>;
  archivePatient: (id: string) => Promise<void>;

  // Real Database Screenings Collection (Phase 4)
  screenings: ApiScreening[];
  screeningsLoading: boolean;
  screeningsTotal: number;
  screeningsError: string | null;
  refreshScreenings: (params?: {
    page?: number;
    page_size?: number;
    patient_id?: string;
    status?: ScreeningLifecycleStatus;
  }) => Promise<ApiScreening[]>;
  fetchScreeningById: (id: string) => Promise<ApiScreening | null>;
  createScreening: (payload: ScreeningCreatePayload) => Promise<ApiScreening>;
  upsertScreeningInCache: (screening: ApiScreening) => void;

  // System Feedback / Notification banner
  notification: { type: 'success' | 'error' | 'info'; message: string } | null;
  setNotification: (notif: { type: 'success' | 'error' | 'info'; message: string } | null) => void;
  clearNotification: () => void;
}

const ClinicalContext = createContext<ClinicalContextType | undefined>(undefined);

export function ClinicalProvider({ children }: { children: React.ReactNode }) {
  // Real authentication state
  const [user, setUser] = useState<SafeUser | null>(null);
  const [isLoadingAuth, setIsLoadingAuth] = useState(true);

  // Real database patients
  const [patients, setPatients] = useState<PatientRecord[]>([]);
  const [patientsLoading, setPatientsLoading] = useState(false);
  const [patientsTotal, setPatientsTotal] = useState(0);

  // Real database screenings (Phase 4)
  const [screenings, setScreenings] = useState<ApiScreening[]>([]);
  const [screeningsLoading, setScreeningsLoading] = useState(false);
  const [screeningsTotal, setScreeningsTotal] = useState(0);
  const [screeningsError, setScreeningsError] = useState<string | null>(null);

  // Ephemeral notifications
  const [notification, setNotification] = useState<{
    type: 'success' | 'error' | 'info';
    message: string;
  } | null>(null);

  const currentUser = userToActiveUser(user);
  const isAuthenticated = !!user;
  const currentRole: UserRole = 'CLINICIAN';

  // Fetch current authenticated user from backend session
  const refreshUser = useCallback(async (): Promise<SafeUser | null> => {
    try {
      const safeUser = await authApi.getMe();
      if (safeUser && safeUser.id) {
        setUser(safeUser);
        return safeUser;
      }
      setUser(null);
      return null;
    } catch {
      setUser(null);
      return null;
    } finally {
      setIsLoadingAuth(false);
    }
  }, []);

  // Fetch owned patient records from backend
  const refreshPatients = useCallback(async (searchQuery?: string): Promise<PatientRecord[]> => {
    setPatientsLoading(true);
    try {
      const res = await patientApi.list({ query: searchQuery, page_size: 100 });
      const records = res.items.map(apiPatientToRecord);
      setPatients(records);
      setPatientsTotal(res.total);
      return records;
    } catch (err) {
      console.error('Failed to query patient registry:', err);
      return [];
    } finally {
      setPatientsLoading(false);
    }
  }, []);

  // Fetch owned screening records from backend
  const refreshScreenings = useCallback(
    async (params?: {
      page?: number;
      page_size?: number;
      patient_id?: string;
      status?: ScreeningLifecycleStatus;
    }): Promise<ApiScreening[]> => {
      setScreeningsLoading(true);
      setScreeningsError(null);
      try {
        const res = await screeningApi.list({
          page: params?.page || 1,
          page_size: params?.page_size || 50,
          patient_id: params?.patient_id,
          status: params?.status,
        });
        if (!params?.patient_id && !params?.status && (!params?.page || params.page === 1)) {
          setScreenings(res.items);
          setScreeningsTotal(res.total);
        }
        return res.items;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to load screenings from database.';
        setScreeningsError(msg);
        return [];
      } finally {
        setScreeningsLoading(false);
      }
    },
    []
  );

  // Check session on component mount and load owned patient & screening registries
  useEffect(() => {
    let ignore = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshUser().then((u) => {
      if (!ignore && u) {
        refreshPatients();
        refreshScreenings();
      }
    });
    return () => {
      ignore = true;
    };
  }, [refreshUser, refreshPatients, refreshScreenings]);

  // Log in with real database verification
  const login = async (payload: LoginPayload): Promise<void> => {
    const res = await authApi.login(payload);
    setUser(res.user);
    await Promise.all([refreshPatients(), refreshScreenings()]);
  };

  // Register a new user in PostgreSQL
  const registerUser = async (payload: RegisterPayload): Promise<void> => {
    const res = await authApi.register(payload);
    setUser(res.user);
    await Promise.all([refreshPatients(), refreshScreenings()]);
  };

  // Log out and revoke session token
  const logout = async (): Promise<void> => {
    try {
      await authApi.logout();
    } finally {
      setUser(null);
      setPatients([]);
      setPatientsTotal(0);
      setScreenings([]);
      setScreeningsTotal(0);
      setScreeningsError(null);
    }
  };

  // Update profile in PostgreSQL
  const updateCurrentUser = async (updates: {
    name?: string;
    full_name?: string;
    facility?: string;
    facility_name?: string;
    registrationNumber?: string;
    registration_number?: string;
  }): Promise<void> => {
    const payload: UpdateProfilePayload = {};
    if (updates.full_name !== undefined) payload.full_name = updates.full_name;
    else if (updates.name !== undefined) payload.full_name = updates.name;

    if (updates.facility_name !== undefined) payload.facility_name = updates.facility_name;
    else if (updates.facility !== undefined) payload.facility_name = updates.facility;

    if (updates.registration_number !== undefined) payload.registration_number = updates.registration_number;
    else if (updates.registrationNumber !== undefined) payload.registration_number = updates.registrationNumber;

    const updatedUser = await authApi.updateMe(payload);
    setUser(updatedUser);
  };

  const switchRole = (_role: UserRole) => {
    void _role;
  };

  const clearNotification = () => setNotification(null);

  // Auto-dismiss notification after 5 seconds
  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => {
        setNotification(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [notification]);

  const getPatientById = (id: string): PatientRecord | undefined => {
    return patients.find((p) => p.id === id || p.mrn === id);
  };

  const fetchPatientById = async (id: string): Promise<PatientRecord | null> => {
    try {
      const apiP = await patientApi.get(id);
      const rec = apiPatientToRecord(apiP);
      setPatients((prev) => {
        const idx = prev.findIndex((p) => p.id === id);
        if (idx >= 0) {
          const updated = [...prev];
          updated[idx] = rec;
          return updated;
        }
        return [rec, ...prev];
      });
      return rec;
    } catch {
      return null;
    }
  };

  const addPatient = async (
    data: Omit<PatientRecord, 'id' | 'screeningCount' | 'registeredAt'>
  ): Promise<PatientRecord> => {
    const payload: PatientCreatePayload = {
      full_name: data.fullName,
      patient_code: data.mrn,
      sex: data.gender.toLowerCase(),
      contact_number: data.contactNumber,
      diabetes_type: data.diabetesType,
      diabetes_duration_years: data.diabetesDurationYears,
      recent_hba1c: data.recentHbA1c,
      notes: data.notes,
      initial_consent: data.consentGiven
        ? {
            consent_type: 'retinal_screening',
            consent_status: 'granted',
            capture_method: 'digital_acknowledgement',
            notes: `Informed consent captured at registration (${data.consentDate})`,
          }
        : undefined,
    };

    const created = await patientApi.create(payload);
    const rec = apiPatientToRecord(created);
    setPatients((prev) => [rec, ...prev]);
    setPatientsTotal((prev) => prev + 1);
    setNotification({
      type: 'success',
      message: `Patient ${rec.fullName} (${rec.mrn}) successfully registered in database.`,
    });
    return rec;
  };

  const updatePatient = async (id: string, updates: PatientUpdatePayload): Promise<PatientRecord> => {
    const updated = await patientApi.update(id, updates);
    const rec = apiPatientToRecord(updated);
    setPatients((prev) => prev.map((p) => (p.id === id ? rec : p)));
    setNotification({
      type: 'success',
      message: `Patient ${rec.fullName} updated successfully.`,
    });
    return rec;
  };

  const archivePatient = async (id: string): Promise<void> => {
    await patientApi.archive(id);
    setPatients((prev) => prev.filter((p) => p.id !== id));
    setPatientsTotal((prev) => Math.max(0, prev - 1));
    setNotification({
      type: 'info',
      message: 'Patient record archived.',
    });
  };

  const upsertScreeningInCache = useCallback((screening: ApiScreening) => {
    setScreenings((prev) => {
      const idx = prev.findIndex((s) => s.id === screening.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = screening;
        return next;
      }
      return [screening, ...prev];
    });
  }, []);

  const fetchScreeningById = useCallback(
    async (id: string): Promise<ApiScreening | null> => {
      try {
        const item = await screeningApi.get(id);
        upsertScreeningInCache(item);
        return item;
      } catch {
        return null;
      }
    },
    [upsertScreeningInCache]
  );

  const createScreening = useCallback(
    async (payload: ScreeningCreatePayload): Promise<ApiScreening> => {
      const created = await screeningApi.create(payload);
      setScreenings((prev) => [created, ...prev]);
      setScreeningsTotal((prev) => prev + 1);
      setPatients((prev) =>
        prev.map((p) =>
          p.id === payload.patient_id ? { ...p, screeningCount: p.screeningCount + 1 } : p
        )
      );
      return created;
    },
    []
  );

  return (
    <ClinicalContext.Provider
      value={{
        user,
        currentUser,
        isAuthenticated,
        isLoadingAuth,
        login,
        registerUser,
        logout,
        refreshUser,
        updateCurrentUser,
        currentRole,
        switchRole,
        patients,
        patientsLoading,
        patientsTotal,
        refreshPatients,
        getPatientById,
        fetchPatientById,
        addPatient,
        updatePatient,
        archivePatient,
        screenings,
        screeningsLoading,
        screeningsTotal,
        screeningsError,
        refreshScreenings,
        fetchScreeningById,
        createScreening,
        upsertScreeningInCache,
        notification,
        setNotification,
        clearNotification,
      }}
    >
      {children}
    </ClinicalContext.Provider>
  );
}

export function useClinical() {
  const context = useContext(ClinicalContext);
  if (!context) {
    throw new Error('useClinical must be used within a ClinicalProvider');
  }
  return context;
}

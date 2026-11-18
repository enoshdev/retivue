/**
 * RETIVUE Central API Client
 * 
 * Provides unified, typed access to the FastAPI backend.
 * Automatically manages:
 * - Credentials (HttpOnly session cookies)
 * - Double-submit CSRF tokens
 * - Structured API error reporting
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface SafeUser {
  id: string;
  full_name: string;
  email: string;
  email_verified: boolean;
  is_active: boolean;
  facility_name?: string | null;
  registration_number?: string | null;
  created_at: string;
  last_login_at?: string | null;
}

export interface RegisterPayload {
  full_name: string;
  email: string;
  password: string;
  facility_name?: string;
  registration_number?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface UpdateProfilePayload {
  full_name?: string;
  facility_name?: string;
  registration_number?: string;
}

export interface AuthSuccessResponse {
  success: boolean;
  message: string;
  user: SafeUser;
}

export interface CSRFResponse {
  csrf_token: string;
}

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

/**
 * Retrieve a cookie value by name in the browser.
 */
function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(^|;\\s*)(' + name + ')=([^;]*)'));
  return match ? decodeURIComponent(match[3]) : null;
}

/**
 * Fetch or retrieve an existing CSRF token for mutating requests.
 */
async function ensureCsrfToken(): Promise<string> {
  const existing = getCookie('retivue_csrf');
  if (existing) {
    return existing;
  }

  // Request fresh token from backend
  const response = await fetch(`${API_BASE_URL}/api/auth/csrf`, {
    method: 'GET',
    credentials: 'include',
  });

  if (!response.ok) {
    throw new ApiError('Failed to initialize CSRF token', response.status);
  }

  const data: CSRFResponse = await response.json();
  return data.csrf_token;
}

/**
 * Core fetch wrapper with credentials and CSRF support.
 */
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const method = (options.method || 'GET').toUpperCase();
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };

  // If request sends a body and content-type isn't set, default to JSON
  if (options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  // Double-submit CSRF protection on mutating methods
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    try {
      const csrfToken = await ensureCsrfToken();
      if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken;
      }
    } catch {
      // If fetching CSRF fails, proceed; backend will reject if strictly required
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include', // Always send and accept HttpOnly cookies
  });

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    let errorData: unknown = null;
    try {
      errorData = await response.json();
      if (typeof errorData === 'object' && errorData !== null) {
        const d = errorData as Record<string, unknown>;
        if (typeof d.detail === 'string') {
          errorDetail = d.detail;
        } else if (Array.isArray(d.detail)) {
          // Pydantic validation errors
          errorDetail = d.detail.map((err: { msg?: string }) => err.msg || 'Invalid field').join(', ');
        } else if (typeof d.message === 'string') {
          errorDetail = d.message;
        }
      }
    } catch {
      // Non-JSON response
    }
    throw new ApiError(errorDetail, response.status, errorData);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

export const authApi = {
  /**
   * Register a new user account.
   */
  async register(payload: RegisterPayload): Promise<AuthSuccessResponse> {
    return apiRequest<AuthSuccessResponse>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Log into an existing account.
   */
  async login(payload: LoginPayload): Promise<AuthSuccessResponse> {
    return apiRequest<AuthSuccessResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Log out and revoke active server session.
   */
  async logout(): Promise<{ success: boolean; message: string }> {
    return apiRequest<{ success: boolean; message: string }>('/api/auth/logout', {
      method: 'POST',
    });
  },

  /**
   * Get active authenticated session profile.
   */
  async getMe(): Promise<SafeUser> {
    const data = await apiRequest<SafeUser | AuthSuccessResponse>('/api/auth/me', {
      method: 'GET',
    });
    return 'user' in data ? data.user : data;
  },

  /**
   * Update active user profile.
   */
  async updateMe(payload: UpdateProfilePayload): Promise<SafeUser> {
    const data = await apiRequest<SafeUser | AuthSuccessResponse>('/api/auth/me', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
    return 'user' in data ? data.user : data;
  },

  /**
   * Get CSRF token.
   */
  async getCsrfToken(): Promise<CSRFResponse> {
    return apiRequest<CSRFResponse>('/api/auth/csrf', {
      method: 'GET',
    });
  },
};

export interface ApiConsent {
  id: string;
  patient_id: string;
  recorded_by_user_id: string;
  consent_type: string;
  consent_status: 'pending' | 'granted' | 'declined' | 'revoked';
  capture_method: string;
  captured_at: string;
  revoked_at?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface ApiPatient {
  id: string;
  owner_user_id: string;
  patient_code?: string | null;
  full_name: string;
  date_of_birth?: string | null;
  sex?: string | null;
  contact_number?: string | null;
  diabetes_type?: string | null;
  diabetes_duration_years?: number | null;
  recent_hba1c?: string | null;
  notes?: string | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  screening_count?: number;
  active_consent?: ApiConsent | null;
}

export interface PatientCreatePayload {
  full_name: string;
  patient_code?: string;
  date_of_birth?: string;
  sex?: string;
  contact_number?: string;
  diabetes_type?: string;
  diabetes_duration_years?: number;
  recent_hba1c?: string;
  notes?: string;
  initial_consent?: {
    consent_type?: string;
    consent_status?: 'pending' | 'granted' | 'declined' | 'revoked';
    capture_method?: string;
    notes?: string;
  };
}

export interface PatientUpdatePayload {
  full_name?: string;
  patient_code?: string;
  date_of_birth?: string;
  sex?: string;
  contact_number?: string;
  diabetes_type?: string;
  diabetes_duration_years?: number;
  recent_hba1c?: string;
  notes?: string;
}

export interface PatientListResponse {
  items: ApiPatient[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export const patientApi = {
  /**
   * Lists patients owned by current authenticated user.
   */
  async list(params?: {
    page?: number;
    page_size?: number;
    query?: string;
    include_archived?: boolean;
    sort_by?: 'created_at' | 'name' | 'updated_at';
    sort_order?: 'asc' | 'desc';
  }): Promise<PatientListResponse> {
    const sp = new URLSearchParams();
    if (params?.page) sp.set('page', String(params.page));
    if (params?.page_size) sp.set('page_size', String(params.page_size));
    if (params?.query) sp.set('query', params.query);
    if (params?.include_archived !== undefined) sp.set('include_archived', String(params.include_archived));
    if (params?.sort_by) sp.set('sort_by', params.sort_by);
    if (params?.sort_order) sp.set('sort_order', params.sort_order);

    const qs = sp.toString();
    return apiRequest<PatientListResponse>(`/api/patients${qs ? `?${qs}` : ''}`);
  },

  /**
   * Retrieves single patient by ID.
   */
  async get(patientId: string): Promise<ApiPatient> {
    return apiRequest<ApiPatient>(`/api/patients/${patientId}`);
  },

  /**
   * Registers a new patient.
   */
  async create(payload: PatientCreatePayload): Promise<ApiPatient> {
    return apiRequest<ApiPatient>('/api/patients', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Updates permitted patient details.
   */
  async update(patientId: string, payload: PatientUpdatePayload): Promise<ApiPatient> {
    return apiRequest<ApiPatient>(`/api/patients/${patientId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Soft-archives patient.
   */
  async archive(patientId: string): Promise<ApiPatient> {
    return apiRequest<ApiPatient>(`/api/patients/${patientId}/archive`, {
      method: 'POST',
    });
  },

  /**
   * Restores an archived patient.
   */
  async unarchive(patientId: string): Promise<ApiPatient> {
    return apiRequest<ApiPatient>(`/api/patients/${patientId}/unarchive`, {
      method: 'POST',
    });
  },

  /**
   * Records a new informed consent event.
   */
  async recordConsent(
    patientId: string,
    payload: {
      consent_type?: string;
      consent_status?: 'pending' | 'granted' | 'declined' | 'revoked';
      capture_method?: string;
      notes?: string;
    }
  ): Promise<ApiConsent> {
    return apiRequest<ApiConsent>(`/api/patients/${patientId}/consent`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Revokes informed consent.
   */
  async revokeConsent(patientId: string, notes?: string): Promise<ApiConsent> {
    return apiRequest<ApiConsent>(`/api/patients/${patientId}/consent/revoke`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    });
  },

  /**
   * Retrieves historical consent audit trail.
   */
  async getConsentHistory(patientId: string): Promise<ApiConsent[]> {
    return apiRequest<ApiConsent[]>(`/api/patients/${patientId}/consent`);
  },
};

export type ScreeningLifecycleStatus =
  | 'draft'
  | 'awaiting_images'
  | 'images_incomplete'
  | 'ready_for_quality_assessment'
  | 'quality_failed_recapture_required'
  | 'ai_completed_review_required'
  | 'ai_completed_advisory'
  | 'ai_failed_review_required'
  | 'clinically_reviewed_signed'
  | 'cancelled'
  | 'archived';

export interface AiModelRegistryItem {
  model_key: string;
  model_version: string;
  architecture: string;
  training_strategy: string;
  checkpoint_sha256: string;
  checkpoint_epoch: number;
  is_default: boolean;
  checkpoint_present: boolean;
  status_note: string;
}

export interface AiExplanationResponse {
  id: string;
  screening_id: string;
  screening_image_id: string;
  ai_run_id: string;
  eye: 'OD' | 'OS';
  target_class: number;
  target_class_label: string;
  is_default_target: boolean;
  status: 'completed' | 'unavailable_ungradable' | 'failed';
  explanation_text: string;
  model_layer: string;
  image_sha256: string;
  checkpoint_sha256: string;
  has_heatmap: boolean;
  has_overlay: boolean;
  created_at: string;
}

export interface AiEyeResult {
  id: string;
  eye: 'OD' | 'OS';
  screening_image_id: string;
  gradable: boolean;
  quality_status: string;
  quality_reason?: string | null;
  quality_metrics: Record<string, unknown>;
  predicted_grade?: number | null;
  predicted_label?: string | null;
  probabilities: Record<string, number>;
  confidence_max_prob?: number | null;
  top2_margin?: number | null;
  normalized_entropy?: number | null;
  vtdr_prob_sum?: number | null;
  uncertainty_review_required: boolean;
  uncertainty_reasons: string[];
  high_risk_flagged: boolean;
  explanation?: AiExplanationResponse | null;
}

export interface AiRunResponse {
  id: string;
  screening_id: string;
  model_key: string;
  model_version: string;
  architecture: string;
  checkpoint_sha256: string;
  checkpoint_epoch: number;
  preprocessing_config: Record<string, unknown>;
  overall_status: string;
  overall_review_required: boolean;
  overall_escalation_reasons: string[];
  higher_risk_eye?: 'OD' | 'OS' | null;
  highest_predicted_grade?: number | null;
  highest_predicted_label?: string | null;
  research_disclaimer: string;
  calibration_warning: string;
  error_message?: string | null;
  execution_ms: number;
  inference_timestamp: string;
  eye_results: AiEyeResult[];
}

export interface ClinicalReviewCreatePayload {
  od_confirmed_grade?: number | null;
  os_confirmed_grade?: number | null;
  ai_agreement_status: 'agreed_with_ai' | 'overrode_ai' | 'independent_no_ai' | 'recapture_ordered';
  override_rationale?: string | null;
  clinical_findings: string;
  follow_up_plan: string;
  recapture_required?: boolean;
  confirm_independent_review: boolean;
}

export interface ClinicalReviewResponse {
  id: string;
  screening_id: string;
  reviewer_user_id: string;
  reviewer_name_snapshot: string;
  reviewer_registration_number_snapshot: string;
  linked_ai_run_id?: string | null;
  od_confirmed_grade?: number | null;
  od_confirmed_label?: string | null;
  os_confirmed_grade?: number | null;
  os_confirmed_label?: string | null;
  worst_eye_confirmed_grade?: number | null;
  worst_eye_confirmed_label?: string | null;
  ai_agreement_status: string;
  override_rationale?: string | null;
  clinical_findings: string;
  follow_up_plan: string;
  recapture_required: boolean;
  is_signed: boolean;
  signed_at: string;
  created_at: string;
}

export interface ReferralCreatePayload {
  screening_id: string;
  urgency: 'IMMEDIATE_48H' | 'WITHIN_2_WEEKS' | 'STANDARD_SURVEILLANCE';
  target_specialty: string;
  target_facility: string;
  reason_summary: string;
  clinical_summary?: string;
}

export interface ReferralStatusUpdatePayload {
  status: 'DISPATCHED' | 'ACCEPTED' | 'APPOINTMENT_SCHEDULED' | 'COMPLETED' | 'CANCELLED';
  appointment_notes?: string;
}

export interface ReferralResponse {
  id: string;
  referral_reference: string;
  screening_id: string;
  clinical_review_id: string;
  patient_id: string;
  patient_name?: string | null;
  patient_mrn?: string | null;
  urgency: string;
  target_specialty: string;
  target_facility: string;
  reason_summary: string;
  clinical_summary?: string | null;
  status: string;
  appointment_notes?: string | null;
  dispatched_at: string;
  updated_at: string;
}

export interface ScreeningReportResponse {
  report_id: string;
  generated_at: string;
  screening_id: string;
  screening_reference: string;
  screening_status: string;
  screening_date: string;
  patient: {
    id: string;
    full_name: string;
    medical_record_number: string;
    date_of_birth?: string | null;
    gender?: string | null;
    diabetes_type?: string | null;
  };
  consent: {
    status: string;
    obtained_at?: string | null;
    form_version?: string | null;
  };
  images: Array<{
    id: string;
    eye: 'OD' | 'OS';
    file_size_bytes: number;
    width: number;
    height: number;
    checksum: string;
    uploaded_at: string;
    is_current: boolean;
  }>;
  latest_ai_run?: AiRunResponse | null;
  explanations?: Record<string, AiExplanationResponse | null>;
  clinical_review?: ClinicalReviewResponse | null;
  referrals: ReferralResponse[];
  audit_trail: Array<{
    id: string;
    screening_id?: string | null;
    patient_id?: string | null;
    event_type: string;
    summary: string;
    metadata: Record<string, unknown>;
    created_at: string;
  }>;
  clinical_safety_notice: string;
}

export interface EyeComparisonResult {
  eye: 'OD' | 'OS';
  has_previous_image: boolean;
  has_current_image: boolean;
  previous_grade?: number | null;
  current_grade?: number | null;
  previous_label?: string | null;
  current_label?: string | null;
  grade_difference?: number | null;
  previous_probabilities: Record<string, number>;
  current_probabilities: Record<string, number>;
  probability_shifts: Record<string, number>;
  previous_vtdr_prob?: number | null;
  current_vtdr_prob?: number | null;
  vtdr_risk_shift?: number | null;
  previous_gradable: boolean;
  current_gradable: boolean;
  has_previous_explanation: boolean;
  has_current_explanation: boolean;
  neutral_summary: string;
  review_required_shift: boolean;
}

export interface ScreeningComparisonResponse {
  patient_id: string;
  patient_name: string;
  medical_record_number: string;
  current_screening_id: string;
  current_screening_reference: string;
  current_screening_date: string;
  previous_screening_id: string;
  previous_screening_reference: string;
  previous_screening_date: string;
  days_interval: number;
  is_directly_comparable: boolean;
  comparability_notes: string[];
  od_comparison: EyeComparisonResult;
  os_comparison: EyeComparisonResult;
  overall_comparison_summary: string;
  clinical_safety_disclaimer: string;
}

export interface PatientTimelineEvent {
  screening_id: string;
  screening_reference: string;
  screening_date: string;
  status: string;
  od_grade?: number | null;
  os_grade?: number | null;
  worst_grade?: number | null;
  worst_label?: string | null;
  referable_dr_risk?: number | null;
  is_bilateral_complete: boolean;
  quality_status: string;
  review_status: string;
  reviewer_name?: string | null;
  has_ai_run: boolean;
  report_id?: string | null;
  trend_category: string;
  trend_description: string;
}

export interface PatientTimelineResponse {
  patient_id: string;
  patient_name: string;
  medical_record_number: string;
  total_screenings: number;
  events: PatientTimelineEvent[];
  summary: string;
  clinical_safety_notice: string;
}

export interface ApiScreeningImage {
  id: string;
  screening_id: string;
  eye: 'OD' | 'OS';
  original_filename?: string | null;
  detected_media_type: string;
  file_extension: string;
  file_size_bytes: number;
  image_width: number;
  image_height: number;
  sha256_checksum: string;
  has_exif_metadata: boolean;
  uploaded_at: string;
  upload_status: string;
  is_current: boolean;
  replaced_at?: string | null;
}

export interface ApiScreeningImageUploadResponse extends ApiScreeningImage {
  screening_status: ScreeningLifecycleStatus;
  has_od_image: boolean;
  has_os_image: boolean;
  is_bilateral_complete: boolean;
}

export interface ApiScreeningPatientSummary {
  id: string;
  patient_code?: string | null;
  full_name: string;
  date_of_birth?: string | null;
  sex?: string | null;
  diabetes_type?: string | null;
  recent_hba1c?: string | null;
  consent_status?: string | null;
}

export interface ApiScreening {
  id: string;
  owner_user_id: string;
  patient_id: string;
  screening_reference: string;
  camera_model?: string | null;
  clinical_notes?: string | null;
  status: ScreeningLifecycleStatus;
  has_od_image: boolean;
  has_os_image: boolean;
  is_bilateral_complete: boolean;
  od_image?: ApiScreeningImage | null;
  os_image?: ApiScreeningImage | null;
  patient?: ApiScreeningPatientSummary | null;
  created_at: string;
  updated_at: string;
  submitted_at?: string | null;
  archived_at?: string | null;
}

export interface ScreeningListResponse {
  items: ApiScreening[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ScreeningCreatePayload {
  patient_id: string;
  camera_model?: string;
  clinical_notes?: string;
  as_draft?: boolean;
}

export interface ScreeningUpdatePayload {
  camera_model?: string;
  clinical_notes?: string;
}

async function uploadImageWithProgress(
  url: string,
  file: File,
  method: 'POST' | 'PUT' = 'POST',
  onProgress?: (percent: number) => void
): Promise<ApiScreeningImageUploadResponse> {
  const csrfToken = await ensureCsrfToken().catch(() => '');

  return new Promise<ApiScreeningImageUploadResponse>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url, true);
    xhr.withCredentials = true;
    xhr.setRequestHeader('Accept', 'application/json');
    if (csrfToken) {
      xhr.setRequestHeader('X-CSRF-Token', csrfToken);
    }

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        const pct = Math.min(100, Math.round((event.loaded / event.total) * 100));
        onProgress(pct);
      }
    };

    xhr.onload = () => {
      let data: unknown = null;
      try {
        data = JSON.parse(xhr.responseText || '{}');
      } catch {
        data = null;
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        if (onProgress) onProgress(100);
        resolve(data as ApiScreeningImageUploadResponse);
      } else {
        let message = `Image upload failed (HTTP ${xhr.status})`;
        if (typeof data === 'object' && data !== null && 'detail' in data) {
          const detail = (data as Record<string, unknown>).detail;
          if (typeof detail === 'string') message = detail;
          else if (Array.isArray(detail)) {
            message = detail.map((e: { msg?: string }) => e.msg || 'Validation error').join(', ');
          }
        }
        reject(new ApiError(message, xhr.status, data));
      }
    };

    xhr.onerror = () => {
      reject(new ApiError('Network error occurred during image upload.', 0));
    };

    const formData = new FormData();
    formData.append('file', file);
    xhr.send(formData);
  });
}

export const screeningApi = {
  async create(payload: ScreeningCreatePayload): Promise<ApiScreening> {
    return apiRequest<ApiScreening>('/api/screenings', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async list(params?: {
    page?: number;
    page_size?: number;
    patient_id?: string;
    status?: ScreeningLifecycleStatus;
    include_archived?: boolean;
    sort_by?: 'created_at' | 'updated_at' | 'submitted_at';
    sort_order?: 'asc' | 'desc';
  }): Promise<ScreeningListResponse> {
    const sp = new URLSearchParams();
    if (params?.page) sp.set('page', String(params.page));
    if (params?.page_size) sp.set('page_size', String(params.page_size));
    if (params?.patient_id) sp.set('patient_id', params.patient_id);
    if (params?.status) sp.set('status', params.status);
    if (params?.include_archived !== undefined) sp.set('include_archived', String(params.include_archived));
    if (params?.sort_by) sp.set('sort_by', params.sort_by);
    if (params?.sort_order) sp.set('sort_order', params.sort_order);
    const qs = sp.toString();
    return apiRequest<ScreeningListResponse>(`/api/screenings${qs ? `?${qs}` : ''}`);
  },

  async get(screeningId: string): Promise<ApiScreening> {
    return apiRequest<ApiScreening>(`/api/screenings/${screeningId}`);
  },

  async update(screeningId: string, payload: ScreeningUpdatePayload): Promise<ApiScreening> {
    return apiRequest<ApiScreening>(`/api/screenings/${screeningId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  async uploadImage(
    screeningId: string,
    eye: 'OD' | 'OS',
    file: File,
    onProgress?: (percent: number) => void
  ): Promise<ApiScreeningImageUploadResponse> {
    return uploadImageWithProgress(
      `${API_BASE_URL}/api/screenings/${screeningId}/images/${eye}`,
      file,
      'POST',
      onProgress
    );
  },

  async replaceImage(
    screeningId: string,
    eye: 'OD' | 'OS',
    file: File,
    onProgress?: (percent: number) => void
  ): Promise<ApiScreeningImageUploadResponse> {
    return uploadImageWithProgress(
      `${API_BASE_URL}/api/screenings/${screeningId}/images/${eye}/replace`,
      file,
      'POST',
      onProgress
    );
  },

  async fetchImageBlobUrl(screeningId: string, eye: 'OD' | 'OS'): Promise<string> {
    const response = await fetch(`${API_BASE_URL}/api/screenings/${screeningId}/images/${eye}`, {
      method: 'GET',
      credentials: 'include',
      cache: 'no-store',
    });
    if (!response.ok) {
      let detail = `Failed to retrieve ${eye} retinal image (HTTP ${response.status})`;
      try {
        const err = await response.json();
        if (err && typeof err.detail === 'string') detail = err.detail;
      } catch {
        // ignore JSON parse error
      }
      throw new ApiError(detail, response.status);
    }
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  },

  async getImageHistory(screeningId: string, eye: 'OD' | 'OS'): Promise<ApiScreeningImage[]> {
    return apiRequest<ApiScreeningImage[]>(`/api/screenings/${screeningId}/images/${eye}/history`);
  },

  async submit(screeningId: string): Promise<ApiScreening> {
    return apiRequest<ApiScreening>(`/api/screenings/${screeningId}/submit`, {
      method: 'POST',
    });
  },

  async cancel(screeningId: string): Promise<ApiScreening> {
    return apiRequest<ApiScreening>(`/api/screenings/${screeningId}/cancel`, {
      method: 'POST',
    });
  },

  async archive(screeningId: string): Promise<ApiScreening> {
    return apiRequest<ApiScreening>(`/api/screenings/${screeningId}/archive`, {
      method: 'POST',
    });
  },
};

export const clinicalWorkflowApi = {
  async getAiModels(): Promise<AiModelRegistryItem[]> {
    return apiRequest<AiModelRegistryItem[]>('/api/workflow/ai-models');
  },

  async runAiScreening(screeningId: string, modelKey?: string): Promise<AiRunResponse> {
    return apiRequest<AiRunResponse>(`/api/screenings/${screeningId}/ai-run`, {
      method: 'POST',
      body: JSON.stringify({ model_key: modelKey || null }),
    });
  },

  async getLatestAiRun(screeningId: string): Promise<AiRunResponse | null> {
    return apiRequest<AiRunResponse | null>(`/api/screenings/${screeningId}/ai-runs/latest`);
  },

  async listAiRuns(screeningId: string): Promise<AiRunResponse[]> {
    return apiRequest<AiRunResponse[]>(`/api/screenings/${screeningId}/ai-runs`);
  },

  async createClinicalReview(
    screeningId: string,
    payload: ClinicalReviewCreatePayload
  ): Promise<ClinicalReviewResponse> {
    return apiRequest<ClinicalReviewResponse>(`/api/screenings/${screeningId}/review`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async getClinicalReview(screeningId: string): Promise<ClinicalReviewResponse | null> {
    return apiRequest<ClinicalReviewResponse | null>(`/api/screenings/${screeningId}/review`);
  },

  async createReferral(payload: ReferralCreatePayload): Promise<ReferralResponse> {
    return apiRequest<ReferralResponse>('/api/referrals', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async listReferrals(screeningId?: string): Promise<ReferralResponse[]> {
    const qs = screeningId ? `?screening_id=${encodeURIComponent(screeningId)}` : '';
    return apiRequest<ReferralResponse[]>(`/api/referrals${qs}`);
  },

  async getReferral(referralId: string): Promise<ReferralResponse> {
    return apiRequest<ReferralResponse>(`/api/referrals/${referralId}`);
  },

  async updateReferralStatus(
    referralId: string,
    payload: ReferralStatusUpdatePayload
  ): Promise<ReferralResponse> {
    return apiRequest<ReferralResponse>(`/api/referrals/${referralId}/status`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  async getExplanation(
    screeningId: string,
    eye: 'OD' | 'OS',
    targetClass?: number
  ): Promise<AiExplanationResponse | null> {
    const qs = targetClass !== undefined ? `?target_class=${targetClass}` : '';
    return apiRequest<AiExplanationResponse | null>(
      `/api/screenings/${screeningId}/explanations/${eye}${qs}`
    );
  },

  async fetchExplanationImageBlobUrl(
    screeningId: string,
    eye: 'OD' | 'OS',
    kind: 'heatmap' | 'overlay',
    targetClass?: number
  ): Promise<string> {
    const qs = targetClass !== undefined ? `?target_class=${targetClass}` : '';
    const response = await fetch(
      `${API_BASE_URL}/api/screenings/${screeningId}/explanations/${eye}/${kind}${qs}`,
      {
        method: 'GET',
        credentials: 'include',
        cache: 'no-store',
      }
    );
    if (!response.ok) {
      let detail = `Failed to retrieve ${eye} Grad-CAM ${kind} (HTTP ${response.status})`;
      try {
        const err = await response.json();
        if (err && typeof err.detail === 'string') detail = err.detail;
      } catch {
        // ignore JSON parse error
      }
      throw new ApiError(detail, response.status);
    }
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  },

  async regenerateExplanation(
    screeningId: string,
    eye: 'OD' | 'OS',
    targetClass?: number
  ): Promise<AiExplanationResponse> {
    return apiRequest<AiExplanationResponse>(
      `/api/screenings/${screeningId}/explanations/${eye}/regenerate`,
      {
        method: 'POST',
        body: JSON.stringify({ target_class: targetClass ?? null }),
      }
    );
  },

  async getScreeningReport(screeningId: string): Promise<ScreeningReportResponse> {
    return apiRequest<ScreeningReportResponse>(`/api/screenings/${screeningId}/report`);
  },

  async getScreeningAuditTrail(screeningId: string): Promise<Array<{
    id: string;
    screening_id?: string | null;
    patient_id?: string | null;
    event_type: string;
    summary: string;
    metadata: Record<string, unknown>;
    created_at: string;
  }>> {
    return apiRequest(`/api/screenings/${screeningId}/audit`);
  },

  async getScreeningComparison(
    screeningId: string,
    previousScreeningId?: string
  ): Promise<ScreeningComparisonResponse> {
    const qs = previousScreeningId ? `?previous_screening_id=${encodeURIComponent(previousScreeningId)}` : '';
    return apiRequest<ScreeningComparisonResponse>(`/api/screenings/${screeningId}/comparison${qs}`);
  },

  async getPatientTimeline(patientId: string): Promise<PatientTimelineResponse> {
    return apiRequest<PatientTimelineResponse>(`/api/patients/${patientId}/timeline`);
  },

  async downloadReportPdf(screeningId: string, filename?: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/screenings/${screeningId}/report/pdf`, {
      method: 'GET',
      credentials: 'include',
    });
    if (!response.ok) {
      let detail = `Failed to generate official PDF report (HTTP ${response.status})`;
      try {
        const err = await response.json();
        if (err && typeof err.detail === 'string') detail = err.detail;
      } catch {
        // ignore
      }
      throw new ApiError(detail, response.status);
    }
    const blob = await response.blob();
    const downloadUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename || `retivue_screening_report_${screeningId.slice(0, 8).toUpperCase()}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(downloadUrl);
  },
};

/**
 * Authentication Service Interface for Retivue
 * 
 * Prepares the application for real backend authentication (FastAPI / OAuth2 / JWT).
 * Strictly contains NO hardcoded credentials, bypass checks, or fabricated users.
 */

export interface UserProfile {
  id: string;
  email: string;
  fullName: string;
  role: 'CLINICIAN' | 'VISION_TECHNICIAN' | 'ADMINISTRATOR';
  facilityName?: string;
  facilityLocation?: string;
  createdAt: string;
}

export interface AuthSession {
  user: UserProfile | null;
  accessToken: string | null;
  isAuthenticated: boolean;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  fullName: string;
  email: string;
  password: string;
  facilityName: string;
  role: string;
}

export interface AuthResponse {
  success: boolean;
  message?: string;
  session?: AuthSession;
  error?: string;
}

export const authService = {
  /**
   * Submit credentials to real backend auth endpoint.
   * If backend is not connected yet, returns clear status rather than fabricating a session.
   */
  login: async (credentials: LoginPayload): Promise<AuthResponse> => {
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials),
      });

      if (!response.ok) {
        if (response.status === 404 || response.status === 502) {
          return {
            success: false,
            error: 'Authentication service is not currently connected to a live backend. Contact your facility administrator.',
          };
        }
        const data = await response.json().catch(() => ({}));
        return {
          success: false,
          error: data.message || 'Invalid email or password.',
        };
      }

      const data = await response.json();
      return {
        success: true,
        session: data,
      };
    } catch {
      // Backend not running/unreachable
      return {
        success: false,
        error: 'Authentication server is currently unreachable. Backend integration pending in Phase 2.',
      };
    }
  },

  /**
   * Submit registration to real backend auth endpoint.
   */
  register: async (payload: RegisterPayload): Promise<AuthResponse> => {
    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        if (response.status === 404 || response.status === 502) {
          return {
            success: false,
            error: 'Facility registration service is not currently connected to a live backend.',
          };
        }
        const data = await response.json().catch(() => ({}));
        return {
          success: false,
          error: data.message || 'Registration failed.',
        };
      }

      const data = await response.json();
      return {
        success: true,
        session: data,
      };
    } catch {
      return {
        success: false,
        error: 'Registration server is currently unreachable. Backend integration pending in Phase 2.',
      };
    }
  },

  /**
   * Get current session state (starts as null when not authenticated).
   */
  getSession: async (): Promise<AuthSession> => {
    return {
      user: null,
      accessToken: null,
      isAuthenticated: false,
    };
  },
};

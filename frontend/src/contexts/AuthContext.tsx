// [Input] Runtime API base config, auth token storage, and backend auth/profile endpoints.
// [Output] React auth context with login/register/logout/profile verification helpers.
// [Pos] frontend auth context node
// [Sync] 2026-06-12: use centralized API_BASE so deployed frontend can call backend cross-origin.
// [Sync] 2026-06-23: consume Google OAuth callback access_token fragments and
//                    expose backend-driven Google login/logout helpers.
/**
 * Authentication context and hooks
 *
 * Manages JWT token storage, user state, and auth operations
 */

import { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { STORAGE_KEYS } from '../constants/storageKeys';
import { API_BASE, apiUrl } from '../lib/apiBase';

interface User {
  id: number;
  email: string;
  display_name?: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: () => void;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchUserProfile = async (authToken: string) => {
    const res = await fetch(`${API_BASE}/api/me`, {
      credentials: 'include',
      headers: {
        'Authorization': `Bearer ${authToken}`
      }
    });

    if (!res.ok) {
      throw new Error('Failed to fetch user profile');
    }

    return res.json();
  };

  // Load token from localStorage on mount
  useEffect(() => {
    const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const oauthToken = fragment.get('access_token');
    if (oauthToken) {
      localStorage.setItem(STORAGE_KEYS.AUTH_TOKEN, oauthToken);
      window.history.replaceState(null, document.title, window.location.pathname + window.location.search);
    }

    const savedToken = oauthToken || localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
    if (savedToken) {
      // Verify token by fetching user info
      fetch(`${API_BASE}/api/me`, {
        credentials: 'include',
        headers: {
          'Authorization': `Bearer ${savedToken}`
        }
      })
        .then(res => {
          if (!res.ok) throw new Error('Token invalid');
          return res.json();
        })
        .then(userData => {
          setUser(userData);
          setToken(savedToken);
        })
        .catch(() => {
          // Token invalid, clear it
          localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
    }
  }, []);

  const loginWithGoogle = () => {
    const returnTo = `${window.location.pathname}${window.location.search}`;
    window.location.href = apiUrl(`/oauth/google/login?return_to=${encodeURIComponent(returnTo)}`);
  };

  const login = async (email: string, password: string) => {
    const response = await fetch(`${API_BASE}/api/login`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ email, password })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }

    const data = await response.json();
    localStorage.setItem(STORAGE_KEYS.AUTH_TOKEN, data.token);
    setToken(data.token);

    try {
      const profile = await fetchUserProfile(data.token);
      setUser(profile);
    } catch (error) {
      // Profile fetch failed, clear token to avoid inconsistent state
      localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
      setToken(null);
      throw error;
    }
  };

  const register = async (email: string, password: string, displayName?: string) => {
    const response = await fetch(`${API_BASE}/api/register`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        email,
        password,
        display_name: displayName
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Registration failed');
    }

    const data = await response.json();
    localStorage.setItem(STORAGE_KEYS.AUTH_TOKEN, data.token);
    setToken(data.token);

    try {
      const profile = await fetchUserProfile(data.token);
      setUser(profile);
    } catch (error) {
      localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
      setToken(null);
      throw error;
    }
  };

  const logout = () => {
    const activeToken = token || localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
    fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
      headers: activeToken ? { 'Authorization': `Bearer ${activeToken}` } : undefined
    }).catch(() => {
      // Local logout should still complete when the network request fails.
    });
    setUser(null);
    setToken(null);
    localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        loginWithGoogle,
        register,
        logout,
        isAuthenticated: !!user && !!token
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

/**
 * Get current auth token for API calls
 */
export function getAuthToken(): string | null {
  return localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
}

/**
 * [Input] Device Flow verification API, AuthContext state, and auth forms.
 * [Output] Browser verification page for approving or denying device user codes.
 * [Pos] device-flow-verification component node in frontend/src/components/Auth
 */

import React, { useEffect, useMemo, useState } from 'react';
import { apiUrl } from '../../lib/apiBase';
import { getAuthToken, useAuth } from '../../contexts/AuthContext';
import LoginForm from './LoginForm';
import RegisterForm from './RegisterForm';

type VerificationInfo = {
  client_id: string;
  scope: string;
  status: string;
  user_code: string;
  expires_at: string;
};

function errorMessage(error: any): string {
  const detail = error?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.error_description) return detail.error_description;
  if (detail?.error) return detail.error;
  return error?.message || 'Request failed';
}

function readInitialUserCode(): string {
  const params = new URLSearchParams(window.location.search);
  return (params.get('user_code') || '').toUpperCase();
}

export default function DeviceVerificationPage() {
  const { isAuthenticated } = useAuth();
  const [authScreen, setAuthScreen] = useState<'login' | 'register'>('login');
  const [userCode, setUserCode] = useState(readInitialUserCode);
  const [info, setInfo] = useState<VerificationInfo | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const normalizedCode = useMemo(() => userCode.trim().toUpperCase(), [userCode]);

  useEffect(() => {
    if (!normalizedCode) return;
    setIsLoading(true);
    setError('');
    fetch(apiUrl(`/oauth/device/verify?user_code=${encodeURIComponent(normalizedCode)}`), {
      credentials: 'include'
    })
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw data;
        setInfo(data);
      })
      .catch((err) => {
        setInfo(null);
        setError(errorMessage(err));
      })
      .finally(() => setIsLoading(false));
  }, [normalizedCode]);

  const submitDecision = async (approve: boolean) => {
    setIsSubmitting(true);
    setError('');
    try {
      const token = getAuthToken();
      const res = await fetch(apiUrl('/oauth/device/verify'), {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ user_code: normalizedCode, approve })
      });
      const data = await res.json();
      if (!res.ok) throw data;
      setInfo((current) => current ? { ...current, status: data.status } : current);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const shellStyle: React.CSSProperties = {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '20px',
    background: 'var(--color-bg-page)',
    fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
  };

  if (!isAuthenticated) {
    return (
      <div style={shellStyle}>
        {authScreen === 'login' ? (
          <LoginForm onSuccess={() => undefined} onSwitchToRegister={() => setAuthScreen('register')} />
        ) : (
          <RegisterForm onSuccess={() => undefined} onSwitchToLogin={() => setAuthScreen('login')} />
        )}
      </div>
    );
  }

  const status = info?.status;
  const completed = status === 'approved' || status === 'denied' || status === 'consumed';

  return (
    <div style={shellStyle}>
      <div style={{
        width: '100%',
        maxWidth: '460px',
        padding: '28px',
        border: '2px solid var(--color-border-paper)',
        borderRadius: '8px',
        backgroundColor: 'var(--color-bg-paper)',
        boxShadow: '0 4px 12px var(--color-shadow-soft)'
      }}>
        <h1 style={{
          margin: '0 0 18px',
          fontSize: '24px',
          color: 'var(--color-text-body)'
        }}>
          Device Authorization
        </h1>

        <label style={{
          display: 'block',
          marginBottom: '8px',
          color: 'var(--color-text-secondary)',
          fontSize: '14px'
        }}>
          User code
        </label>
        <input
          value={userCode}
          onChange={(event) => setUserCode(event.target.value)}
          disabled={isSubmitting}
          style={{
            width: '100%',
            boxSizing: 'border-box',
            padding: '12px',
            border: '1px solid var(--color-border-paper)',
            borderRadius: '6px',
            backgroundColor: 'var(--color-bg-surface-solid)',
            color: 'var(--color-text-body)',
            fontSize: '20px',
            letterSpacing: 0,
            textTransform: 'uppercase',
            marginBottom: '16px'
          }}
        />

        {isLoading && (
          <div style={{ color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
            Loading...
          </div>
        )}

        {error && (
          <div style={{
            padding: '12px',
            marginBottom: '16px',
            border: '1px solid color-mix(in srgb, var(--color-state-danger) 25%, transparent)',
            borderRadius: '6px',
            color: 'var(--color-state-danger)',
            backgroundColor: 'color-mix(in srgb, var(--color-state-danger) 8%, transparent)'
          }}>
            {error}
          </div>
        )}

        {info && (
          <div style={{
            marginBottom: '18px',
            color: 'var(--color-text-secondary)',
            lineHeight: 1.5
          }}>
            <div><strong style={{ color: 'var(--color-text-body)' }}>Client:</strong> {info.client_id}</div>
            <div><strong style={{ color: 'var(--color-text-body)' }}>Scope:</strong> {info.scope || 'default'}</div>
            <div><strong style={{ color: 'var(--color-text-body)' }}>Status:</strong> {info.status}</div>
          </div>
        )}

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            type="button"
            onClick={() => submitDecision(true)}
            disabled={!info || isSubmitting || completed}
            style={{
              flex: 1,
              padding: '12px',
              border: 'none',
              borderRadius: '6px',
              backgroundColor: completed ? 'var(--color-disabled-bg)' : 'var(--color-action-link)',
              color: 'var(--color-text-on-action)',
              cursor: !info || isSubmitting || completed ? 'not-allowed' : 'pointer',
              fontWeight: 600
            }}
          >
            Approve
          </button>
          <button
            type="button"
            onClick={() => submitDecision(false)}
            disabled={!info || isSubmitting || completed}
            style={{
              flex: 1,
              padding: '12px',
              border: '1px solid var(--color-border-paper)',
              borderRadius: '6px',
              backgroundColor: 'var(--color-bg-surface-solid)',
              color: 'var(--color-text-body)',
              cursor: !info || isSubmitting || completed ? 'not-allowed' : 'pointer',
              fontWeight: 600
            }}
          >
            Deny
          </button>
        </div>
      </div>
    </div>
  );
}

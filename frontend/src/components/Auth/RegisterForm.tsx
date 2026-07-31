/**
 * [Input] AuthContext register/google helpers and register form callbacks.
 * [Output] Registration form with password signup and Google OAuth entry points.
 * [Pos] register-form component node in frontend/src/components/Auth
 * [Sync] 2026-06-23: add Continue with Google button backed by Python OAuth login.
 *
 * Registration form component
 */

import React, { useState } from 'react';
import { FaGoogle } from 'react-icons/fa';
import { useAuth } from '../../contexts/AuthContext';

interface RegisterFormProps {
  onSuccess: () => void;
  onSwitchToLogin: () => void;
}

export default function RegisterForm({ onSuccess, onSwitchToLogin }: RegisterFormProps) {
  const { register, loginWithGoogle } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    setIsSubmitting(true);

    try {
      await register(email, password, displayName || undefined);
      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Registration failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{
      width: '100%',
      maxWidth: '400px',
      margin: '0 auto',
      padding: '32px',
      backgroundColor: 'var(--color-bg-paper)',
      border: '2px solid var(--color-border-paper)',
      borderRadius: '12px',
      boxShadow: '0 4px 12px var(--color-shadow-soft)',
      fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
    }}>
      <h2 style={{
        margin: '0 0 24px 0',
        fontSize: '24px',
        fontWeight: 600,
        color: 'var(--color-text-body)',
        textAlign: 'center'
      }}>
        Create Account
      </h2>

      {error && (
        <div style={{
          padding: '12px',
          marginBottom: '16px',
          backgroundColor: 'color-mix(in srgb, var(--color-state-danger) 8%, transparent)',
          border: '1px solid color-mix(in srgb, var(--color-state-danger) 25%, transparent)',
          borderRadius: '6px',
          fontSize: '14px',
          color: 'var(--color-state-danger)'
        }}>
          {error}
        </div>
      )}

      <button
        type="button"
        onClick={loginWithGoogle}
        disabled={isSubmitting}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          padding: '11px',
          border: '1px solid var(--color-border-paper)',
          borderRadius: '6px',
          backgroundColor: 'var(--color-bg-surface-solid)',
          color: 'var(--color-text-body)',
          fontSize: '15px',
          fontWeight: 600,
          cursor: isSubmitting ? 'not-allowed' : 'pointer',
          fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
          marginBottom: '18px'
        }}
      >
        <FaGoogle aria-hidden="true" />
        Continue with Google
      </button>

      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        marginBottom: '18px',
        color: 'var(--color-text-muted)',
        fontSize: '13px'
      }}>
        <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--color-border-paper)' }} />
        <span>or</span>
        <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--color-border-paper)' }} />
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '16px' }}>
          <label style={{
            display: 'block',
            marginBottom: '6px',
            fontSize: '14px',
            fontWeight: 500,
            color: 'var(--color-text-secondary)'
          }}>
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            disabled={isSubmitting}
            style={{
              width: '100%',
              padding: '10px 12px',
              border: '1px solid var(--color-border-paper)',
              borderRadius: '6px',
              fontSize: '15px',
              fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif", backgroundColor: 'var(--color-bg-surface-solid)', color: 'var(--color-text-body)',
              boxSizing: 'border-box'
            }}
          />
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label style={{
            display: 'block',
            marginBottom: '6px',
            fontSize: '14px',
            fontWeight: 500,
            color: 'var(--color-text-secondary)'
          }}>
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            disabled={isSubmitting}
            style={{
              width: '100%',
              padding: '10px 12px',
              border: '1px solid var(--color-border-paper)',
              borderRadius: '6px',
              fontSize: '15px',
              fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif", backgroundColor: 'var(--color-bg-surface-solid)', color: 'var(--color-text-body)',
              boxSizing: 'border-box'
            }}
          />
          <div style={{
            marginTop: '4px',
            fontSize: '12px',
            color: 'var(--color-text-muted)'
          }}>
            At least 6 characters
          </div>
        </div>

        <div style={{ marginBottom: '24px' }}>
          <label style={{
            display: 'block',
            marginBottom: '6px',
            fontSize: '14px',
            fontWeight: 500,
            color: 'var(--color-text-secondary)'
          }}>
            Display Name (Optional)
          </label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            disabled={isSubmitting}
            style={{
              width: '100%',
              padding: '10px 12px',
              border: '1px solid var(--color-border-paper)',
              borderRadius: '6px',
              fontSize: '15px',
              fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif", backgroundColor: 'var(--color-bg-surface-solid)', color: 'var(--color-text-body)',
              boxSizing: 'border-box'
            }}
          />
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          style={{
            width: '100%',
            padding: '12px',
            border: 'none',
            borderRadius: '6px',
            backgroundColor: isSubmitting ? 'var(--color-disabled-bg)' : 'var(--color-action-link)',
            color: 'var(--color-text-on-action)',
            fontSize: '16px',
            fontWeight: 600,
            cursor: isSubmitting ? 'not-allowed' : 'pointer',
            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
            transition: 'background-color 0.2s'
          }}
          onMouseEnter={(e) => {
            if (!isSubmitting) {
              e.currentTarget.style.backgroundColor = 'var(--color-action-link-hover)';
            }
          }}
          onMouseLeave={(e) => {
            if (!isSubmitting) {
              e.currentTarget.style.backgroundColor = 'var(--color-action-link)';
            }
          }}
        >
          {isSubmitting ? 'Creating account...' : 'Register'}
        </button>
      </form>

      <div style={{
        marginTop: '20px',
        textAlign: 'center',
        fontSize: '14px',
        color: 'var(--color-text-secondary)'
      }}>
        Already have an account?{' '}
        <button
          onClick={onSwitchToLogin}
          disabled={isSubmitting}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--color-action-link)',
            cursor: 'pointer',
            textDecoration: 'underline',
            fontSize: '14px',
            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
          }}
        >
          Login
        </button>
      </div>
    </div>
  );
}

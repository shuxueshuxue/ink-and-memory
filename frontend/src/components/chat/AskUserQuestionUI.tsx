// [Input] AskUserQuestionInput from tool part; onSubmit/onCancel callbacks from ToolConfirmationDock.
// [Output] Interactive question form — rendered unframed inside the floating ToolConfirmationDock
//          above AIInputDock (framed/showHeader/label props keep the legacy card look available).
// [Pos] ask-user-question component node in frontend/src/components/chat
// [Sync] 2026-05-27: add null guard for undefined input at useMemo start to prevent crash when tool is in input-streaming state.
// [Sync] 2026-07-08: use the semantic on-action text token for dark-mode-safe submit buttons.
// [Sync] 2026-07-20: add framed/showHeader/submitLabel/cancelLabel props so the form can render
//        unframed with Chinese 取消/提交 buttons inside ToolConfirmationDock (design §8).
// [Sync] 2026-07-20: add compact density prop (smaller fonts, tighter gaps/padding, 3-row
//        textarea) so the dock-mounted form does not dominate the chat viewport.
// [Sync] 2026-07-20: i18n — submit/cancel defaults and form copy (header, select placeholder,
//        fallback question, Yes option) resolve through chat.toolConfirmation / chat.askUser
//        namespaces (en + zh) via useTranslation.
import { useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { IconCheck, IconX } from './Icons';

export type QuestionOption =
  | string
  | { value: string; label: string }
  | { label: string; description?: string; value?: string };

export interface QuestionField {
  id?: string;
  question?: string;
  label?: string;
  header?: string;
  type?: 'text' | 'textarea' | 'select' | 'checkbox' | 'radio' | 'number';
  options?: QuestionOption[];
  required?: boolean;
  default?: string | number | boolean;
  placeholder?: string;
  description?: string;
  multiSelect?: boolean;
}

export interface AskUserQuestionInput {
  questions?: QuestionField[];
  question?: string;
  message?: string;
  text?: string;
  prompt?: string;
  options?: string[];
  choices?: string[];
  default?: string;
}

interface AskUserQuestionUIProps {
  input: AskUserQuestionInput;
  toolCallId: string;
  toolName: string;
  isProcessing?: boolean;
  /** Render with the legacy card chrome (border/radius/header). Default true; the
   *  floating ToolConfirmationDock passes false and provides its own chrome. */
  framed?: boolean;
  /** Show the "Your input is needed" header row. Only meaningful when framed. */
  showHeader?: boolean;
  submitLabel?: string;
  cancelLabel?: string;
  /** Compact density: smaller fonts, tighter gaps and padding — used inside the
   *  floating ToolConfirmationDock so the panel does not dominate the viewport. */
  compact?: boolean;
  onSubmit: (answers: Record<string, unknown>) => void;
  onCancel: () => void;
}

const fieldStyle: CSSProperties = {
  width: '100%',
  padding: '0.7rem 0.85rem',
  fontSize: '0.9rem',
  color: 'var(--color-text-primary)',
  background: 'var(--color-bg-paper)',
  border: '1px solid var(--color-border-paper)',
  borderRadius: '10px',
  boxSizing: 'border-box',
};

const compactFieldStyle: CSSProperties = {
  ...fieldStyle,
  padding: '0.42rem 0.65rem',
  fontSize: '0.82rem',
  borderRadius: '8px',
};

export default function AskUserQuestionUI({ input, toolCallId, toolName, isProcessing = false, framed = true, showHeader = true, submitLabel, cancelLabel, compact = false, onSubmit, onCancel }: AskUserQuestionUIProps) {
  const { t } = useTranslation();
  const resolvedSubmitLabel = submitLabel ?? t('chat.toolConfirmation.submit');
  const resolvedCancelLabel = cancelLabel ?? t('chat.toolConfirmation.cancel');
  const effectiveFieldStyle = compact ? compactFieldStyle : fieldStyle;
  const questionGap = compact ? '0.3rem' : '0.5rem';
  const formGap = compact ? '0.6rem' : '1rem';
  const labelFontSize = compact ? '0.82rem' : '0.9rem';
  const descriptionFontSize = compact ? '0.7rem' : '0.76rem';
  const buttonStyle: CSSProperties = compact
    ? { borderRadius: '999px', padding: '0.42rem 0.85rem', fontSize: '0.8rem' }
    : { borderRadius: '999px', padding: '0.8rem 1rem', fontSize: '0.88rem' };
  const questions = useMemo<QuestionField[]>(() => {
    if (!input) {
      return [{ id: 'answer', question: t('chat.askUser.fallbackQuestion'), type: 'text', required: true }];
    }
    if (input.questions?.length) {
      return input.questions.map((question, index) => {
        const hasOptions = Array.isArray(question.options) && question.options.length > 0;
        return {
          id: question.id || `q${index}`,
          question: question.question || question.label || question.header || t('chat.askUser.questionNumber', { number: index + 1 }),
          type: question.type || (hasOptions ? 'radio' : 'text'),
          options: question.options,
          required: question.required ?? true,
          default: question.default,
          placeholder: question.placeholder,
          description: question.description,
          multiSelect: question.multiSelect,
        };
      });
    }

    const questionText = input.question || input.message || input.text || input.prompt;
    if (questionText) {
      const options = input.options || input.choices;
      return [{ id: 'answer', question: questionText, type: options?.length ? 'radio' : 'text', options, required: true, default: input.default }];
    }

    return [{ id: 'answer', question: t('chat.askUser.fallbackQuestion'), type: 'text', required: true }];
  }, [input, t]);

  const [answers, setAnswers] = useState<Record<string, unknown>>(() => {
    const initial: Record<string, unknown> = {};
    questions.forEach((question) => {
      const key = question.question || question.id || 'answer';
      if (question.default !== undefined) initial[key] = question.default;
      else if (question.type === 'checkbox') initial[key] = false;
      else initial[key] = '';
    });
    return initial;
  });

  useEffect(() => {
    setAnswers((current) => {
      const next: Record<string, unknown> = {};
      questions.forEach((question) => {
        const key = question.question || question.id || 'answer';
        next[key] = current[key] ?? (question.default ?? (question.type === 'checkbox' ? false : ''));
      });
      return next;
    });
  }, [questions]);

  const handleChange = useCallback((questionText: string, value: unknown) => {
    setAnswers((current) => ({ ...current, [questionText]: value }));
  }, []);

  const getCleanAnswers = useCallback(() => {
    const cleaned: Record<string, unknown> = {};
    Object.entries(answers).forEach(([key, value]) => {
      if (value !== '' && value !== undefined && value !== null) {
        cleaned[key] = value;
      }
    });
    return cleaned;
  }, [answers]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
        event.preventDefault();
        onSubmit(getCleanAnswers());
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        onCancel();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [getCleanAnswers, onCancel, onSubmit]);

  const isValid = useMemo(() => {
    return questions.every((question) => {
      if (!question.required) return true;
      const key = question.question || question.id || 'answer';
      const value = answers[key];
      return value !== undefined && value !== null && value !== '';
    });
  }, [answers, questions]);

  return (
    <div style={framed ? { overflow: 'hidden', borderRadius: '14px', border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-paper)' } : { width: '100%' }}>
      {framed && showHeader ? (
        <div style={{ padding: '0.95rem 1rem', borderBottom: '1px solid var(--color-border-paper)', background: 'var(--color-bg-surface)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1rem' }}>❓</span>
            <h3 style={{ margin: 0, fontSize: '0.96rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>{t('chat.askUser.header')}</h3>
          </div>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{toolName} · {toolCallId}</p>
        </div>
      ) : null}

      <form onSubmit={(event) => { event.preventDefault(); onSubmit(getCleanAnswers()); }} style={{ padding: framed ? (compact ? '0.75rem' : '1rem') : 0, display: 'flex', flexDirection: 'column', gap: formGap }}>
        {questions.map((question, index) => {
          const answerKey = question.question || question.id || `q${index}`;
          const fieldId = question.id || `q${index}`;
          const value = answers[answerKey];

          return (
            <div key={fieldId} style={{ display: 'flex', flexDirection: 'column', gap: questionGap }}>
              <label htmlFor={fieldId} style={{ fontSize: labelFontSize, fontWeight: 600, color: 'var(--color-text-primary)' }}>
                {question.question}
                {question.required ? <span style={{ color: 'var(--color-state-danger)', marginLeft: '0.25rem' }}>*</span> : null}
              </label>
              {question.description ? <p style={{ margin: 0, fontSize: descriptionFontSize, color: 'var(--color-text-muted)' }}>{question.description}</p> : null}

              {question.type === 'textarea' ? (
                <textarea id={fieldId} value={String(value || '')} onChange={(event) => handleChange(answerKey, event.target.value)} placeholder={question.placeholder} rows={compact ? 3 : 4} style={{ ...effectiveFieldStyle, resize: 'vertical' }} required={question.required} disabled={isProcessing} />
              ) : question.type === 'select' && question.options ? (
                <select id={fieldId} value={String(value || '')} onChange={(event) => handleChange(answerKey, event.target.value)} style={effectiveFieldStyle} required={question.required} disabled={isProcessing}>
                  <option value="">{t('chat.askUser.selectOption')}</option>
                  {question.options.map((option) => {
                    const optionValue = typeof option === 'string' ? option : option.value || option.label;
                    const optionLabel = typeof option === 'string' ? option : option.label;
                    return <option key={optionValue} value={optionValue}>{optionLabel}</option>;
                  })}
                </select>
              ) : question.type === 'radio' && question.options ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: compact ? '0.3rem' : '0.5rem' }}>
                  {question.options.map((option) => {
                    const optionValue = typeof option === 'string' ? option : option.value || option.label;
                    const optionLabel = typeof option === 'string' ? option : option.label;
                    const optionDescription = typeof option === 'string' ? undefined : ('description' in option ? option.description : undefined);
                    return (
                      <label key={optionValue} style={{ display: 'flex', alignItems: compact ? 'center' : undefined, gap: compact ? '0.5rem' : '0.75rem', padding: compact ? '0.4rem 0.6rem' : '0.7rem 0.85rem', borderRadius: compact ? '8px' : '10px', background: 'var(--color-bg-surface)', cursor: 'pointer' }}>
                        <input type="radio" name={fieldId} value={optionValue} checked={value === optionValue} onChange={(event) => handleChange(answerKey, event.target.value)} disabled={isProcessing} style={compact ? { margin: 0 } : undefined} />
                        <span>
                          <span style={{ display: 'block', fontSize: compact ? '0.82rem' : '0.9rem', fontWeight: 500, color: 'var(--color-text-primary)' }}>{optionLabel}</span>
                          {optionDescription ? <span style={{ display: 'block', marginTop: '0.15rem', fontSize: descriptionFontSize, color: 'var(--color-text-muted)' }}>{optionDescription}</span> : null}
                        </span>
                      </label>
                    );
                  })}
                </div>
              ) : question.type === 'checkbox' ? (
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontSize: labelFontSize, color: 'var(--color-text-primary)', cursor: 'pointer' }}>
                  <input type="checkbox" id={fieldId} checked={Boolean(value)} onChange={(event) => handleChange(answerKey, event.target.checked)} disabled={isProcessing} />
                  {t('chat.askUser.yes')}
                </label>
              ) : question.type === 'number' ? (
                <input type="number" id={fieldId} value={String(value || '')} onChange={(event) => handleChange(answerKey, event.target.value === '' ? '' : Number(event.target.value))} placeholder={question.placeholder} style={effectiveFieldStyle} required={question.required} disabled={isProcessing} />
              ) : (
                <input type="text" id={fieldId} value={String(value || '')} onChange={(event) => handleChange(answerKey, event.target.value)} placeholder={question.placeholder} style={effectiveFieldStyle} required={question.required} disabled={isProcessing} />
              )}
            </div>
          );
        })}

        <div style={{ display: 'flex', gap: compact ? '0.5rem' : '0.75rem', paddingTop: compact ? 0 : '0.25rem' }}>
          <button type="submit" disabled={isProcessing || !isValid} style={{ flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem', border: 'none', ...buttonStyle, background: 'var(--color-action-link)', color: 'var(--color-text-on-action)', fontWeight: 600, cursor: isProcessing || !isValid ? 'not-allowed' : 'pointer', opacity: isProcessing || !isValid ? 0.55 : 1 }}>
            <IconCheck style={{ width: compact ? '0.85rem' : '1rem', height: compact ? '0.85rem' : '1rem' }} />
            {resolvedSubmitLabel}
          </button>
          <button type="button" onClick={onCancel} disabled={isProcessing} style={{ flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem', ...buttonStyle, border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-paper)', color: 'var(--color-text-secondary)', fontWeight: 600, cursor: isProcessing ? 'not-allowed' : 'pointer', opacity: isProcessing ? 0.55 : 1 }}>
            <IconX style={{ width: compact ? '0.85rem' : '1rem', height: compact ? '0.85rem' : '1rem' }} />
            {resolvedCancelLabel}
          </button>
        </div>
      </form>
    </div>
  );
}

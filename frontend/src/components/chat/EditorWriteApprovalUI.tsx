// [Input] tool input from MCP editor write tools; onApprove/onReject callbacks from ToolMessagePart.
// [Output] Specialized confirmation UI cards for write_segment, delete_segment, insert_widget, reply_to_comment.
// [Pos] editor-write-approval component node in frontend/src/components/chat
// [Sync] 2026-05-29: initial creation — 4 specialized editor write tool confirmation UIs + router component.
// [Sync] 2026-05-29: remove decorative icons from editor write approval/completed cards in the chat message surface.
// [Sync] 2026-07-08: use semantic on-action text tokens for editor write approval buttons in dark mode.
// [Sync] 2026-07-08: move editor write tool name detection into editorWriteTools.ts so this file exports components only.
// [Sync] 2026-07-20: i18n — all approval card copy (titles, labels, buttons, completed
//        states) resolves through the chat.editorWrite namespace (en + zh) via useTranslation.
import { useCallback, useEffect, useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';

// ── Shared types ─────────────────────────────────────────────────────────────

interface EditorWriteApprovalBaseProps {
  toolCallId: string;
  isProcessing: boolean;
  onApprove: () => void;
  onReject: (reason?: string) => void;
}

// ── Shared style constants ────────────────────────────────────────────────────

const cardStyle: CSSProperties = {
  overflow: 'hidden',
  borderRadius: '14px',
  border: '1px solid var(--color-border-paper)',
  background: 'var(--color-bg-paper)',
};

const headerStyle: CSSProperties = {
  padding: '0.95rem 1rem',
  borderBottom: '1px solid var(--color-border-paper)',
  background: 'var(--color-bg-surface)',
};

const metaStyle: CSSProperties = {
  margin: '0.25rem 0 0',
  fontSize: '0.75rem',
  color: 'var(--color-text-muted)',
};

const bodyStyle: CSSProperties = {
  padding: '1rem',
  display: 'flex',
  flexDirection: 'column',
  gap: '0.85rem',
};

const labelStyle: CSSProperties = {
  fontSize: '0.75rem',
  fontWeight: 600,
  color: 'var(--color-text-muted)',
  textTransform: 'uppercase' as const,
  letterSpacing: '0.04em',
  marginBottom: '0.3rem',
};

const previewBoxStyle: CSSProperties = {
  borderRadius: '10px',
  border: '1px solid var(--color-border-paper)',
  background: 'var(--color-bg-surface)',
  padding: '0.75rem 0.85rem',
  fontSize: '0.88rem',
  lineHeight: 1.65,
  color: 'var(--color-text-primary)',
  whiteSpace: 'pre-wrap',
  overflowY: 'auto',
  maxHeight: '12rem',
};

const reasonBoxStyle: CSSProperties = {
  borderRadius: '10px',
  border: '1px solid var(--color-border-paper)',
  background: 'var(--color-bg-surface)',
  padding: '0.65rem 0.85rem',
  fontSize: '0.86rem',
  lineHeight: 1.6,
  color: 'var(--color-text-secondary)',
  fontStyle: 'italic',
};

const fieldStyle: CSSProperties = {
  width: '100%',
  padding: '0.7rem 0.85rem',
  fontSize: '0.88rem',
  color: 'var(--color-text-primary)',
  background: 'var(--color-bg-paper)',
  border: '1px solid var(--color-border-paper)',
  borderRadius: '10px',
  boxSizing: 'border-box',
  resize: 'vertical' as const,
};

// ── Shared sub-components ─────────────────────────────────────────────────────

function LabelRow({ children }: { children: React.ReactNode }) {
  return <div style={labelStyle}>{children}</div>;
}

function PreviewBox({ text, mono = false }: { text: string; mono?: boolean }) {
  return (
    <div style={{ ...previewBoxStyle, fontFamily: mono ? 'ui-monospace, SFMono-Regular, Menlo, monospace' : undefined, fontSize: mono ? '0.8rem' : '0.88rem' }}>
      {text}
    </div>
  );
}

function ReasonBox({ reason }: { reason: string }) {
  const { t } = useTranslation();
  return (
    <div>
      <LabelRow>{t('chat.editorWrite.reasonLabel')}</LabelRow>
      <div style={reasonBoxStyle}>{reason}</div>
    </div>
  );
}

interface ActionRowProps {
  isProcessing: boolean;
  approveLabel: string;
  rejectLabel: string;
  approveDanger?: boolean;
  rejectReason: string;
  showRejectInput: boolean;
  onToggleRejectInput: () => void;
  onRejectReasonChange: (v: string) => void;
  onApprove: () => void;
  onReject: () => void;
}

function ActionRow({
  isProcessing,
  approveLabel,
  rejectLabel,
  approveDanger = false,
  rejectReason,
  showRejectInput,
  onToggleRejectInput,
  onRejectReasonChange,
  onApprove,
  onReject,
}: ActionRowProps) {
  const { t } = useTranslation();
  const approveColor = approveDanger ? 'var(--color-state-danger, #d9534f)' : 'var(--color-action-link)';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', paddingTop: '0.1rem' }}>
      {showRejectInput ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          <LabelRow>{t('chat.editorWrite.rejectReasonLabel')}</LabelRow>
          <textarea
            value={rejectReason}
            onChange={(e) => onRejectReasonChange(e.target.value)}
            placeholder={t('chat.editorWrite.rejectReasonPlaceholder')}
            rows={2}
            style={fieldStyle}
            disabled={isProcessing}
          />
        </div>
      ) : null}
      <div style={{ display: 'flex', gap: '0.75rem' }}>
        <button
          type="button"
          onClick={onApprove}
          disabled={isProcessing}
          style={{ flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', border: 'none', borderRadius: '999px', padding: '0.8rem 1rem', background: approveColor, color: 'var(--color-text-on-action)', fontSize: '0.88rem', fontWeight: 600, cursor: isProcessing ? 'not-allowed' : 'pointer', opacity: isProcessing ? 0.55 : 1 }}
        >
          {approveLabel}
        </button>
        <button
          type="button"
          onClick={showRejectInput ? onReject : onToggleRejectInput}
          disabled={isProcessing}
          style={{ flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', borderRadius: '999px', padding: '0.8rem 1rem', border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-paper)', color: 'var(--color-text-secondary)', fontSize: '0.88rem', fontWeight: 600, cursor: isProcessing ? 'not-allowed' : 'pointer', opacity: isProcessing ? 0.55 : 1 }}
        >
          {showRejectInput ? t('chat.editorWrite.confirmReject') : rejectLabel}
        </button>
      </div>
      {!showRejectInput ? (
        <button type="button" onClick={onToggleRejectInput} disabled={isProcessing} style={{ alignSelf: 'center', border: 'none', background: 'transparent', color: 'var(--color-text-muted)', fontSize: '0.76rem', cursor: 'pointer', textDecoration: 'underline', padding: 0 }}>
          {t('chat.editorWrite.addRejectNote')}
        </button>
      ) : (
        <button type="button" onClick={onToggleRejectInput} disabled={isProcessing} style={{ alignSelf: 'center', border: 'none', background: 'transparent', color: 'var(--color-text-muted)', fontSize: '0.76rem', cursor: 'pointer', textDecoration: 'underline', padding: 0 }}>
          {t('chat.editorWrite.rejectDirectly')}
        </button>
      )}
    </div>
  );
}

// ── useApprovalKeyboard ───────────────────────────────────────────────────────

function useApprovalKeyboard(onApprove: () => void, onReject: (reason?: string) => void, rejectReason: string) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey)) return;
      if (e.key === 'Enter') { e.preventDefault(); onApprove(); }
      if (e.key === 'Escape') { e.preventDefault(); onReject(rejectReason || undefined); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onApprove, onReject, rejectReason]);
}

// ── WriteSegmentApprovalUI ────────────────────────────────────────────────────

interface WriteSegmentInput {
  editor_session_id?: string;
  cellId?: string;
  text?: string;
  reason?: string;
}

export function WriteSegmentApprovalUI({ toolCallId, isProcessing, onApprove, onReject, input }: EditorWriteApprovalBaseProps & { input: WriteSegmentInput }) {
  const { t } = useTranslation();
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const handleApprove = useCallback(() => { if (!isProcessing) onApprove(); }, [isProcessing, onApprove]);
  const handleReject = useCallback(() => { if (!isProcessing) onReject(rejectReason || undefined); }, [isProcessing, onReject, rejectReason]);

  useApprovalKeyboard(handleApprove, onReject, rejectReason);

  return (
    <div style={cardStyle}>
      <div style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: '0.96rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>{t('chat.editorWrite.writeSegmentTitle')}</h3>
        </div>
        <p style={metaStyle}>mcp__editor__write_segment · {toolCallId}</p>
      </div>
      <div style={bodyStyle}>
        {input.cellId ? (
          <div>
            <LabelRow>{t('chat.editorWrite.targetSegmentId')}</LabelRow>
            <code style={{ fontSize: '0.82rem', color: 'var(--color-text-secondary)', background: 'var(--color-bg-surface)', padding: '0.2rem 0.5rem', borderRadius: '6px' }}>{input.cellId}</code>
          </div>
        ) : null}
        {input.text != null ? (
          <div>
            <LabelRow>{t('chat.editorWrite.newContentPreview')}</LabelRow>
            <PreviewBox text={input.text} />
          </div>
        ) : null}
        {input.reason ? <ReasonBox reason={input.reason} /> : null}
        <ActionRow
          isProcessing={isProcessing}
          approveLabel={t('chat.editorWrite.acceptChange')}
          rejectLabel={t('chat.editorWrite.reject')}
          rejectReason={rejectReason}
          showRejectInput={showRejectInput}
          onToggleRejectInput={() => setShowRejectInput((v) => !v)}
          onRejectReasonChange={setRejectReason}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      </div>
    </div>
  );
}

// ── DeleteSegmentApprovalUI ───────────────────────────────────────────────────

interface DeleteSegmentInput {
  editor_session_id?: string;
  cellId?: string;
  reason?: string;
}

export function DeleteSegmentApprovalUI({ toolCallId, isProcessing, onApprove, onReject, input }: EditorWriteApprovalBaseProps & { input: DeleteSegmentInput }) {
  const { t } = useTranslation();
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const handleApprove = useCallback(() => { if (!isProcessing) onApprove(); }, [isProcessing, onApprove]);
  const handleReject = useCallback(() => { if (!isProcessing) onReject(rejectReason || undefined); }, [isProcessing, onReject, rejectReason]);

  useApprovalKeyboard(handleApprove, onReject, rejectReason);

  return (
    <div style={{ ...cardStyle, borderColor: 'rgba(217,83,79,0.35)' }}>
      <div style={{ ...headerStyle, background: 'rgba(217,83,79,0.06)', borderBottomColor: 'rgba(217,83,79,0.2)' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: '0.96rem', fontWeight: 600, color: '#c0392b' }}>{t('chat.editorWrite.deleteSegmentTitle')}</h3>
        </div>
        <p style={metaStyle}>mcp__editor__delete_segment · {toolCallId}</p>
      </div>
      <div style={bodyStyle}>
        {input.cellId ? (
          <div>
            <LabelRow>{t('chat.editorWrite.segmentToDeleteId')}</LabelRow>
            <code style={{ fontSize: '0.82rem', color: '#c0392b', background: 'rgba(217,83,79,0.08)', padding: '0.2rem 0.5rem', borderRadius: '6px' }}>{input.cellId}</code>
          </div>
        ) : null}
        <div style={{ borderRadius: '10px', border: '1px solid rgba(217,83,79,0.3)', background: 'rgba(217,83,79,0.06)', padding: '0.65rem 0.85rem', fontSize: '0.85rem', color: '#c0392b' }}>
          {t('chat.editorWrite.irreversibleWarning')}
        </div>
        {input.reason ? <ReasonBox reason={input.reason} /> : null}
        <ActionRow
          isProcessing={isProcessing}
          approveLabel={t('chat.editorWrite.confirmDelete')}
          rejectLabel={t('chat.editorWrite.cancel')}
          approveDanger
          rejectReason={rejectReason}
          showRejectInput={showRejectInput}
          onToggleRejectInput={() => setShowRejectInput((v) => !v)}
          onRejectReasonChange={setRejectReason}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      </div>
    </div>
  );
}

// ── InsertWidgetApprovalUI ────────────────────────────────────────────────────

interface InsertWidgetInput {
  editor_session_id?: string;
  widgetType?: string;
  data?: unknown;
  afterCellId?: string;
  reason?: string;
}

export function InsertWidgetApprovalUI({ toolCallId, isProcessing, onApprove, onReject, input }: EditorWriteApprovalBaseProps & { input: InsertWidgetInput }) {
  const { t } = useTranslation();
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [dataExpanded, setDataExpanded] = useState(false);

  const handleApprove = useCallback(() => { if (!isProcessing) onApprove(); }, [isProcessing, onApprove]);
  const handleReject = useCallback(() => { if (!isProcessing) onReject(rejectReason || undefined); }, [isProcessing, onReject, rejectReason]);

  useApprovalKeyboard(handleApprove, onReject, rejectReason);

  const dataPreview = input.data != null ? JSON.stringify(input.data, null, 2) : null;
  const dataKeys = input.data != null && typeof input.data === 'object' ? Object.keys(input.data as object) : [];

  return (
    <div style={cardStyle}>
      <div style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: '0.96rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>{t('chat.editorWrite.insertWidgetTitle')}</h3>
        </div>
        <p style={metaStyle}>mcp__editor__insert_widget · {toolCallId}</p>
      </div>
      <div style={bodyStyle}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
          <div>
            <LabelRow>{t('chat.editorWrite.widgetType')}</LabelRow>
            <code style={{ fontSize: '0.85rem', color: 'var(--color-action-link)', background: 'var(--color-bg-surface)', padding: '0.2rem 0.5rem', borderRadius: '6px' }}>{input.widgetType ?? '—'}</code>
          </div>
          <div>
            <LabelRow>{t('chat.editorWrite.insertPosition')}</LabelRow>
            <span style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
              {input.afterCellId ? t('chat.editorWrite.afterSegment', { id: input.afterCellId }) : t('chat.editorWrite.documentEnd')}
            </span>
          </div>
        </div>
        {dataPreview ? (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
              <span style={labelStyle}>{t('chat.editorWrite.widgetData')}</span>
              <button type="button" onClick={() => setDataExpanded((v) => !v)} style={{ border: 'none', background: 'transparent', color: 'var(--color-action-link)', fontSize: '0.75rem', cursor: 'pointer', padding: 0 }}>
                {dataExpanded ? t('chat.editorWrite.collapse') : t('chat.editorWrite.expandFields', { count: dataKeys.length })}
              </button>
            </div>
            {dataExpanded ? (
              <PreviewBox text={dataPreview} mono />
            ) : (
              <div style={{ ...previewBoxStyle, maxHeight: '3.5rem', overflow: 'hidden', color: 'var(--color-text-muted)', fontSize: '0.8rem', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' }}>
                {dataKeys.length > 0 ? `{ ${dataKeys.join(', ')} }` : dataPreview.slice(0, 120)}
              </div>
            )}
          </div>
        ) : null}
        {input.reason ? <ReasonBox reason={input.reason} /> : null}
        <ActionRow
          isProcessing={isProcessing}
          approveLabel={t('chat.editorWrite.acceptInsert')}
          rejectLabel={t('chat.editorWrite.reject')}
          rejectReason={rejectReason}
          showRejectInput={showRejectInput}
          onToggleRejectInput={() => setShowRejectInput((v) => !v)}
          onRejectReasonChange={setRejectReason}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      </div>
    </div>
  );
}

// ── ReplyToCommentApprovalUI ──────────────────────────────────────────────────

interface ReplyToCommentInput {
  editor_session_id?: string;
  commentId?: string;
  content?: string;
  reason?: string;
}

export function ReplyToCommentApprovalUI({ toolCallId, isProcessing, onApprove, onReject, input }: EditorWriteApprovalBaseProps & { input: ReplyToCommentInput }) {
  const { t } = useTranslation();
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const handleApprove = useCallback(() => { if (!isProcessing) onApprove(); }, [isProcessing, onApprove]);
  const handleReject = useCallback(() => { if (!isProcessing) onReject(rejectReason || undefined); }, [isProcessing, onReject, rejectReason]);

  useApprovalKeyboard(handleApprove, onReject, rejectReason);

  return (
    <div style={cardStyle}>
      <div style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: '0.96rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>{t('chat.editorWrite.replyCommentTitle')}</h3>
        </div>
        <p style={metaStyle}>mcp__editor__reply_to_comment · {toolCallId}</p>
      </div>
      <div style={bodyStyle}>
        {input.commentId ? (
          <div>
            <LabelRow>{t('chat.editorWrite.targetCommentId')}</LabelRow>
            <code style={{ fontSize: '0.82rem', color: 'var(--color-text-secondary)', background: 'var(--color-bg-surface)', padding: '0.2rem 0.5rem', borderRadius: '6px' }}>{input.commentId}</code>
          </div>
        ) : null}
        {input.content ? (
          <div>
            <LabelRow>{t('chat.editorWrite.replyContent')}</LabelRow>
            <PreviewBox text={input.content} />
          </div>
        ) : null}
        {input.reason ? <ReasonBox reason={input.reason} /> : null}
        <ActionRow
          isProcessing={isProcessing}
          approveLabel={t('chat.editorWrite.sendReply')}
          rejectLabel={t('chat.editorWrite.reject')}
          rejectReason={rejectReason}
          showRejectInput={showRejectInput}
          onToggleRejectInput={() => setShowRejectInput((v) => !v)}
          onRejectReasonChange={setRejectReason}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      </div>
    </div>
  );
}

// ── EditorWriteCompletedCard ──────────────────────────────────────────────────

export interface EditorWriteOutput {
  ok?: boolean;
  cellId?: string;
  reason?: string;
  error?: string;
}

interface EditorWriteCompletedCardProps {
  toolName: string;
  input: Record<string, unknown>;
  output: EditorWriteOutput;
}

const COMPLETED_LABEL_KEY: Record<string, string> = {
  'mcp__editor__write_segment': 'chat.editorWrite.completed.writeSegment',
  'mcp__editor__delete_segment': 'chat.editorWrite.completed.deleteSegment',
  'mcp__editor__insert_widget': 'chat.editorWrite.completed.insertWidget',
  'mcp__editor__reply_to_comment': 'chat.editorWrite.completed.replyComment',
};

function resolveTargetCellId(toolName: string, input: Record<string, unknown>, output: EditorWriteOutput): string | null {
  if (output.cellId) return output.cellId;
  if (typeof input.cellId === 'string') return input.cellId;
  if (toolName === 'mcp__editor__reply_to_comment' && typeof input.commentId === 'string') return input.commentId;
  return null;
}

export function EditorWriteCompletedCard({ toolName, input, output }: EditorWriteCompletedCardProps) {
  const { t } = useTranslation();
  const name = toolName.toLowerCase();
  const labelKey = COMPLETED_LABEL_KEY[name];
  const label = labelKey ? t(labelKey) : toolName;
  const isSuccess = output.ok !== false;
  const targetCellId = resolveTargetCellId(name, input, output);
  const reason = output.reason ?? (typeof input.reason === 'string' ? input.reason : undefined);

  const handleJumpToCell = () => {
    if (!targetCellId) return;
    window.dispatchEvent(new CustomEvent('editor:jump-to-cell', { detail: { cellId: targetCellId } }));
  };

  return (
    <div style={{
      overflow: 'hidden',
      borderRadius: '12px',
      border: `1px solid ${isSuccess ? 'rgba(34,197,94,0.3)' : 'rgba(217,83,79,0.3)'}`,
      background: isSuccess ? 'rgba(34,197,94,0.04)' : 'rgba(217,83,79,0.04)',
    }}>
      <div style={{
        padding: '0.7rem 1rem',
        borderBottom: `1px solid ${isSuccess ? 'rgba(34,197,94,0.15)' : 'rgba(217,83,79,0.15)'}`,
        display: 'flex',
        alignItems: 'center',
        gap: '0.55rem',
      }}>
        <span style={{ fontSize: '0.9rem', fontWeight: 600, color: isSuccess ? '#166534' : '#c0392b', flex: 1 }}>{label}</span>
        <span style={{
          fontSize: '0.72rem',
          fontWeight: 600,
          padding: '0.15rem 0.55rem',
          borderRadius: '999px',
          background: isSuccess ? 'rgba(34,197,94,0.12)' : 'rgba(217,83,79,0.12)',
          color: isSuccess ? '#166534' : '#c0392b',
        }}>
          {isSuccess ? t('chat.editorWrite.success') : t('chat.editorWrite.failure')}
        </span>
      </div>
      <div style={{ padding: '0.65rem 1rem', display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
        {targetCellId ? (
          <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
            {t('chat.editorWrite.segmentIdPrefix')}<code style={{ fontSize: '0.78rem', background: 'var(--color-bg-surface)', padding: '0.1rem 0.4rem', borderRadius: '4px', color: 'var(--color-text-secondary)' }}>{targetCellId}</code>
          </div>
        ) : null}
        {reason ? (
          <div style={{ fontSize: '0.82rem', color: 'var(--color-text-secondary)', lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as const, overflow: 'hidden' }}>
            {reason}
          </div>
        ) : null}
        {!isSuccess && output.error ? (
          <div style={{ fontSize: '0.82rem', color: '#c0392b' }}>{output.error}</div>
        ) : null}
      </div>
      {targetCellId && isSuccess ? (
        <div style={{ padding: '0 1rem 0.75rem', display: 'flex', justifyContent: 'flex-end' }}>
          <button
            type="button"
            onClick={handleJumpToCell}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.45rem 0.85rem',
              border: '1px solid rgba(34,197,94,0.35)',
              borderRadius: '8px',
              background: 'rgba(34,197,94,0.06)',
              color: '#166534',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(34,197,94,0.14)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(34,197,94,0.06)'; }}
          >
            {t('chat.editorWrite.jumpToNote')}
          </button>
        </div>
      ) : null}
    </div>
  );
}


interface EditorWriteApprovalUIProps {
  toolName: string;
  toolCallId: string;
  input: Record<string, unknown>;
  isProcessing: boolean;
  onApprove: () => void;
  onReject: (reason?: string) => void;
}

export default function EditorWriteApprovalUI({ toolName, toolCallId, input, isProcessing, onApprove, onReject }: EditorWriteApprovalUIProps) {
  const { t } = useTranslation();
  const name = toolName.toLowerCase();
  const base = { toolCallId, isProcessing, onApprove, onReject };

  if (name === 'mcp__editor__write_segment') {
    return <WriteSegmentApprovalUI {...base} input={input as WriteSegmentInput} />;
  }
  if (name === 'mcp__editor__delete_segment') {
    return <DeleteSegmentApprovalUI {...base} input={input as DeleteSegmentInput} />;
  }
  if (name === 'mcp__editor__insert_widget') {
    return <InsertWidgetApprovalUI {...base} input={input as InsertWidgetInput} />;
  }
  if (name === 'mcp__editor__reply_to_comment') {
    return <ReplyToCommentApprovalUI {...base} input={input as ReplyToCommentInput} />;
  }

  // Fallback: unknown editor write tool
  return (
    <div style={{ ...cardStyle, padding: '1rem' }}>
      <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
        {t('chat.editorWrite.fallbackTitle')}<code>{toolName}</code>
      </p>
      <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.85rem' }}>
        <button type="button" onClick={onApprove} disabled={isProcessing} style={{ flex: 1, border: 'none', borderRadius: '999px', padding: '0.75rem', background: 'var(--color-action-link)', color: 'var(--color-text-on-action)', fontWeight: 600, cursor: isProcessing ? 'not-allowed' : 'pointer' }}>
          {t('chat.editorWrite.accept')}
        </button>
        <button type="button" onClick={() => onReject()} disabled={isProcessing} style={{ flex: 1, border: '1px solid var(--color-border-paper)', borderRadius: '999px', padding: '0.75rem', background: 'var(--color-bg-paper)', color: 'var(--color-text-secondary)', fontWeight: 600, cursor: isProcessing ? 'not-allowed' : 'pointer' }}>
          {t('chat.editorWrite.reject')}
        </button>
      </div>
    </div>
  );
}

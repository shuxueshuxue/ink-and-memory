// [Input] Mermaid chart source text extracted from a ```mermaid fenced code block in chat Markdown.
// [Output] Lazily loaded mermaid SVG render with debounced streaming retries and raw-code fallback;
//          toolbar offers preview/source mode toggle, source copy, and PNG export.
// [Pos] mermaid-block component node in frontend/src/components/chat
// [Sync] 2026-07-20: created per docs/design/claude-agent/chat-markdown-mermaid.md — dynamic import
//                    singleton, strict securityLevel, base theme mapped from CSS design tokens,
//                    serialized render queue, 300ms debounce for streaming input, non-throwing fallback.
// [Sync] 2026-07-20: 新增图表工具栏（设计文档 §2.6）— 预览/源码分段切换、复用 useCopy 复制
//                    完整 ```mermaid 围栏文本、viewBox 尺寸 + 2x scale canvas 栅格化导出 PNG；
//                    渲染失败时强制源码视图。
// [Sync] 2026-07-20: i18n — toolbar labels/titles and render status copy resolve through the
//                    chat.mermaid namespace (en + zh) via useTranslation.
import { memo, useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useCopy } from '../../hooks/useCopy';
import { IconCheck, IconDownload, IconLoader } from './Icons';

type MermaidApi = typeof import('mermaid')['default'];
type ViewMode = 'preview' | 'source';

const RENDER_DEBOUNCE_MS = 300;
const EXPORT_SCALE = 2;

let mermaidSingleton: Promise<MermaidApi> | null = null;
let renderQueue: Promise<unknown> = Promise.resolve();

function cssVar(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function loadMermaid(): Promise<MermaidApi> {
  if (!mermaidSingleton) {
    mermaidSingleton = import('mermaid').then((mod) => {
      const mermaid = mod.default;
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        theme: 'base',
        themeVariables: {
          background: 'transparent',
          primaryColor: cssVar('--color-bg-paper', '#ffffff'),
          primaryTextColor: cssVar('--color-text-primary', '#1f2933'),
          primaryBorderColor: cssVar('--color-border-paper', '#d8d2c4'),
          lineColor: cssVar('--color-text-muted', '#6b7280'),
          textColor: cssVar('--color-text-primary', '#1f2933'),
          fontFamily: 'inherit',
        },
      });
      return mermaid;
    });
  }
  return mermaidSingleton;
}

// Serialize mermaid.render calls: mermaid keeps global rendering state and races
// leave orphan error elements in document.body.
function enqueueRender<T>(task: () => Promise<T>): Promise<T> {
  const run = renderQueue.then(task, task);
  renderQueue = run.then(
    () => undefined,
    () => undefined,
  );
  return run;
}

function removeOrphanRenderElement(id: string): void {
  document.getElementById(`d${id}`)?.remove();
  document.getElementById(id)?.remove();
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('svg image decode failed'));
    image.src = url;
  });
}

function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = fileName;
    anchor.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}

// Rasterize the rendered SVG into a PNG download. mermaid emits transparent SVGs
// sized via viewBox/max-width, so write explicit dimensions and paint the paper
// background before drawing.
async function exportSvgAsPng(svgMarkup: string): Promise<void> {
  const doc = new DOMParser().parseFromString(svgMarkup, 'image/svg+xml');
  const svgEl = doc.documentElement;
  const viewBox = (svgEl.getAttribute('viewBox') ?? '').split(/[\s,]+/).map(Number);
  const width = viewBox.length === 4 && viewBox[2] > 0 ? viewBox[2] : 800;
  const height = viewBox.length === 4 && viewBox[3] > 0 ? viewBox[3] : 600;
  svgEl.setAttribute('width', String(width));
  svgEl.setAttribute('height', String(height));

  const serialized = new XMLSerializer().serializeToString(svgEl);
  const url = URL.createObjectURL(new Blob([serialized], { type: 'image/svg+xml;charset=utf-8' }));
  try {
    const image = await loadImage(url);
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(width * EXPORT_SCALE);
    canvas.height = Math.round(height * EXPORT_SCALE);
    const context = canvas.getContext('2d');
    if (!context) {
      throw new Error('canvas 2d context unavailable');
    }
    context.scale(EXPORT_SCALE, EXPORT_SCALE);
    context.fillStyle = cssVar('--color-bg-paper', '#ffffff');
    context.fillRect(0, 0, width, height);
    context.drawImage(image, 0, 0, width, height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'));
    if (!blob) {
      throw new Error('png encode failed');
    }
    downloadBlob(blob, `mermaid-diagram-${Date.now()}.png`);
  } finally {
    URL.revokeObjectURL(url);
  }
}

function IconCopy() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ width: '0.95rem', height: '0.95rem' }}>
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function ToolbarButton({ title, onClick, disabled, children }: { title: string; onClick: () => void; disabled?: boolean; children: ReactNode }) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      disabled={disabled}
      style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '1.7rem', height: '1.7rem', borderRadius: '0.5rem', border: 'none', background: 'transparent', color: 'var(--color-text-muted)', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.45 : 1 }}
    >
      {children}
    </button>
  );
}

interface MermaidBlockProps {
  chart: string;
}

export default memo(function MermaidBlock({ chart }: MermaidBlockProps) {
  const { t } = useTranslation();
  const { copied, copy } = useCopy();
  const [svg, setSvg] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('preview');
  const [isExporting, setIsExporting] = useState(false);
  const instanceIdRef = useRef(`mermaid-${crypto.randomUUID()}`);
  const seqRef = useRef(0);

  useEffect(() => {
    const seq = ++seqRef.current;
    const timer = window.setTimeout(() => {
      const renderId = `${instanceIdRef.current}-${seq}`;
      loadMermaid()
        .then((mermaid) => enqueueRender(() => mermaid.render(renderId, chart)))
        .then((result) => {
          if (seqRef.current === seq) {
            setSvg(result.svg);
            setFailed(false);
          }
        })
        .catch((error: unknown) => {
          removeOrphanRenderElement(renderId);
          // Expected during streaming: the fenced block is often syntactically incomplete.
          console.warn('[MermaidBlock] render failed, showing source fallback', error);
          if (seqRef.current === seq) {
            setFailed(true);
          }
        });
    }, RENDER_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [chart]);

  const handleExport = useCallback(() => {
    if (!svg || isExporting) {
      return;
    }
    setIsExporting(true);
    exportSvgAsPng(svg)
      .catch((error: unknown) => {
        console.warn('[MermaidBlock] png export failed', error);
      })
      .finally(() => setIsExporting(false));
  }, [svg, isExporting]);

  const showPreview = viewMode === 'preview' && svg !== null;
  // Copy the complete fenced Markdown block, not just the chart source.
  const fencedMarkdown = `\`\`\`mermaid\n${chart.replace(/\n+$/, '')}\n\`\`\``;

  return (
    <div
      style={{
        margin: '0.75rem 0',
        borderRadius: '0.75rem',
        border: '1px solid var(--color-border-paper)',
        background: 'var(--color-bg-paper)',
        overflow: 'hidden',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.35rem 0.5rem', borderBottom: '1px solid var(--color-border-paper)' }}>
        <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginRight: 'auto' }}>
          {failed ? t('chat.mermaid.renderFailed') : svg ? 'Mermaid' : t('chat.mermaid.rendering')}
        </span>
        <div style={{ display: 'flex', borderRadius: '0.5rem', border: '1px solid var(--color-border-paper)', overflow: 'hidden' }}>
          {(['preview', 'source'] as const).map((mode) => {
            const active = showPreview === (mode === 'preview');
            const disabled = mode === 'preview' && svg === null;
            return (
              <button
                key={mode}
                type="button"
                disabled={disabled}
                onClick={() => setViewMode(mode)}
                style={{
                  padding: '0.15rem 0.6rem',
                  fontSize: '0.72rem',
                  border: 'none',
                  background: active ? 'var(--color-bg-surface)' : 'transparent',
                  color: active ? 'var(--color-text-primary)' : 'var(--color-text-muted)',
                  cursor: disabled ? 'not-allowed' : 'pointer',
                  opacity: disabled ? 0.45 : 1,
                }}
              >
                {mode === 'preview' ? t('chat.mermaid.preview') : t('chat.mermaid.source')}
              </button>
            );
          })}
        </div>
        <ToolbarButton title={t('chat.mermaid.copySource')} onClick={() => copy(fencedMarkdown)}>
          {copied ? <IconCheck style={{ width: '0.95rem', height: '0.95rem' }} /> : <IconCopy />}
        </ToolbarButton>
        <ToolbarButton title={t('chat.mermaid.exportPng')} onClick={handleExport} disabled={!svg || isExporting}>
          {isExporting ? <IconLoader style={{ width: '0.95rem', height: '0.95rem' }} /> : <IconDownload style={{ width: '0.95rem', height: '0.95rem' }} />}
        </ToolbarButton>
      </div>
      <div style={{ padding: '0.75rem', overflowX: 'auto' }}>
        {showPreview ? (
          <div
            style={{ display: 'flex', justifyContent: 'center', minWidth: 0 }}
            // mermaid with securityLevel 'strict' emits sanitized SVG markup.
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        ) : (
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
            <code>{chart}</code>
          </pre>
        )}
      </div>
    </div>
  );
});

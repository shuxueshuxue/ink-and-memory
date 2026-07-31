// [Input] Shared chat/dashboard icon requests and inline style props.
// [Output] SVG icon components used by chat, dashboard, file, and settings UI.
// [Pos] chat-icons component node in frontend/src/components/chat
// [Sync] 2026-05-29: add share and more icons for the theme-adaptive chat status bar.
// [Sync] 2026-06-09: add downward arrow icon for the ChatPanel scroll-to-bottom floating action.
// [Sync] 2026-06-28: add message-circle icon for the Chat history search dialog.
// [Sync] 2026-07-20: add IconPlanTasks (document + check rows) for the PlanButton
//                    "计划与待办" dual-section semantics (claude-todo §5.6).
// [Sync] 2026-07-20: add IconList (bulleted list) — PlanButton 改为纯图标按钮，
//                    文字经悬浮 tooltip 展示（claude-todo §5.6 交互修订）。
// [Sync] 2026-07-26: add shared IconCopy (lifted from AssistMessagePart) so user and
//                    assistant message bubbles reuse the same copy affordance.
import type { CSSProperties, ReactNode } from 'react';

type IconProps = { className?: string; style?: CSSProperties };

function createIcon(viewBox: string, paths: ReactNode) {
  return function Icon({ className, style }: IconProps) {
    return (
      <svg
        className={className}
        style={style}
        viewBox={viewBox}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        {paths}
      </svg>
    );
  };
}

export const IconSparkles = createIcon('0 0 24 24', <>
  <path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z" />
  <path d="M19 14l.8 2.3L22 17l-2.2.7L19 20l-.8-2.3L16 17l2.2-.7L19 14z" />
  <path d="M4 14l.8 2.3L7 17l-2.2.7L4 20l-.8-2.3L1 17l2.2-.7L4 14z" />
</>);
export const IconSearch = createIcon('0 0 24 24', <><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>);
export const IconUsers = createIcon('0 0 24 24', <><path d="M16 11c1.7 0 3-1.6 3-3.5S17.7 4 16 4s-3 1.6-3 3.5S14.3 11 16 11z" /><path d="M8 12c2.2 0 4-1.8 4-4S10.2 4 8 4 4 5.8 4 8s1.8 4 4 4z" /><path d="M2 20c0-2.2 2.5-4 5.5-4h1" /><path d="M13 16h1.5c3 0 5.5 1.8 5.5 4" /></>);
export const IconChecklist = createIcon('0 0 24 24', <><path d="M9 6h11" /><path d="M9 12h11" /><path d="M9 18h11" /><path d="M4 6l1.5 1.5L7 6" /><path d="M4 12l1.5 1.5L7 12" /><circle cx="5.5" cy="18" r="1" /></>);
export const IconUser = createIcon('0 0 24 24', <><circle cx="12" cy="8" r="4" /><path d="M4 20c1.6-3 4.5-5 8-5s6.4 2 8 5" /></>);
export const IconChevronRight = createIcon('0 0 24 24', <path d="M9 6l6 6-6 6" />);
export const IconChevronLeft = createIcon('0 0 24 24', <path d="M15 18l-6-6 6-6" />);
export const IconChevronDown = createIcon('0 0 24 24', <path d="M6 9l6 6 6-6" />);
export const IconChevronUp = createIcon('0 0 24 24', <path d="M18 15l-6-6-6 6" />);
export const IconPaperclip = createIcon('0 0 24 24', <path d="M21 12l-8.5 8.5a5 5 0 0 1-7.1-7.1L14 4.8a3.5 3.5 0 0 1 5 5L9.4 19.4" />);
export const IconImage = createIcon('0 0 24 24', <><rect x="3" y="4" width="18" height="16" rx="3" /><path d="M7 14l3-3 4 4 3-3 3 3" /><circle cx="9" cy="9" r="1.5" /></>);
export const IconCamera = createIcon('0 0 24 24', <><path d="M4 7h4l2-2h4l2 2h4v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" /><circle cx="12" cy="13" r="3.5" /></>);
export const IconSend = createIcon('0 0 24 24', <><path d="M22 2L11 13" /><path d="M22 2l-7 20-4-9-9-4 20-7z" /></>);
export const IconSettings = createIcon('0 0 24 24', <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a7.9 7.9 0 0 0 .1-2l2.1-1.6-2-3.4-2.5 1a7.8 7.8 0 0 0-1.6-.9l-.4-2.7h-4l-.4 2.7a7.8 7.8 0 0 0-1.6.9l-2.5-1-2 3.4 2.1 1.6a7.9 7.9 0 0 0 .1 2L2.5 16.6l2 3.4 2.5-1a7.8 7.8 0 0 0 1.6.9l.4 2.7h4l.4-2.7a7.8 7.8 0 0 0 1.6-.9l2.5 1 2-3.4z" /></>);
export const IconCircle = createIcon('0 0 24 24', <circle cx="12" cy="12" r="8" />);
export const IconPlus = createIcon('0 0 24 24', <><path d="M12 5v14" /><path d="M5 12h14" /></>);
export const IconTrash = createIcon('0 0 24 24', <><path d="M3 6h18" /><path d="M8 6V4h8v2" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6" /><path d="M14 11v6" /></>);
export const IconEdit = createIcon('0 0 24 24', <><path d="M12 20h9" /><path d="M16.5 3.5l4 4L7 21H3v-4L16.5 3.5z" /></>);
export const IconX = createIcon('0 0 24 24', <><path d="M18 6L6 18" /><path d="M6 6l12 12" /></>);
export const IconCheck = createIcon('0 0 24 24', <polyline points="20 6 9 17 4 12" />);
// 复制图标（双矩形）：用户/助手消息气泡共用。
export const IconCopy = createIcon('0 0 24 24', <>
  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
</>);
export const IconFile = createIcon('0 0 24 24', <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></>);
export const IconDownload = createIcon('0 0 24 24', <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></>);
export const IconLoader = createIcon('0 0 24 24', <path d="M21 12a9 9 0 1 1-6.219-8.56" />);
export const IconGrid = createIcon('0 0 24 24', <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>);
export const IconFolder = createIcon('0 0 24 24', <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />);
export const IconClock = createIcon('0 0 24 24', <><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></>);
export const IconEnvelope = createIcon('0 0 24 24', <><rect x="2" y="4" width="20" height="16" rx="2" /><path d="M22 4l-10 8L2 4" /></>);
export const IconCalendar = createIcon('0 0 24 24', <><rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></>);
export const IconDatabase = createIcon('0 0 24 24', <><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M21 12c0 1.66-4.03 3-9 3s-9-1.34-9-3" /><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" /></>);
export const IconTasks = createIcon('0 0 24 24', <><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></>);
// 文档 + 勾选组合：表达 PlanButton「计划与待办」双区语义（claude-todo §5.6）。
export const IconPlanTasks = createIcon('0 0 24 24', <>
  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
  <polyline points="14 2 14 8 20 8" />
  <path d="M7.5 12.5l1.5 1.5 2.5-2.5" />
  <path d="M13.5 13h3.5" />
  <path d="M7.5 17l1.5 1.5 2.5-2.5" />
  <path d="M13.5 17.5h3.5" />
</>);
// 纯列表图标（圆点 + 三行）：PlanButton 纯图标按钮形态使用。
export const IconList = createIcon('0 0 24 24', <>
  <circle cx="4.5" cy="6" r="1" />
  <circle cx="4.5" cy="12" r="1" />
  <circle cx="4.5" cy="18" r="1" />
  <path d="M9 6h11" />
  <path d="M9 12h11" />
  <path d="M9 18h11" />
</>);
export const IconTable = createIcon('0 0 24 24', <><rect x="3" y="3" width="18" height="18" rx="2" /><line x1="3" y1="9" x2="21" y2="9" /><line x1="3" y1="15" x2="21" y2="15" /><line x1="9" y1="3" x2="9" y2="21" /></>);
export const IconMoreHorizontal = createIcon('0 0 24 24', <><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></>);
export const IconMessageCircle = createIcon('0 0 24 24', <><path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.7 8.7 0 0 1-7.8 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.5a8.4 8.4 0 0 1-.9-3.8 8.7 8.7 0 0 1 4.7-7.8 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5z" /></>);
export const IconShare = createIcon('0 0 24 24', <><path d="M4 12v7a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7" /><path d="M16 6l-4-4-4 4" /><path d="M12 2v14" /></>);
export const IconSun = createIcon('0 0 24 24', <><circle cx="12" cy="12" r="5" /><line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" /><line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" /><line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" /><line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" /></>);
export const IconMoon = createIcon('0 0 24 24', <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />);
export const IconMonitor = createIcon('0 0 24 24', <><rect x="2" y="3" width="20" height="14" rx="2" /><line x1="8" y1="21" x2="16" y2="21" /><line x1="12" y1="17" x2="12" y2="21" /></>);
export const IconArrowUp = createIcon('0 0 24 24', <><line x1="12" y1="19" x2="12" y2="5" /><polyline points="5 12 12 5 19 12" /></>);
export const IconArrowDown = createIcon('0 0 24 24', <><line x1="12" y1="5" x2="12" y2="19" /><polyline points="5 12 12 19 19 12" /></>);

export function IconStop({ className, style }: IconProps) {
  return (
    <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  );
}

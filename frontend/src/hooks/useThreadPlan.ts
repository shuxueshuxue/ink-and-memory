// [Input] plan-mode-changed / plan-updated SSE 事件（经 claude-agent-transport convertEvent 转发）
//         与 GET /api/claude-agent/threads/{thread_id}/plan REST 水合响应。
// [Output] 按 threadId 键控的轻量 plan store：useThreadPlan 订阅、applyPlanEvent 事件写入、
//          hydrateThreadPlan REST 水合（含截断内容的全量拉取）。
// [Pos] claude-plan store hook in frontend/src/hooks
// [Sync] 2026-07-20: 初版 — 依据 docs/design/claude-agent/claude-plan.md §5.4-5.6 实现；
//                    plan-* SSE 帧不产生消息气泡，全部状态经本 store 流向 PlanPanel。

import { useSyncExternalStore } from 'react';
import { getAuthToken } from '../contexts/AuthContext';
import { apiUrl } from '../lib/apiBase';

// ---------------------------------------------------------------------------
// State shapes (mirrors docs/design/claude-agent/claude-plan.md §5.2/§5.4/§5.5)
// ---------------------------------------------------------------------------

export type ThreadPlanMode = 'none' | 'planning' | 'exited';

export interface ThreadPlanState {
  planMode: ThreadPlanMode;
  exists: boolean;
  slug: string | null;
  fileName: string | null;
  content: string | null;
  contentBytes: number;
  truncated: boolean;
  updatedAt: string | null;
}

/** Raw plan-* SSE frames forwarded by claude-agent-transport (§5.4). */
export type ThreadPlanEvent =
  | {
      type: 'plan-mode-changed';
      planMode: 'planning' | 'exited';
      toolCallId?: string;
    }
  | {
      type: 'plan-updated';
      slug: string;
      fileName: string;
      content: string;
      contentBytes: number;
      truncated?: boolean;
      updatedAt?: string;
    };

/** REST payload of GET /api/claude-agent/threads/{thread_id}/plan (§5.5). */
interface ThreadPlanApiResponse {
  thread_id: string;
  plan_mode?: ThreadPlanMode | null;
  exists: boolean;
  slug: string | null;
  file_name: string | null;
  content: string | null;
  content_bytes: number | null;
  truncated: boolean | null;
  updated_at: string | null;
}

const EMPTY_THREAD_PLAN: ThreadPlanState = Object.freeze({
  planMode: 'none',
  exists: false,
  slug: null,
  fileName: null,
  content: null,
  contentBytes: 0,
  truncated: false,
  updatedAt: null,
});

// ---------------------------------------------------------------------------
// Context-free keyed store (module singleton, per-thread listeners)
// ---------------------------------------------------------------------------

const planByThreadId = new Map<string, ThreadPlanState>();
const listenersByThreadId = new Map<string, Set<() => void>>();

function getThreadPlan(threadId: string): ThreadPlanState {
  return planByThreadId.get(threadId) ?? EMPTY_THREAD_PLAN;
}

function setThreadPlan(threadId: string, next: ThreadPlanState): void {
  planByThreadId.set(threadId, next);
  const listeners = listenersByThreadId.get(threadId);
  if (!listeners) return;
  for (const listener of listeners) {
    listener();
  }
}

function subscribeThreadPlan(threadId: string, listener: () => void): () => void {
  let listeners = listenersByThreadId.get(threadId);
  if (!listeners) {
    listeners = new Set();
    listenersByThreadId.set(threadId, listeners);
  }
  listeners.add(listener);
  return () => {
    const current = listenersByThreadId.get(threadId);
    if (!current) return;
    current.delete(listener);
    if (current.size === 0) {
      listenersByThreadId.delete(threadId);
    }
  };
}

/**
 * Subscribe to the plan state of one thread. Returns a stable frozen
 * EMPTY_THREAD_PLAN when the thread has no recorded plan yet.
 */
export function useThreadPlan(threadId: string | null | undefined): ThreadPlanState {
  const key = threadId ?? '';
  return useSyncExternalStore(
    (listener) => subscribeThreadPlan(key, listener),
    () => getThreadPlan(key),
  );
}

/**
 * Apply a plan-* SSE frame to the store. Lifecycle frames never become
 * UIMessageChunks (§5.4 收集策略: 不收集); they only mutate this store.
 */
export function applyPlanEvent(threadId: string, event: ThreadPlanEvent): void {
  if (!threadId) return;
  const prev = getThreadPlan(threadId);

  if (event.type === 'plan-mode-changed') {
    setThreadPlan(threadId, { ...prev, planMode: event.planMode });
    return;
  }

  if (event.type === 'plan-updated') {
    setThreadPlan(threadId, {
      ...prev,
      exists: true,
      slug: event.slug ?? null,
      fileName: event.fileName ?? null,
      content: event.content ?? null,
      contentBytes: event.contentBytes ?? 0,
      truncated: event.truncated === true,
      updatedAt: event.updatedAt ?? prev.updatedAt,
    });
  }
}

/**
 * Hydrate (or refresh) the store from GET /api/claude-agent/threads/{id}/plan.
 * Used on initial load / reconnect and by the "load full content" affordance
 * when an SSE snapshot arrived truncated (§5.4 truncated → §5.5 拉全量).
 * Fetch failures leave the current state untouched.
 */
export async function hydrateThreadPlan(threadId: string): Promise<void> {
  if (!threadId) return;
  try {
    const res = await fetch(
      apiUrl(`/api/claude-agent/threads/${encodeURIComponent(threadId)}/plan`),
      { headers: { 'Authorization': `Bearer ${getAuthToken()}` } },
    );
    if (!res.ok) return;
    const data = (await res.json()) as ThreadPlanApiResponse;
    const prev = getThreadPlan(threadId);

    if (!data.exists) {
      // §5.5: exists:false 时 slug/file_name/content/updated_at 为 null，
      // plan_mode 仍返回内存态或 "none"。
      setThreadPlan(threadId, {
        planMode: data.plan_mode ?? 'none',
        exists: false,
        slug: null,
        fileName: null,
        content: null,
        contentBytes: 0,
        truncated: false,
        updatedAt: null,
      });
      return;
    }

    setThreadPlan(threadId, {
      planMode: data.plan_mode ?? prev.planMode,
      exists: true,
      slug: data.slug ?? null,
      fileName: data.file_name ?? null,
      content: data.content ?? null,
      contentBytes: data.content_bytes ?? 0,
      truncated: data.truncated === true,
      updatedAt: data.updated_at ?? null,
    });
  } catch {
    // Network/parse failure: keep existing state, panel simply stays stale.
  }
}

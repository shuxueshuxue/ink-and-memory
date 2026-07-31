// [Input] todo-updated SSE 事件（经 claude-agent-transport convertEvent 转发）
//         与 GET /api/claude-agent/threads/{thread_id}/todos REST 水合响应。
// [Output] 按 threadId 键控的轻量 todos store：useThreadTodos 订阅、applyTodoEvent 事件写入、
//          hydrateThreadTodos REST 水合（v2 文件系统重建 / v1 内存态回退）。
// [Pos] claude-todo store hook in frontend/src/hooks
// [Sync] 2026-07-20: 初版 — 依据 docs/design/claude-agent/claude-todo.md §5.4-5.6 实现；
//                    todo-updated SSE 帧不产生消息气泡，全部状态经本 store 流向 PlanButton
//                    弹层「待办」分区。结构复刻 useThreadPlan.ts。

import { useSyncExternalStore } from 'react';
import { getAuthToken } from '../contexts/AuthContext';
import { apiUrl } from '../lib/apiBase';

// ---------------------------------------------------------------------------
// State shapes (mirrors docs/design/claude-agent/claude-todo.md §5.2/§5.4/§5.5)
// ---------------------------------------------------------------------------

export type ThreadTodoSource = 'todo_write' | 'task_v2';

export type ThreadTodoStatus = 'pending' | 'in_progress' | 'completed';

/** 统一 TodoItem 模型（claude-todo.md §5.2）。 */
export interface ThreadTodoItem {
  id: string;
  content: string;
  status: ThreadTodoStatus;
  active_form: string | null;
  owner: string | null;
  blocked_by: string[];
}

export interface ThreadTodoState {
  source: ThreadTodoSource | null;
  exists: boolean;
  todos: ThreadTodoItem[];
  truncated: boolean;
  updatedAt: string | null;
}

/** Raw todo-updated SSE frame forwarded by claude-agent-transport (§5.4). */
export interface ThreadTodoEvent {
  type: 'todo-updated';
  source: ThreadTodoSource | null;
  todos: ThreadTodoItem[];
  truncated?: boolean;
  updatedAt?: string | null;
}

/** REST payload of GET /api/claude-agent/threads/{thread_id}/todos (§5.5). */
interface ThreadTodosApiResponse {
  thread_id: string;
  source: ThreadTodoSource | null;
  exists: boolean;
  todos: ThreadTodoItem[];
  truncated: boolean | null;
  updated_at: string | null;
}

const EMPTY_THREAD_TODOS: ThreadTodoState = Object.freeze({
  source: null,
  exists: false,
  todos: [],
  truncated: false,
  updatedAt: null,
});

// ---------------------------------------------------------------------------
// Context-free keyed store (module singleton, per-thread listeners)
// ---------------------------------------------------------------------------

const todosByThreadId = new Map<string, ThreadTodoState>();
const listenersByThreadId = new Map<string, Set<() => void>>();

function getThreadTodos(threadId: string): ThreadTodoState {
  return todosByThreadId.get(threadId) ?? EMPTY_THREAD_TODOS;
}

function setThreadTodos(threadId: string, next: ThreadTodoState): void {
  todosByThreadId.set(threadId, next);
  const listeners = listenersByThreadId.get(threadId);
  if (!listeners) return;
  for (const listener of listeners) {
    listener();
  }
}

function subscribeThreadTodos(threadId: string, listener: () => void): () => void {
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
 * Subscribe to the todo state of one thread. Returns a stable frozen
 * EMPTY_THREAD_TODOS when the thread has no recorded todos yet.
 */
export function useThreadTodos(threadId: string | null | undefined): ThreadTodoState {
  const key = threadId ?? '';
  return useSyncExternalStore(
    (listener) => subscribeThreadTodos(key, listener),
    () => getThreadTodos(key),
  );
}

/**
 * Apply a todo-updated SSE frame to the store. Lifecycle frames never become
 * UIMessageChunks (§5.4 收集策略: 不收集); they only mutate this store.
 */
export function applyTodoEvent(threadId: string, event: ThreadTodoEvent): void {
  if (!threadId) return;
  if (event.type !== 'todo-updated') return;
  setThreadTodos(threadId, {
    source: event.source ?? null,
    exists: true,
    todos: Array.isArray(event.todos) ? event.todos : [],
    truncated: event.truncated === true,
    updatedAt: event.updatedAt ?? null,
  });
}

/**
 * Hydrate (or refresh) the store from GET /api/claude-agent/threads/{id}/todos.
 * Used on initial load / reconnect (与 hydrateThreadPlan 并行, §5.6).
 * Fetch failures leave the current state untouched.
 */
export async function hydrateThreadTodos(threadId: string): Promise<void> {
  if (!threadId) return;
  try {
    const res = await fetch(
      apiUrl(`/api/claude-agent/threads/${encodeURIComponent(threadId)}/todos`),
      { headers: { 'Authorization': `Bearer ${getAuthToken()}` } },
    );
    if (!res.ok) return;
    const data = (await res.json()) as ThreadTodosApiResponse;

    if (!data.exists) {
      // §5.5: exists:false 时 source/todos/updated_at 为空。
      setThreadTodos(threadId, {
        source: null,
        exists: false,
        todos: [],
        truncated: false,
        updatedAt: null,
      });
      return;
    }

    setThreadTodos(threadId, {
      source: data.source ?? null,
      exists: true,
      todos: Array.isArray(data.todos) ? data.todos : [],
      truncated: data.truncated === true,
      updatedAt: data.updated_at ?? null,
    });
  } catch {
    // Network/parse failure: keep existing state, panel simply stays stale.
  }
}

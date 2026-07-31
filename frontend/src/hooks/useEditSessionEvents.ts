// [Input] Auth token storage, runtime API base config, and edit-session sync constants.
// [Output] useEditSessionEvents hook that streams authenticated /api/sessions/events frames.
// [Pos] edit-session SSE hook in frontend/src/hooks
// [Sync] 2026-06-14: add fetch-based Edit Session SSE subscription for Agent MCP write sync.

import { useEffect, useRef } from 'react';
import { STORAGE_KEYS } from '../constants/storageKeys';
import { SESSION_EVENT_RECONNECT_DELAY_MS } from '../constants/sessionSync';
import { apiUrl } from '../lib/apiBase';

export type EditSessionEvent = {
  type: 'connected' | 'session_updated' | 'session_deleted';
  sessionId?: string;
  source?: 'api' | 'agent';
  toolCallId?: string;
  toolName?: string;
  timestamp?: string;
};

interface EditSessionEventHandlers {
  onEvent: (event: EditSessionEvent) => void;
  onConnectionChange?: (connected: boolean) => void;
}

function splitSseFrames(buffer: string): { frames: string[]; buffer: string } {
  const parts = buffer.split('\n\n');
  const tail = parts.pop() ?? '';
  return {
    frames: parts.filter((frame) => frame.trim() && !frame.startsWith(':')),
    buffer: tail,
  };
}

function parseSseFrame(frame: string): EditSessionEvent | null {
  let eventType = '';
  const dataLines: string[] = [];

  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) {
      eventType = line.slice('event:'.length).trim();
      continue;
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trim());
    }
  }

  const dataText = dataLines.join('\n');
  if (!dataText) return eventType ? { type: eventType as EditSessionEvent['type'] } : null;

  try {
    const parsed = JSON.parse(dataText) as Partial<EditSessionEvent>;
    const type = parsed.type ?? eventType;
    if (!type) return null;
    return { ...parsed, type: type as EditSessionEvent['type'] };
  } catch {
    return null;
  }
}

async function consumeEditSessionEventStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onEvent: (event: EditSessionEvent) => void,
): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const drained = splitSseFrames(buffer);
    buffer = drained.buffer;

    for (const frame of drained.frames) {
      const event = parseSseFrame(frame);
      if (event) onEvent(event);
    }
  }

  const tail = decoder.decode();
  if (tail) buffer += tail;
  if (buffer.trim() && !buffer.startsWith(':')) {
    const event = parseSseFrame(buffer);
    if (event) onEvent(event);
  }
}

export function useEditSessionEvents(
  enabled: boolean,
  handlers: EditSessionEventHandlers,
) {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    if (!enabled) return;

    let stopped = false;
    let controller: AbortController | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let resolveReconnect: (() => void) | null = null;

    const waitBeforeReconnect = () =>
      new Promise<void>((resolve) => {
        resolveReconnect = resolve;
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          resolveReconnect = null;
          resolve();
        }, SESSION_EVENT_RECONNECT_DELAY_MS);
      });

    const run = async () => {
      while (!stopped) {
        const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
        if (!token) return;

        controller = new AbortController();
        try {
          const response = await fetch(apiUrl('/api/sessions/events'), {
            headers: {
              Accept: 'text/event-stream',
              Authorization: `Bearer ${token}`,
            },
            signal: controller.signal,
          });
          if (!response.ok || !response.body) {
            throw new Error(`Edit Session event stream failed: ${response.status}`);
          }

          handlersRef.current.onConnectionChange?.(true);
          await consumeEditSessionEventStream(
            response.body.getReader(),
            (event) => handlersRef.current.onEvent(event),
          );
        } catch (error) {
          if (!stopped) {
            console.warn('[EditSessionEvents] stream disconnected; reconnecting', error);
          }
        } finally {
          handlersRef.current.onConnectionChange?.(false);
          controller = null;
        }

        if (!stopped) {
          await waitBeforeReconnect();
        }
      }
    };

    void run();

    return () => {
      stopped = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      resolveReconnect?.();
      resolveReconnect = null;
      controller?.abort();
      handlersRef.current.onConnectionChange?.(false);
    };
  }, [enabled]);
}

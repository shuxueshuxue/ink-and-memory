// [Input] Consume ClaudeAgentChatTransport, WorkspaceContext, chat schema/types, file proxy utilities, AIInputDock/helpers, ChatMessageList, and auth token.
//         reconnectStreamNonce from ChatView; claude-agent-sse-utils for stream replay.
// [Output] Coordinate chat transport, pending attachments/tool choice, message state, scrolling, and input/message layout.
// [Pos] chat-panel component node in frontend/src/components/chat
// [Sync] 2026-05-25: stop forwarding frontend customer context into chat requests.
// [Sync] 2026-05-26: hide the empty message surface until chat content or an error exists.
// [Sync] 2026-05-27: forward currentToolChoice to ChatMessageList so manual-mode tool approvals are shown inline.
// [Sync] 2026-05-29: accept editorState prop and forward as editor_state in prepareSendMessagesRequest body.
// [Sync] 2026-05-29: default resume=true in every claude-agent request body.
// [Sync] 2026-05-30: fix shouldShowLoadingIndicator — include reasoning parts as visible so "Thinking…" footer doesn't show alongside inline reasoning block.
// [Sync] 2026-05-29: add onEditorWriteConfirmed prop; forward to ChatMessageList.
// [Sync] 2026-05-29: let the input dock fill the available chat page width.
// [Sync] 2026-06-01: accept queuedToolChoice so lazy-created first-turn ChatView sends preserve the selected tool mode.
// [Sync] 2026-06-09: read system_config.im_full_access_enabled; hide manual
//                    approvals by forcing chat UI tool mode to auto when enabled.
// [Sync] 2026-06-09: subscribe to same-tab IM full-access config events so
//                    Settings changes update active Chat panels immediately.
// [Sync] 2026-06-09: SSE reconnect — subscribe GET /threads/{id}/stream when reconnectStreamNonce bumps.
// [Sync] 2026-06-09: keep reconnect effect deps stable (threadId/nonce only) so parent re-renders do not abort stream.
// [Sync] 2026-06-09: agentBusy drives input dock stop button (streaming/submitted/reconnect).
// [Sync] 2026-06-09: show a floating scroll-to-bottom arrow above AIInputDock when the message list is scrolled away from the bottom.
// [Sync] 2026-06-12: use centralized API_BASE for cross-origin chat transport and SSE reconnect.
// [Sync] 2026-06-14: forward editor write toolCallId for event-driven Writing view reload de-duplication.
// [Sync] 2026-06-22: respect Workspace Mode by withholding workspaceSessionId
//                    from the input dock when workspace is disabled.
// [Sync] 2026-06-25: stop button now calls the backend thread stop endpoint
//                    instead of only aborting the local browser stream.
// [Sync] 2026-07-20: pass threadId into ClaudeAgentChatTransport so plan-* SSE
//                    frames route to the useThreadPlan store (claude-plan feature).
// [Sync] 2026-07-20: forward todo-updated SSE frames to the useThreadTodos store
//                    on the reconnect path (claude-todo §5.6).
// [Sync] 2026-07-20: derive pendingConfirmation from messages and swap AIInputDock for
//                    ToolConfirmationDock while a confirmation is pending (the composer
//                    hides until the user decides); inline approval/askuser UIs removed
//                    from the message list (design: claude-agent-tool-confirmation-flow.md §8).
// [Sync] 2026-07-20: i18n — scroll-to-bottom aria/title resolves through chat.panel.scrollToBottom.
// [Sync] 2026-07-23: SandboxPermissionRequest — pendingConfirmation carries the backend
//                    networkRequest metadata for kind==='sandbox-network' so ToolConfirmationDock
//                    renders the network-variant card (claude-agent-sandbox-network-permission-tool.md §5).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useChat } from '@ai-sdk/react';
import {
  getToolName,
  isToolUIPart,
  type DynamicToolUIPart,
  type FileUIPart,
  type TextUIPart,
  type ToolUIPart,
  type UIMessage,
} from 'ai';
import { ClaudeAgentChatTransport } from '../../lib/claude-agent-transport';
import { useWorkspaceSession } from '../../contexts/WorkspaceContext';
import {
  type ChatApiSchemaRequestBody,
  type ChatAttachment,
  type ChatModel,
  type ToolChoice,
  DEFAULT_CHAT_MODEL,
} from '../../lib/chat-schema';
import { toFileProxyUrl } from '../../lib/toFileProxyUrl';
import {
  type Attachment,
  toAttachment,
} from './AIInputDock.helpers';
import AIInputDock from './AIInputDock';
import ChatMessageList from './ChatMessageList';
import ToolConfirmationDock from './ToolConfirmationDock';
import {
  resolvePendingToolConfirmation,
  resolveSandboxNetworkRequest,
  resolveToolName,
  type PendingToolConfirmation,
} from './toolConfirmation';
import { getAuthToken } from '../../contexts/AuthContext';
import { subscribeImFullAccessChanged } from '../../lib/system-config-events';
import {
  applyBackendEventToMessages,
  consumeClaudeAgentSseStream,
} from '../../lib/claude-agent-sse-utils';
import { applyPlanEvent, type ThreadPlanEvent } from '../../hooks/useThreadPlan';
import { applyTodoEvent, type ThreadTodoEvent } from '../../hooks/useThreadTodos';
import { IconArrowDown } from './Icons';
import { API_BASE } from '../../lib/apiBase';
const CHAT_BOTTOM_PROXIMITY_PX = 120;

interface SystemConfigData {
  provider?: string;
  model?: string;
  system_prompt?: string;
  im_full_access_enabled?: boolean;
}

interface SystemConfigResponse {
  data?: SystemConfigData;
  provider?: string;
  model?: string;
  system_prompt?: string;
  im_full_access_enabled?: boolean;
}

interface ChatPanelProps {
  threadId: string;
  initialMessages?: UIMessage[];
  isLoading?: boolean;
  /** Incremented by ChatView when /status reports lifecycle=running — triggers SSE reconnect. */
  reconnectStreamNonce?: number;
  /** Called after reconnect stream finishes so parent can reload persisted messages. */
  onReconnectComplete?: () => void;
  className?: string;
  inputPlaceholder?: string;
  queuedPrompt?: string;
  queuedAttachments?: Attachment[];
  queuedToolChoice?: ToolChoice;
  queuedPromptNonce?: number;
  openFileDialogSignal?: number;
  onConversationStart?: () => void;
  /** Current EditorState snapshot forwarded to the backend agent runner via editor_state request field. */
  editorState?: Record<string, unknown> | null;
  /** Called after an editor write tool is confirmed so the Writing view can reload from the database. */
  onEditorWriteConfirmed?: (toolCallId: string) => void;
  /** Voice / deck system prompt injected as voice_context into each user message. */
  voiceSystemPrompt?: string;
}

function normalizeSystemConfig(payload: SystemConfigResponse): SystemConfigData | undefined {
  if (payload.data) {
    return payload.data;
  }
  if (
    payload.provider ||
    payload.model ||
    payload.system_prompt ||
    payload.im_full_access_enabled !== undefined
  ) {
    return payload;
  }
  return undefined;
}

export default function ChatPanel({
  threadId,
  initialMessages,
  isLoading = false,
  reconnectStreamNonce = 0,
  onReconnectComplete,
  className,
  inputPlaceholder = 'Press i to chat',
  queuedPrompt,
  queuedAttachments = [],
  queuedToolChoice = 'auto',
  queuedPromptNonce,
  openFileDialogSignal,
  onConversationStart,
  editorState,
  onEditorWriteConfirmed,
  voiceSystemPrompt,
}: ChatPanelProps) {
  const { t } = useTranslation();
  const pendingDataRef = useRef<{
    rawAttachments: Attachment[];
    toolChoice: ToolChoice;
  } | null>(null);
  const [currentToolChoice, setCurrentToolChoice] = useState<ToolChoice>('auto');
  const [systemConfig, setSystemConfig] = useState<SystemConfigData>();
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);
  const hasInitializedRef = useRef(false);
  const lastQueuedNonceRef = useRef<number | undefined>(undefined);
  const lastReconnectNonceRef = useRef(0);
  const onReconnectCompleteRef = useRef(onReconnectComplete);
  const setMessagesRef = useRef<
    ((value: UIMessage[] | ((messages: UIMessage[]) => UIMessage[])) => void) | null
  >(null);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const reconnectAbortRef = useRef<AbortController | null>(null);
  const { setActiveSessionId, workspaceEnabled } = useWorkspaceSession();

  onReconnectCompleteRef.current = onReconnectComplete;

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/system-config`, {
          headers: { 'Authorization': `Bearer ${getAuthToken()}` },
        });
        if (!response.ok) {
          return;
        }
        const payload = (await response.json()) as SystemConfigResponse;
        if (active) {
          setSystemConfig(normalizeSystemConfig(payload));
        }
      } catch {
        // ignore config fetch errors
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    return subscribeImFullAccessChanged((enabled) => {
      setSystemConfig((current) => ({
        ...(current ?? {}),
        im_full_access_enabled: enabled,
      }));
      if (enabled) {
        setCurrentToolChoice('auto');
      }
    });
  }, []);

  const getPendingData = () => pendingDataRef.current;
  const imFullAccessEnabled = systemConfig?.im_full_access_enabled === true;

  const { messages, sendMessage, setMessages, status, error, addToolResult, stop } = useChat({
    id: threadId,
    transport: new ClaudeAgentChatTransport({
      threadId,
      api: `${API_BASE}/api/claude-agent`,
      headers: () => ({ 'Authorization': `Bearer ${getAuthToken()}` }),
      prepareSendMessagesRequest: ({ messages: outgoingMessages, body, id }) => {
        const lastMessage = outgoingMessages.at(-1) as UIMessage | undefined;
        if (!lastMessage) {
          return { body: body ?? {} };
        }

        const attachments: ChatAttachment[] = (getPendingData()?.rawAttachments ?? [])
          .filter((file) => file.storageKey)
          .map((file) => ({
            type: 'file',
            url: toFileProxyUrl(file.storageKey!),
            storageKey: file.storageKey,
            mediaType: file.type,
            filename: file.name,
            size: file.size,
            workspacePath: file.workspacePath,
            savedAt: file.savedAt,
            hash: file.hash,
          }));

        const resolvedChatModel: ChatModel = systemConfig?.provider && systemConfig?.model
          ? { provider: systemConfig.provider, model: systemConfig.model }
          : DEFAULT_CHAT_MODEL;

        const requestToolChoice: ToolChoice = imFullAccessEnabled
          ? 'auto'
          : getPendingData()?.toolChoice ?? currentToolChoice;

        const requestBody: ChatApiSchemaRequestBody = {
          id,
          resume: true,
          message: lastMessage,
          chatModel: resolvedChatModel,
          toolChoice: requestToolChoice,
          allowedAppDefaultToolkit: [],
          allowedMcpServers: {},
          attachments,
          systemPrompt: voiceSystemPrompt ?? systemConfig?.system_prompt,
          ...(editorState != null ? { editor_state: editorState } : {}),
        };

        setTimeout(() => {
          pendingDataRef.current = null;
        }, 0);
        return { body: requestBody };
      },
    }),
    generateId: () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`,
    experimental_throttle: 100,
  });

  setMessagesRef.current = setMessages;

  useEffect(() => {
    setActiveSessionId(threadId);
    return () => {
      setActiveSessionId((current) => (current === threadId ? null : current));
    };
  }, [setActiveSessionId, threadId]);

  // Initialise the chat with messages provided by the parent (following the
  // better-chatbot pattern: parent fetches history, passes as initialMessages).
  useEffect(() => {
    if (hasInitializedRef.current) {
      return;
    }
    if (!initialMessages) {
      return;
    }
    if (initialMessages.length > 0) {
      setMessages(initialMessages);
    }
    hasInitializedRef.current = true;
  }, [initialMessages, setMessages]);

  useEffect(() => {
    if (!queuedPromptNonce || queuedPromptNonce === lastQueuedNonceRef.current) {
      return;
    }
    if (!queuedPrompt?.trim() && queuedAttachments.length === 0) {
      return;
    }
    lastQueuedNonceRef.current = queuedPromptNonce;

    void (async () => {
      onConversationStart?.();
      setCurrentToolChoice(queuedToolChoice);
      pendingDataRef.current = {
        rawAttachments: queuedAttachments,
        toolChoice: queuedToolChoice,
      };

      const validFiles = queuedAttachments.filter((file) => file.storageKey);
      const queuedMessageParts: Array<FileUIPart | TextUIPart> = validFiles.map((file) => ({
        type: 'file',
        url: toFileProxyUrl(file.storageKey!),
        mediaType: file.type,
        filename: file.name,
      } as FileUIPart));

      if (queuedPrompt?.trim()) {
        queuedMessageParts.push({ type: 'text', text: queuedPrompt.trim() } as TextUIPart);
      }

      if (queuedMessageParts.length === 0) {
        return;
      }
      await sendMessage({ role: 'user', parts: queuedMessageParts });
    })();
  }, [onConversationStart, queuedAttachments, queuedPrompt, queuedPromptNonce, queuedToolChoice, sendMessage]);

  useEffect(() => {
    if (!reconnectStreamNonce || reconnectStreamNonce === lastReconnectNonceRef.current) {
      return;
    }
    lastReconnectNonceRef.current = reconnectStreamNonce;

    const abort = new AbortController();
    reconnectAbortRef.current = abort;
    const activeThreadId = threadId;
    let finished = false;

    const finishReconnect = () => {
      if (finished) return;
      finished = true;
      setIsReconnecting(false);
      onReconnectCompleteRef.current?.();
    };

    setIsReconnecting(true);

    void (async () => {
      try {
        const response = await fetch(
          `${API_BASE}/api/claude-agent/threads/${encodeURIComponent(activeThreadId)}/stream`,
          {
            headers: { Authorization: `Bearer ${getAuthToken()}` },
            signal: abort.signal,
          },
        );
        if (!response.ok || !response.body) {
          finishReconnect();
          return;
        }

        const reader = response.body.getReader();
        await consumeClaudeAgentSseStream(reader, (event) => {
          if (event.type === 'finish' || event.type === 'error') {
            finishReconnect();
            return false;
          }
          // plan-* 生命周期帧不产生消息气泡，转发 plan store（claude-plan.md §5.4）。
          if (event.type === 'plan-mode-changed' || event.type === 'plan-updated') {
            applyPlanEvent(activeThreadId, event as unknown as ThreadPlanEvent);
            return;
          }
          // todo-updated 生命周期帧不产生消息气泡，转发 todos store（claude-todo.md §5.4）。
          if (event.type === 'todo-updated') {
            applyTodoEvent(activeThreadId, event as unknown as ThreadTodoEvent);
            return;
          }
          const applyMessages = setMessagesRef.current;
          if (!applyMessages) {
            return;
          }
          applyMessages((current) => applyBackendEventToMessages(current, event));
        });
        finishReconnect();
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          setIsReconnecting(false);
          return;
        }
        finishReconnect();
      } finally {
        if (reconnectAbortRef.current === abort) {
          reconnectAbortRef.current = null;
        }
      }
    })();

    return () => {
      abort.abort();
      if (reconnectAbortRef.current === abort) {
        reconnectAbortRef.current = null;
      }
      if (!finished) {
        setIsReconnecting(false);
      }
    };
  }, [reconnectStreamNonce, threadId]);

  const agentBusy = status === 'streaming' || status === 'submitted' || isReconnecting || isStopping;
  const chatLoading = agentBusy || isLoading;

  const handleStop = useCallback(async () => {
    if (isStopping) {
      return;
    }
    setIsStopping(true);
    reconnectAbortRef.current?.abort();
    reconnectAbortRef.current = null;
    setIsReconnecting(false);
    stop();
    try {
      await fetch(
        `${API_BASE}/api/claude-agent/threads/${encodeURIComponent(threadId)}/stop`,
        {
          method: 'POST',
          headers: { Authorization: `Bearer ${getAuthToken()}` },
        },
      );
    } catch {
      // The local stream is already stopped; the next status check/reconnect
      // will reconcile whether the backend turn is still running.
    } finally {
      setIsStopping(false);
      onReconnectCompleteRef.current?.();
    }
  }, [isStopping, stop, threadId]);
  const shouldShowMessageSurface = messages.length > 0 || Boolean(error) || chatLoading;

  const effectiveToolChoice: ToolChoice = imFullAccessEnabled ? 'auto' : currentToolChoice;

  // Derive the earliest tool part that is waiting on a user decision. The
  // confirmation UI (approve/reject or AskUserQuestion form) floats above the
  // input dock instead of rendering inline in the message list.
  const pendingConfirmation = useMemo<PendingToolConfirmation | null>(() => {
    for (const message of messages) {
      const parts = message.parts ?? [];
      for (let partIndex = 0; partIndex < parts.length; partIndex += 1) {
        const part = parts[partIndex];
        if (!isToolUIPart(part)) continue;
        const toolPart = part as ToolUIPart | DynamicToolUIPart;
        const kind = resolvePendingToolConfirmation(toolPart, effectiveToolChoice);
        if (!kind) continue;
        return {
          kind,
          partKey: `${message.id}-${partIndex}`,
          toolCallId: toolPart.toolCallId,
          toolName: resolveToolName(toolPart) || getToolName(toolPart),
          title: 'title' in toolPart ? (toolPart as { title?: string }).title : undefined,
          input: 'input' in toolPart ? toolPart.input : undefined,
          networkRequest: kind === 'sandbox-network' ? resolveSandboxNetworkRequest(toolPart) : undefined,
        };
      }
    }
    return null;
  }, [messages, effectiveToolChoice]);

  const shouldShowLoadingIndicator = useMemo(() => {
    if (!agentBusy || messages.length === 0) {
      return false;
    }
    const lastMessage = messages.at(-1);
    const hasVisibleParts = lastMessage?.parts?.some(
      (part) => part.type === 'text' || part.type === 'reasoning' || isToolUIPart(part),
    );
    return !hasVisibleParts;
  }, [agentBusy, messages]);

  const updateScrollToBottomVisibility = useCallback((element: HTMLDivElement) => {
    const distanceFromBottom = element.scrollHeight - element.scrollTop - element.clientHeight;
    const isScrollable = element.scrollHeight - element.clientHeight > CHAT_BOTTOM_PROXIMITY_PX;
    const isNearBottom = distanceFromBottom < CHAT_BOTTOM_PROXIMITY_PX;
    isNearBottomRef.current = isNearBottom;
    setShowScrollToBottom(isScrollable && !isNearBottom);
  }, []);

  const handleScroll = useCallback(() => {
    const element = chatContainerRef.current;
    if (!element) {
      return;
    }
    updateScrollToBottomVisibility(element);
  }, [updateScrollToBottomVisibility]);

  const handleScrollToBottom = useCallback(() => {
    const element = chatContainerRef.current;
    if (!element) {
      return;
    }
    isNearBottomRef.current = true;
    setShowScrollToBottom(false);
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
      return;
    }
    element.scrollTo({ top: element.scrollHeight, behavior: 'smooth' });
  }, []);

  useEffect(() => {
    const element = chatContainerRef.current;
    if (!element) {
      setShowScrollToBottom(false);
      return undefined;
    }
    if (isNearBottomRef.current) {
      setShowScrollToBottom(false);
      const frameId = requestAnimationFrame(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
      });
      return () => cancelAnimationFrame(frameId);
    }
    const frameId = requestAnimationFrame(() => {
      updateScrollToBottomVisibility(element);
    });
    return () => cancelAnimationFrame(frameId);
  }, [messages, status, shouldShowMessageSurface, updateScrollToBottomVisibility]);

  return (
    <div className={className} style={{ display: 'flex', minHeight: 0, flex: 1, flexDirection: 'column', justifyContent: shouldShowMessageSurface ? 'flex-start' : 'flex-end', overflow: 'hidden' }}>
      {shouldShowMessageSurface ? (
        <div ref={chatContainerRef} onScroll={handleScroll} style={{ minHeight: 0, flex: 1, overflowY: 'auto', borderRadius: '1.5rem', background: 'var(--color-bg-app)', padding: '1rem 1rem 1.5rem' }}>
          <ChatMessageList
            messages={messages}
            threadId={threadId}
            isLoading={chatLoading}
            error={error}
            addToolResult={addToolResult}
            shouldShowLoadingIndicator={shouldShowLoadingIndicator}
            toolChoice={effectiveToolChoice}
            setMessages={setMessages}
            sendMessage={sendMessage}
            onEditorWriteConfirmed={onEditorWriteConfirmed}
          />
          <div ref={bottomRef} aria-hidden="true" />
        </div>
      ) : null}

      <div style={{ position: 'relative', zIndex: 10, width: '100%', margin: '0.75rem 0 0', flexShrink: 0, paddingBottom: 'calc(env(safe-area-inset-bottom) + 0.5rem)' }}>
        {shouldShowMessageSurface && showScrollToBottom ? (
          <button
            type="button"
            aria-label={t('chat.panel.scrollToBottom')}
            title={t('chat.panel.scrollToBottom')}
            onClick={handleScrollToBottom}
            style={{
              position: 'absolute',
              left: '50%',
              bottom: 'calc(100% + 0.6rem)',
              transform: 'translateX(-50%)',
              width: '2.5rem',
              height: '2.5rem',
              borderRadius: '999px',
              border: '1px solid var(--color-border-paper)',
              background: 'var(--color-bg-surface-solid)',
              color: 'var(--color-text-primary)',
              boxShadow: '0 8px 20px var(--color-shadow-soft)',
              cursor: 'pointer',
              display: 'grid',
              placeItems: 'center',
              transition: 'transform 0.16s ease, box-shadow 0.16s ease, background 0.16s ease',
            }}
          >
            <IconArrowDown style={{ width: '1.05rem', height: '1.05rem' }} />
          </button>
        ) : null}
        {pendingConfirmation ? (
          // While a tool confirmation is pending, the input dock is replaced by
          // the confirmation panel — the composer returns once the user decides.
          <ToolConfirmationDock
            key={pendingConfirmation.partKey}
            confirmation={pendingConfirmation}
            threadId={threadId}
            addToolResult={addToolResult}
          />
        ) : (
          <AIInputDock
            openFileDialogSignal={openFileDialogSignal}
            fullAccessEnabled={imFullAccessEnabled}
            onSendMessage={async (message, uploadedFiles = [], toolChoice = 'auto') => {
              onConversationStart?.();
              setCurrentToolChoice(toolChoice);
              pendingDataRef.current = {
                rawAttachments: uploadedFiles.map(toAttachment),
                toolChoice,
              };

              const validFiles = uploadedFiles.filter((file) => file.storageKey);
              const parts: Array<FileUIPart | TextUIPart> = validFiles.map((file) => ({
                type: 'file',
                url: toFileProxyUrl(file.storageKey!),
                mediaType: file.mimeType,
                filename: file.name,
              } as FileUIPart));
              if (message) {
                parts.push({ type: 'text', text: message } as TextUIPart);
              }
              if (parts.length === 0) {
                return;
              }
              await sendMessage({ role: 'user', parts });
            }}
            placeholder={inputPlaceholder}
            loading={agentBusy}
            onStop={agentBusy ? handleStop : undefined}
            stopPending={isStopping}
            workspaceSessionId={workspaceEnabled ? threadId : undefined}
            mode="full"
          />
        )}
      </div>
    </div>
  );
}

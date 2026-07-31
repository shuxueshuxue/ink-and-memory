// [Input] Runtime WebSocket base config, editor engine refs, browser audio APIs, and speech-recognition websocket endpoint.
// [Output] Voice input hook that streams microphone audio to backend speech recognition.
// [Pos] voice-input hook node in frontend/src/hooks
// [Sync] 2026-06-12: derive speech-recognition websocket URL from runtime API base instead of localhost.
import { useState, useEffect, useRef, useCallback } from 'react';
import type { RefObject } from 'react';
import type { EditorEngine, TextCell } from '../engine/EditorEngine';
import { webSocketUrl } from '../lib/apiBase';

export interface UseVoiceInputOptions {
  engineRef: RefObject<EditorEngine | null>;
  textareaRefs: RefObject<Map<string, HTMLTextAreaElement>>;
  isAuthenticated: boolean;
}

export interface UseVoiceInputReturn {
  userTalking: boolean;
  handleToggleTalking: () => Promise<void>;
}

function floatTo16BitPCM(float32Array: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(float32Array.length * 2);
  const view = new DataView(buffer);
  let offset = 0;
  for (let i = 0; i < float32Array.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }
  return buffer;
}

function downsampleBuffer(buffer: Float32Array, inSampleRate: number, outSampleRate: number): Float32Array {
  if (outSampleRate === inSampleRate) {
    return buffer;
  }
  if (outSampleRate > inSampleRate) {
    console.warn('downsampleBuffer: target sample rate is higher than input, returning original');
    return buffer;
  }
  const sampleRateRatio = inSampleRate / outSampleRate;
  const newLength = Math.round(buffer.length / sampleRateRatio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    result[offsetResult] = count ? accum / count : 0;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

function showToast(message: string, isError: boolean = false) {
  const toast = document.createElement('div');
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed;
    top: 70px;
    right: 20px;
    background: ${isError ? 'var(--color-state-error)' : 'var(--color-state-success)'};
    color: white;
    padding: 12px 20px;
    border-radius: 6px;
    font-size: 14px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto;
    z-index: 10000;
    box-shadow: 0 4px 12px var(--color-shadow-medium);
  `;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => document.body.removeChild(toast), 300);
  }, 2000);
}

// @@@ Voice input hook: manages websocket speech recognition + audio piping
export function useVoiceInput({
  engineRef,
  textareaRefs,
  isAuthenticated,
}: UseVoiceInputOptions): UseVoiceInputReturn {
  const [userTalking, setUserTalking] = useState(false);

  const focusedTextarea = useRef<HTMLTextAreaElement | undefined>(undefined);
  const focusedCell = useRef<TextCell | undefined>(undefined);
  const lastUpdateTime = useRef<number>(0);
  const voiceInputNewContent = useRef<string>('');
  const stopTalking = useRef<() => void>(() => setUserTalking(false));

  useEffect(() => {
    lastUpdateTime.current = performance.now();

    if (userTalking) {
      startTalking();
    } else {
      stopTalking.current();
    }

    async function startTalking() {
      let audioCtx: AudioContext | undefined;
      let stream: MediaStream | undefined;
      let processor: ScriptProcessorNode | undefined;
      let source: MediaStreamAudioSourceNode | undefined;
      let ws: WebSocket | undefined;
      const targetSampleRate = 16000;

      stopTalking.current = function () {
        document.querySelector('.voice-input-modal')?.remove();
        processor?.disconnect();
        source?.disconnect();
        audioCtx?.close();
        stream?.getTracks().forEach(t => t.stop());
        ws?.close();
      };

      try {
        if (!engineRef.current) {
          throw new Error('engineRef.current is empty');
        }

        focusedCell.current = [...engineRef.current.getState().cells]
          .reverse()
          .find(c => c.type === 'text') as TextCell | undefined;
        focusedTextarea.current = textareaRefs.current.get(focusedCell.current?.id ?? '');

        if (!focusedTextarea.current || !focusedCell.current) {
          throw new Error('Cannot find focused cell');
        }

        const currentContent = focusedCell.current.content;
        const cursorPos = focusedTextarea.current.selectionEnd;
        const contentBefore = currentContent.slice(0, cursorPos);
        const contentAfter = currentContent.slice(cursorPos);

        let sentences: Array<string> = [];
        let sentenceId = -1;

        const voiceInputModal = document.createElement('div');
        voiceInputModal.className = 'voice-input-modal';
        document.body.append(voiceInputModal);

        ws = new WebSocket(webSocketUrl('/ws/speech-recognition'));
        ws.binaryType = 'arraybuffer';
        ws.onerror = (e) => {
          console.error('WS err', e);
        };
        ws.onmessage = (evt) => {
          const now = performance.now();
          if (now - lastUpdateTime.current < 300) {
            return;
          }
          lastUpdateTime.current = now;

          try {
            if (!engineRef.current || !focusedCell.current || !focusedTextarea.current) {
              throw new Error('Lost focus');
            }

            const data = JSON.parse(evt.data);
            const id = data.id;
            if (id !== sentenceId) {
              sentenceId = id;
              sentences.push('');
            }
            sentences[sentences.length - 1] = data.sentence;

            voiceInputNewContent.current = contentBefore + sentences.join('') + contentAfter;
            engineRef.current.updateTextCell(focusedCell.current.id, voiceInputNewContent.current);

            setTimeout(() => {
              if (!engineRef.current) {
                return;
              }
              focusedCell.current = [...engineRef.current.getState().cells]
                .reverse()
                .find(c => c.type === 'text') as TextCell | undefined;
              focusedTextarea.current = textareaRefs.current.get(focusedCell.current?.id ?? '');
              if (focusedTextarea.current) {
                focusedTextarea.current.style.height = `${focusedTextarea.current.scrollHeight}px`;
              }
            }, 100);
          } catch (err) {
            console.log('Non-JSON message from server:', evt.data);
          }
        };

        const checkInactivity = () => {
          if (performance.now() - lastUpdateTime.current > 10000) {
            setUserTalking(false);
          } else {
            requestAnimationFrame(checkInactivity);
          }
        };
        requestAnimationFrame(checkInactivity);

        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioCtx = new window.AudioContext();
        source = audioCtx.createMediaStreamSource(stream);

        const inputSampleRate = audioCtx.sampleRate;
        const bufferSize = 4096;
        processor = audioCtx.createScriptProcessor(bufferSize, 1, 1);

        processor.onaudioprocess = (event) => {
          const inputBuffer = event.inputBuffer.getChannelData(0);
          const downsampled = downsampleBuffer(inputBuffer, inputSampleRate, targetSampleRate);
          const pcm16ab = floatTo16BitPCM(downsampled);
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(pcm16ab);
          }
        };

        source.connect(processor);
        processor.connect(audioCtx.destination);
      } catch (error) {
        console.error('Voice input encountered an unexpected error:', error);
        setUserTalking(false);
      }
    }
  }, [userTalking, engineRef, textareaRefs]);

  const handleToggleTalking = useCallback(async () => {
    if (!textareaRefs.current) return;

    if (!isAuthenticated) {
      showToast('Please sign in to enable voice input', true);
      return;
    }

    setUserTalking(prev => !prev);
  }, [isAuthenticated, textareaRefs]);

  return {
    userTalking,
    handleToggleTalking,
  };
}

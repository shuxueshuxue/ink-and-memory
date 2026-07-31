/**
 * EditorEngine.ts
 * Clean editor engine based on trace-based energy model
 * [Sync] 2026-05-30: fix insertWidgetAfterLine to always ensure a text cell exists after any widget,
 *   even when inserting between two widgets (was only guarding the last-cell case).
 * [Sync] 2026-05-30: fix deleteCell to guarantee last cell is always text after widget removal.
 * [Sync] 2026-06-14: add loadState source markers so remote Agent-write reloads
 *   can skip the next automatic save cycle.
 */

import { findNormalizedPhrase } from '../utils/textNormalize';
import { debugLogger } from '../utils/debugLogger';
import { STORAGE_KEYS } from '../constants/storageKeys';

// @@@ Core data model - cells + commentors + tasks + WeightPath
export interface EditorState {
  cells: Cell[];
  commentors: Commentor[];
  tasks: Task[];
  weightPath: WeightEntry[];
  overlappedPhrases: string[];  // @@@ Phrases rejected due to overlap (feedback to backend)
  notFoundPhrases: string[];  // @@@ Phrases LLM suggested that were not found in text
  id: string;
  selectedState?: string | null;  // @@@ Emotional state for this session (stored per-session)
  createdAt?: string;  // @@@ ISO timestamp when session was created
}

export type Cell = TextCell | WidgetCell;

export interface TextCell {
  id: string;
  type: 'text';
  content: string;  // Plain text content
}

export interface WidgetCell {
  id: string;
  type: 'widget';
  widgetType: 'chat' | 'greeting' | 'other';
  data: any;  // Widget-specific data
}

export interface ChatMessage {
  role: 'assistant' | 'user';
  content: string;
  timestamp: number;
}

export interface Commentor {
  id: string;
  phrase: string;       // Highlighted phrase
  comment: string;      // The comment
  voiceId?: string;     // NEW: Voice ID for voiceConfigs lookup (e.g., "mirror")
  voice: string;        // Voice display name (e.g., "照镜者") - immutable snapshot
  icon: string;         // Icon identifier
  color: string;        // Color identifier
  appliedAt?: number;   // Timestamp when applied (if applied)
  computedAt: number;   // Timestamp when computed
  textSnapshot: string; // Text at computation time
  chatHistory?: ChatMessage[];  // Conversation with this comment
  feedback?: 'star' | 'kill';   // User feedback
}

export interface Task {
  id: string;
  type: 'searching' | 'thinking' | 'other';
  message: string;
  startedAt: number;
  completedAt?: number;
}

export interface WeightEntry {
  timestamp: number;
  text: string;
  weight: number;
  delta: number;  // max(0, weight - prevWeight)
  energy: number; // Accumulated energy at this point
}

export type EditorStateLoadSource = 'local' | 'remote';

// @@@ Weight function implementation
export function computeWeight(text: string): number {
  let weight = 0;

  for (const char of text) {
    // Sentence boundaries
    if (/[.!?。！？\n]/.test(char)) {
      weight += 4;
    }
    // Chinese comma (ignored)
    else if (char === '，') {
      // Skip: weight += 0
    }
    // CJK characters
    else if (/[\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ff]/.test(char)) {
      weight += 2;
    }
    // Default
    else {
      weight += 1;
    }
  }

  return weight;
}

// @@@ Extract completed sentences (for backend analysis)
export function getCompletedSentences(text: string): string {
  // Split by sentence boundaries (including Chinese comma and newline)
  const parts = text.split(/([.!?。！？，\n]+)/);

  let result = '';
  for (let i = 0; i < parts.length - 1; i += 2) {
    // Include sentence + its punctuation
    if (i + 1 < parts.length) {
      result += parts[i] + parts[i + 1];
    }
  }

  // Don't include the last part if it doesn't end with punctuation
  return result.trim();
}

// @@@ Main engine class
export class EditorEngine {
  private state: EditorState;
  private usedEnergy: number = 0;
  private threshold: number = 50;
  private commentorWaitlist: Commentor[] = [];
  private sentCache: Map<string, string> = new Map(); // Track sent sentences -> commentor hash
  private onStateChange?: (state: EditorState) => void;
  private isRequesting: boolean = false; // Track if request in progress
  private blankResetSubscribers: Set<() => void> = new Set();
  private lastLoadSource: EditorStateLoadSource = 'local';

  constructor(sessionId: string) {
    this.state = {
      cells: [{ id: generateId(), type: 'text', content: '' }],
      commentors: [],
      tasks: [],
      weightPath: [],
      overlappedPhrases: [],
      notFoundPhrases: [],
      id: sessionId
    };
  }

  onBlankReset(callback: () => void) {
    this.blankResetSubscribers.add(callback);
    return () => this.blankResetSubscribers.delete(callback);
  }

  private notifyBlankReset() {
    this.blankResetSubscribers.forEach(cb => {
      try {
        cb();
      } catch (error) {
        console.error('Blank reset subscriber failed', error);
      }
    });
  }

  // @@@ Update voice configurations from settings
  // No-op: Backend now loads voice configs from database, not from frontend
  setVoiceConfigs(_configs: Record<string, any>) {
    // Kept for backward compatibility, but does nothing
  }

  // @@@ Update a specific text cell by ID
  updateTextCell(cellId: string, newText: string) {
    const cell = this.state.cells.find(c => c.id === cellId);
    if (!cell || cell.type !== 'text') return;

    (cell as TextCell).content = newText;
    this.applyTextUpdate();
  }

  // @@@ Apply weight calculation and trigger analysis
  private applyTextUpdate() {
    const combinedText = this.getCombinedText();

    // @@@ Auto-reset when editor is cleared (no widgets + empty text cells)
    if (this.shouldResetEditorState(combinedText)) {
      this.resetEditorToBlank();
      return;
    }

    // Compute new weight entry
    const weight = computeWeight(combinedText);
    const lastEntry = this.state.weightPath[this.state.weightPath.length - 1];
    const prevWeight = lastEntry?.weight || 0;
    const delta = Math.max(0, weight - prevWeight);
    const prevEnergy = lastEntry?.energy || 0;
    const energy = prevEnergy + delta;

    // Add to weight path
    this.state.weightPath.push({
      timestamp: Date.now(),
      text: combinedText,
      weight,
      delta,
      energy
    });

    // Check if we should request analysis
    this.checkAnalysisTrigger(combinedText, energy);

    // Check if we can apply commentors
    const result = this.checkCommentorApplication(combinedText, energy);

    // @@@ If comments were skipped, invalidate cache to allow fresh request
    if (result.skippedAny && !result.appliedAny) {
      debugLogger.log('skip', 'Comments were skipped, invalidating cache to allow fresh request', {
        waitlistLength: this.commentorWaitlist.length
      });
      const completedSentences = getCompletedSentences(combinedText);
      if (completedSentences) {
        this.sentCache.delete(completedSentences);
      }
    }

    this.notifyChange();
  }

  // @@@ Get combined text from all text cells
  private getCombinedText(): string {
    return this.state.cells
      .filter(c => c.type === 'text')
      .map(c => (c as TextCell).content)
      .join('');
  }

  // @@@ Detect when all text cells are empty and no other cells remain
  private shouldResetEditorState(combinedText: string): boolean {
    const hasNonTextCells = this.state.cells.some(cell => cell.type !== 'text');
    if (hasNonTextCells) {
      return false;
    }

    return combinedText.trim().length === 0;
  }

  // @@@ Restore editor to pristine state while starting a fresh session
  private resetEditorToBlank() {
    const { selectedState, createdAt, id } = this.state;
    const preservedTimestamp = createdAt ?? new Date().toISOString();
    const preservedId = id || (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString());

    this.state = {
      cells: [{ id: generateId(), type: 'text', content: '' }],
      commentors: [],
      tasks: [],
      weightPath: [],
      overlappedPhrases: [],
      notFoundPhrases: [],
      id: preservedId,
      selectedState,
      createdAt: preservedTimestamp
    };

    this.usedEnergy = 0;
    this.commentorWaitlist = [];
    this.sentCache.clear();
    this.isRequesting = false;

    this.notifyChange();
    this.notifyBlankReset();
  }


  // @@@ Check if we should send text for analysis
  private checkAnalysisTrigger(text: string, _currentEnergy: number) {
    const completedSentences = getCompletedSentences(text);

    // Skip if no completed sentences or already requesting
    if (!completedSentences || this.isRequesting) {
      return;
    }

    // Build hash of current commentor configuration
    const commentorHash = this.getCommentorHash();

    // Check if this text+commentor combination was already sent
    const cachedHash = this.sentCache.get(completedSentences);

    // Only send if not in cache OR commentor config changed
    if (!cachedHash || cachedHash !== commentorHash) {
      this.sentCache.set(completedSentences, commentorHash);

      // Request analysis from backend (async, results go to waitlist)
      this.requestAnalysis(completedSentences);
    }
  }

  // @@@ Get hash of current commentor configuration
  private getCommentorHash(): string {
    // For now, just use applied commentor count as simple hash
    // Could be more sophisticated if needed
    return `v1_${this.state.commentors.filter(c => c.appliedAt).length}`;
  }

  // @@@ Check if we can apply commentors from waitlist
  private checkCommentorApplication(text: string, currentEnergy: number): { appliedAny: boolean; skippedAny: boolean } {
    let appliedAny = false;
    let skippedAny = false;

    // Apply ONE commentor at a time when we have enough energy
    while (this.commentorWaitlist.length > 0) {
      const unusedEnergy = currentEnergy - this.usedEnergy;

      // Stop if we don't have enough energy for the next commentor
      if (unusedEnergy < this.threshold) {
        break;
      }

      const commentor = this.commentorWaitlist.pop()!;

      // Check if text still matches (current text starts with snapshot)
      if (!text.startsWith(commentor.textSnapshot)) {
        debugLogger.log('skip', `Skipped outdated commentor: ${commentor.voice}`, {
          voice: commentor.voice,
          phrase: commentor.phrase,
          reason: 'text snapshot mismatch'
        });
        skippedAny = true;
        continue;
      }

      // @@@ Check for overlap with existing highlights (with normalized matching)
      const phraseIndex = findNormalizedPhrase(text, commentor.phrase);
      if (phraseIndex === -1) {
        // @@@ Deep debugging - show character codes
        const phraseChars = Array.from(commentor.phrase.slice(0, 30)).map(c => `${c}(${c.charCodeAt(0)})`).join(' ');
        const textSnippet = text.includes('transcend') ? text.substring(text.indexOf('transcend'), text.indexOf('transcend') + 50) : '';
        const textChars = textSnippet ? Array.from(textSnippet.slice(0, 30)).map(c => `${c}(${c.charCodeAt(0)})`).join(' ') : '';

        debugLogger.log('phrase_not_found', `Skipped commentor (phrase not found): ${commentor.voice}`, {
          voice: commentor.voice,
          phrase: commentor.phrase,
          phraseCharCodes: phraseChars,
          textLength: text.length,
          fullText: text,
          textSnippet: textSnippet,
          textCharCodes: textChars
        });
        if (!this.state.notFoundPhrases.includes(commentor.phrase)) {
          this.state.notFoundPhrases.push(commentor.phrase);
        }
        skippedAny = true;
        continue;
      }

      const phraseStart = phraseIndex;
      const phraseEnd = phraseIndex + commentor.phrase.length;

      // Check overlap with all applied commentors
      let hasOverlap = false;
      for (const applied of this.state.commentors.filter(c => c.appliedAt)) {
        const appliedIndex = findNormalizedPhrase(text, applied.phrase);
        if (appliedIndex === -1) continue;

        const appliedStart = appliedIndex;
        const appliedEnd = appliedIndex + applied.phrase.length;

        // Check if ranges overlap: [phraseStart, phraseEnd) overlaps with [appliedStart, appliedEnd)
        if (phraseStart < appliedEnd && phraseEnd > appliedStart) {
          hasOverlap = true;
          debugLogger.log('overlap', `Skipped overlapping commentor: "${commentor.phrase}" overlaps with "${applied.phrase}"`, {
            newVoice: commentor.voice,
            newPhrase: commentor.phrase,
            newRange: [phraseStart, phraseEnd],
            existingVoice: applied.voice,
            existingPhrase: applied.phrase,
            existingRange: [appliedStart, appliedEnd]
          });
          break;
        }
      }

      if (hasOverlap) {
        // @@@ Track overlapped phrase for backend feedback
        if (!this.state.overlappedPhrases.includes(commentor.phrase)) {
          this.state.overlappedPhrases.push(commentor.phrase);
        }
        skippedAny = true;
        continue;
      }

      // Apply commentor
      commentor.appliedAt = Date.now();
      this.state.commentors.push(commentor);
      this.usedEnergy += this.threshold;
      appliedAny = true;
      debugLogger.log('apply', `Applied commentor: ${commentor.voice} on "${commentor.phrase}"`, {
        voice: commentor.voice,
        phrase: commentor.phrase,
        comment: commentor.comment,
        usedEnergy: this.usedEnergy,
        totalEnergy: currentEnergy,
        remainingEnergy: currentEnergy - this.usedEnergy,
        waitlistRemaining: this.commentorWaitlist.length
      });
    }

    if (appliedAny) {
      this.notifyChange();
    }

    return { appliedAny, skippedAny };
  }

  // @@@ Request analysis from backend
  private async requestAnalysis(text: string) {
    // Prevent duplicate requests
    if (this.isRequesting) {
      return;
    }

    this.isRequesting = true;

    // Add a task to show we're working
    const task: Task = {
      id: generateId(),
      type: 'thinking',
      message: 'Analyzing text...',
      startedAt: Date.now()
    };
    this.state.tasks.push(task);
    this.notifyChange();

    try {
      // Call backend (returns ONLY ONE comment at a time)
      // Backend loads voice configs from database using user_id from JWT token
      const { analyzeText } = await import('../api/voiceApi');
      const { getMetaPrompt, getStateConfig } = await import('../utils/voiceStorage');

      // Send only APPLIED commentors to backend
      const appliedCommentors = this.state.commentors.filter(c => c.appliedAt);
      const metaPrompt = getMetaPrompt();

      // Get state prompt from localStorage
      const selectedState = localStorage.getItem(STORAGE_KEYS.SELECTED_STATE);
      const stateConfig = getStateConfig();
      const statePrompt = selectedState && stateConfig.states[selectedState]
        ? stateConfig.states[selectedState].prompt
        : '';

      const result = await analyzeText(
        text,
        this.state.id,
        appliedCommentors,
        metaPrompt,
        statePrompt,
        this.state.overlappedPhrases,
        this.state.notFoundPhrases
      );

      // Backend returns at most ONE voice
      if (result.voices.length > 0) {
        const voice = result.voices[0]; // Only take first one
        const commentor: Commentor = {
          id: generateId(),
          phrase: voice.phrase,
          comment: voice.comment,
          voiceId: voice.voice_id,     // NEW: Store ID for config lookup
          voice: voice.voice,           // KEEP: Store name for display
          icon: voice.icon,
          color: voice.color,
          computedAt: Date.now(),
          textSnapshot: text
        };
        this.commentorWaitlist.push(commentor);
        debugLogger.log('waitlist', `Added 1 commentor to waitlist: ${commentor.voice}`, {
          voice: commentor.voice,
          phrase: commentor.phrase,
          comment: commentor.comment,
          waitlistLength: this.commentorWaitlist.length
        });
      } else {
        debugLogger.log('request', 'No new commentor from backend', {
          appliedCount: this.state.commentors.filter(c => c.appliedAt).length
        });
      }
    } catch (error) {
      debugLogger.log('request', 'Analysis failed', { error: String(error) });
      console.error('Analysis failed:', error);
    } finally {
      this.isRequesting = false;

      // Complete task
      task.completedAt = Date.now();
      this.notifyChange();

      // Remove task after a delay
      setTimeout(() => {
        const idx = this.state.tasks.indexOf(task);
        if (idx !== -1) {
          this.state.tasks.splice(idx, 1);
          this.notifyChange();
        }
      }, 2000);

      // @@@ After request completes, immediately check if we can apply and request more
      this.processPendingComments(text);
    }
  }

  // @@@ Process pending comments and trigger more requests if needed
  private processPendingComments(text: string) {
    const lastEntry = this.state.weightPath[this.state.weightPath.length - 1];
    const currentEnergy = lastEntry?.energy || 0;

    // Try to apply comments from waitlist
    const result = this.checkCommentorApplication(text, currentEnergy);

    // @@@ If comments were skipped but not applied, invalidate cache
    if (result.skippedAny && !result.appliedAny) {
      debugLogger.log('skip', 'All pending comments were skipped, invalidating cache', {
        waitlistLength: this.commentorWaitlist.length,
        willRetry: true
      });
      const completedSentences = getCompletedSentences(text);
      if (completedSentences) {
        this.sentCache.delete(completedSentences);
        // Trigger a fresh request immediately
        setTimeout(() => {
          this.checkAnalysisTrigger(text, currentEnergy);
        }, 50);
      }
    }
    // If we applied comments, hash changed, so check if we need another request
    else if (result.appliedAny) {
      // Give a small delay to let the UI update
      setTimeout(() => {
        this.checkAnalysisTrigger(text, currentEnergy);
      }, 50);
    }
  }

  // @@@ Merge consecutive text cells to prevent text-text pattern
  private mergeConsecutiveTextCells() {
    const merged: Cell[] = [];
    let i = 0;
    let mergeCount = 0;

    while (i < this.state.cells.length) {
      const cell = this.state.cells[i];

      if (cell.type === 'text') {
        // Collect all consecutive text cells
        let combinedContent = (cell as TextCell).content;
        let j = i + 1;
        let mergedCells = 0;

        while (j < this.state.cells.length && this.state.cells[j].type === 'text') {
          combinedContent += (this.state.cells[j] as TextCell).content;
          j++;
          mergedCells++;
        }

        if (mergedCells > 0) {
          mergeCount += mergedCells;
        }

        // Add merged text cell
        merged.push({
          id: cell.id, // Keep first cell's ID
          type: 'text',
          content: combinedContent
        });

        i = j; // Skip all merged cells
      } else {
        merged.push(cell);
        i++;
      }
    }

    this.state.cells = merged;
  }

  // @@@ Insert widget at cursor, removing @ character if present
  insertWidgetAtCursor(cellId: string, cursorPosition: number, widgetType: WidgetCell['widgetType'], data: any) {
    const cell = this.state.cells.find(c => c.id === cellId);
    if (!cell || cell.type !== 'text') return;

    const text = (cell as TextCell).content;

    // Remove @ character if it's right before cursor
    const atPosition = cursorPosition - 1;
    if (atPosition >= 0 && text[atPosition] === '@') {
      // Check if @ is the only character on its line
      const lineStart = text.lastIndexOf('\n', atPosition - 1) + 1;
      const lineEnd = text.indexOf('\n', cursorPosition);
      const lineEndPos = lineEnd === -1 ? text.length : lineEnd;
      const lineContent = text.substring(lineStart, lineEndPos);
      const isOnlyCharOnLine = lineContent.trim() === '@';

      // Remove the @ and optionally the newline
      let newText: string;
      if (isOnlyCharOnLine) {
        // @ is alone on its line - remove the newline before it (if exists)
        const hasNewlineBefore = atPosition > 0 && text[atPosition - 1] === '\n';
        if (hasNewlineBefore) {
          // Remove the newline before @ and the @
          newText = text.substring(0, atPosition - 1) + text.substring(cursorPosition);
        } else {
          // Just remove @
          newText = text.substring(0, atPosition) + text.substring(cursorPosition);
        }
      } else {
        // @ is not alone - just remove @
        newText = text.substring(0, atPosition) + text.substring(cursorPosition);
      }
      (cell as TextCell).content = newText;

      // Insert widget at the @ position (adjust if we removed newline before)
      const insertPos = isOnlyCharOnLine && atPosition > 0 && text[atPosition - 1] === '\n'
        ? atPosition - 1
        : atPosition;
      this.insertWidgetAfterLine(cellId, insertPos, widgetType, data);
    } else {
      // No @ found, just insert widget at cursor position
      this.insertWidgetAfterLine(cellId, cursorPosition, widgetType, data);
    }
  }

  // @@@ Add a widget cell after a specific text position in a specific cell
  insertWidgetAfterLine(cellId: string, cursorPosition: number, widgetType: WidgetCell['widgetType'], data: any) {
    // Find the specific cell and its index
    const cellIndex = this.state.cells.findIndex(c => c.id === cellId);
    if (cellIndex === -1) return;

    const cell = this.state.cells[cellIndex];
    if (cell.type !== 'text') return;

    const text = (cell as TextCell).content;

    // Find the line end after cursor position
    let lineEndPos = text.indexOf('\n', cursorPosition);
    if (lineEndPos === -1) {
      lineEndPos = text.length;
    } else {
      lineEndPos += 1; // Include the newline
    }

    // Split text into before and after
    const beforeText = text.substring(0, lineEndPos);
    const afterText = text.substring(lineEndPos);

    // Create replacement cells for this position
    const replacementCells: Cell[] = [];

    // Text before widget (only if non-empty)
    if (beforeText.length > 0) {
      replacementCells.push({
        id: generateId(),
        type: 'text',
        content: beforeText
      });
    }

    // Widget cell
    replacementCells.push({
      id: generateId(),
      type: 'widget',
      widgetType,
      data
    });

    // Text after widget: always add when there's afterText, or when the next cell is not
    // already a text cell (covers both end-of-list and widget-follows-widget cases).
    const hasNextTextCell = cellIndex + 1 < this.state.cells.length &&
      this.state.cells[cellIndex + 1].type === 'text';

    if (afterText.length > 0 || !hasNextTextCell) {
      replacementCells.push({
        id: generateId(),
        type: 'text',
        content: afterText
      });
    }

    // Replace the cell at cellIndex with the new cells, keeping all other cells intact
    this.state.cells.splice(cellIndex, 1, ...replacementCells);
    this.mergeConsecutiveTextCells(); // Ensure no consecutive text cells
    this.notifyChange();
  }

  // @@@ Add a widget cell at the end
  addWidgetCell(widgetType: WidgetCell['widgetType'], data: any) {
    const widget: WidgetCell = {
      id: generateId(),
      type: 'widget',
      widgetType,
      data
    };
    this.state.cells.push(widget);
    this.notifyChange();
  }

  // @@@ Update widget data (for chat messages)
  updateWidgetData(widgetId: string, data: any) {
    const widget = this.state.cells.find(c => c.type === 'widget' && c.id === widgetId);
    if (widget && widget.type === 'widget') {
      widget.data = data;
      this.notifyChange();
    }
  }

  // @@@ Subscribe to state changes
  subscribe(callback: (state: EditorState) => void) {
    this.onStateChange = callback;
  }

  private notifyChange() {
    this.onStateChange?.(this.state);
  }

  // @@@ Get current state
  getState(): EditorState {
    return this.state;
  }

  // @@@ Load state from storage
  loadState(state: EditorState, options: { source?: EditorStateLoadSource } = {}) {
    if (!state.id) {
      throw new Error('EditorState.id is required when loading');
    }
    this.lastLoadSource = options.source ?? 'local';
    this.state = { ...state };
    // @@@ Ensure overlappedPhrases field exists (migration for old state)
    if (!this.state.overlappedPhrases) {
      this.state.overlappedPhrases = [];
    }
    if (!this.state.notFoundPhrases) {
      this.state.notFoundPhrases = [];
    }
    // Recompute used energy from applied commentors
    this.usedEnergy = this.state.commentors.filter(c => c.appliedAt).length * this.threshold;
    this.notifyChange();
  }

  consumeLastLoadSource(): EditorStateLoadSource {
    const source = this.lastLoadSource;
    this.lastLoadSource = 'local';
    return source;
  }

  // @@@ Set current entry ID (for calendar overwrite tracking)
  setCurrentEntryId(entryId: string | undefined) {
    if (!entryId) return;
    this.state.id = entryId;
    this.notifyChange();
  }

  // @@@ Delete a cell by ID
  deleteCell(cellId: string) {
    const cellIndex = this.state.cells.findIndex(c => c.id === cellId);
    if (cellIndex === -1) return;

    this.state.cells.splice(cellIndex, 1);

    // Ensure we always have at least one text cell
    if (this.state.cells.length === 0) {
      this.state.cells.push({ id: generateId(), type: 'text', content: '' });
    }

    // Merge consecutive text cells (important when deleting a widget between text cells)
    this.mergeConsecutiveTextCells();

    // Ensure the last cell is always a text cell so the user can continue writing
    const lastCell = this.state.cells[this.state.cells.length - 1];
    if (lastCell && lastCell.type !== 'text') {
      this.state.cells.push({ id: generateId(), type: 'text', content: '' });
    }

    this.notifyChange();
  }

  // @@@ Add a message to a comment's chat history
  addCommentChatMessage(commentId: string, role: 'assistant' | 'user', content: string) {
    const comment = this.state.commentors.find(c => c.id === commentId);
    if (!comment) return;

    if (!comment.chatHistory) {
      // Initialize with the original comment as first assistant message
      comment.chatHistory = [{
        role: 'assistant',
        content: comment.comment,
        timestamp: comment.computedAt
      }];
    }

    comment.chatHistory.push({
      role,
      content,
      timestamp: Date.now()
    });

    this.notifyChange();
  }

  // @@@ Set feedback for a comment
  setCommentFeedback(commentId: string, feedback: 'star' | 'kill') {
    const comment = this.state.commentors.find(c => c.id === commentId);
    if (!comment) return;

    comment.feedback = feedback;
    this.notifyChange();
  }

  // @@@ Get comment by ID
  getComment(commentId: string): Commentor | undefined {
    return this.state.commentors.find(c => c.id === commentId);
  }
}

// @@@ Helper to generate IDs
function generateId(): string {
  return `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

import type { EditorState } from '../engine/EditorEngine';
import { STORAGE_KEYS } from '../constants/storageKeys';

export interface CalendarEntry {
  id: string;
  timestamp: number;
  state: EditorState;
  firstLine: string;
  labels?: string[];
}

export interface CalendarData {
  [date: string]: CalendarEntry[]; // date format: YYYY-MM-DD
}

export function getCalendarData(): CalendarData {
  const stored = localStorage.getItem(STORAGE_KEYS.CALENDAR_ENTRIES);
  if (!stored) return {};
  try {
    return JSON.parse(stored);
  } catch {
    return {};
  }
}

export function saveCalendarData(data: CalendarData): void {
  localStorage.setItem(STORAGE_KEYS.CALENDAR_ENTRIES, JSON.stringify(data));
}

export function getTodayKey(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function getDateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function extractFirstLine(state: EditorState): string {
  // Get first text cell's content
  const firstTextCell = state.cells.find(c => c.type === 'text');
  if (!firstTextCell || firstTextCell.type !== 'text') return 'Empty note';

  const content = firstTextCell.content.trim();
  if (!content) return 'Empty note';

  // Get first line, max 30 chars
  const firstLine = content.split('\n')[0];
  return firstLine.length > 30 ? firstLine.slice(0, 30) + '...' : firstLine;
}

export function saveEntryToToday(state: EditorState): string {
  const data = getCalendarData();
  const today = getTodayKey();

  // @@@ Check if we're overwriting an existing entry
  if (state.id) {
    // Find and update the existing entry across all dates
    for (const dateKey of Object.keys(data)) {
      const entryIndex = data[dateKey].findIndex(e => e.id === state.id);
      if (entryIndex !== -1) {
        // Update existing entry
        data[dateKey][entryIndex] = {
          id: state.id,
          timestamp: Date.now(),
          state: state,
          firstLine: extractFirstLine(state)
        };
        saveCalendarData(data);
        return state.id;
      }
    }
  }

  // @@@ Create new entry
  if (!data[today]) {
    data[today] = [];
  }

  const generatedId = `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  const entry: CalendarEntry = {
    id: generatedId,
    timestamp: Date.now(),
    state: state,
    firstLine: extractFirstLine(state)
  };

  data[today].push(entry);
  saveCalendarData(data);

  state.id = generatedId;
  return generatedId;
}

export function getEntriesForDate(dateKey: string): CalendarEntry[] {
  const data = getCalendarData();
  return data[dateKey] || [];
}

export function getDatesWithEntries(): string[] {
  const data = getCalendarData();
  return Object.keys(data);
}

export function deleteEntry(dateKey: string, entryId: string): void {
  const data = getCalendarData();
  if (!data[dateKey]) return;

  data[dateKey] = data[dateKey].filter(e => e.id !== entryId);

  // Remove date if no entries left
  if (data[dateKey].length === 0) {
    delete data[dateKey];
  }

  saveCalendarData(data);
}

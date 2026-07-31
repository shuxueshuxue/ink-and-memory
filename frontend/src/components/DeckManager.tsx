// [Input] Voice deck API client, i18n labels, and deck editor modal.
// [Output] Deck management surface for local and community voice decks.
// [Pos] deck-manager-view node in frontend/src/components
// [Sync] 2026-07-08: replace light-only Decks cards, loading/error states, and publish modal colors
//                    with semantic theme tokens so the Decks surface adapts to dark mode.
// [Sync] 2026-07-09: replace the high-saturation create-deck gradient with the same theme-inverted
//                    paper/ink primary button treatment used by Settings actions.
// [Sync] 2026-07-09: align the Decks page with the light paper / dashed boundary color system;
//                    deck items now use flat paper rows, weak boundaries, and small accent marks.
import { useMemo, useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  listDecks,
  getDeck,
  createDeck,
  updateDeck,
  deleteDeck,
  forkDeck,
  syncDeck,
  createVoice,
  updateVoice,
  deleteVoice,
  publishDeck,
  type Deck,
  type Voice
} from '../api/voiceApi';
import DeckEditorModal from './DeckEditorModal';
import { COLORS, iconMap } from './deckVisuals';
import type { ActiveChatVoice } from '../lib/chat-schema';

interface Props {
  onUpdate?: () => void;
  onOpenChat?: (threadId: string, voiceInfo: ActiveChatVoice) => void;
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

const DECK_PAGE_BORDER = '1px dashed color-mix(in srgb, var(--color-border-paper) 62%, transparent)';
const DECK_CONTROL_BORDER = '1px solid color-mix(in srgb, var(--color-border-paper) 58%, transparent)';
const DECK_ITEM_BORDER = '1px solid color-mix(in srgb, var(--color-border-paper) 36%, transparent)';
const DECK_LIST_SURFACE = 'color-mix(in srgb, var(--color-bg-paper) 36%, transparent)';
const DECK_ITEM_HOVER_SURFACE = 'color-mix(in srgb, var(--color-bg-paper) 58%, var(--color-bg-surface))';

export default function DeckManager({ onUpdate, onOpenChat }: Props) {
  const { t } = useTranslation();
  const spinnerKeyframes = useMemo(() => (
    `@keyframes deck-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`
  ), []);
  const [decks, setDecks] = useState<Deck[]>([]);
  const [communityDecks, setCommunityDecks] = useState<Deck[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deckIconPickerOpen, setDeckIconPickerOpen] = useState<string | null>(null); // @@@ Track which deck's icon+color picker is open
  const [creatingDeck, setCreatingDeck] = useState(false);
  const [creatingVoice, setCreatingVoice] = useState<string | null>(null);
  const [publishWarning, setPublishWarning] = useState<string | null>(null);
  const [selectedVoiceByDeck, setSelectedVoiceByDeck] = useState<Record<string, string | null>>({});
  const [activeDeckId, setActiveDeckId] = useState<string | null>(null);

  // @@@ Scroll position preservation
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadDecks();
    loadCommunityDecks();
  }, []);

  useEffect(() => {
    setSelectedVoiceByDeck(prev => {
      let changed = false;
      const next = { ...prev };

      decks.forEach((deck) => {
        const voiceIds = deck.voices?.map(v => v.id) || [];
        const currentSelection = next[deck.id];

        if (voiceIds.length === 0) {
          if (currentSelection !== null) {
            next[deck.id] = null;
            changed = true;
          }
          return;
        }

        if (!currentSelection || !voiceIds.includes(currentSelection)) {
          next[deck.id] = voiceIds[0];
          changed = true;
        }
      });

      return changed ? next : prev;
    });
  }, [decks]);

  async function loadDecks(preserveScroll = false) {
    // @@@ Save scroll position before reload
    const savedScrollTop = preserveScroll && scrollContainerRef.current
      ? scrollContainerRef.current.scrollTop
      : 0;

    try {
      if (!preserveScroll) {
        setLoading(true);
      }
      const fetchedDecks = await listDecks();

      // Load voices for each deck
      const decksWithVoices = await Promise.all(
        fetchedDecks.map(async (deck) => {
          try {
            return await getDeck(deck.id);
          } catch (err) {
            console.error(`Failed to load voices for deck ${deck.id}:`, err);
            return deck;
          }
        })
      );

      setDecks(decksWithVoices);
      setError(null);

      // @@@ Restore scroll position after render
      if (preserveScroll && scrollContainerRef.current) {
        setTimeout(() => {
          if (scrollContainerRef.current) {
            scrollContainerRef.current.scrollTop = savedScrollTop;
          }
        }, 0);
      }
    } catch (err: unknown) {
      console.error('Failed to load decks:', err);
      setError(getErrorMessage(err, 'Failed to load decks'));
    } finally {
      if (!preserveScroll) {
        setLoading(false);
      }
    }
  }

  function toggleDeck(deckId: string) {
    setActiveDeckId(deckId);
  }

  async function handleForkDeck(deckId: string) {
    try {
      await forkDeck(deckId);
      await loadDecks(true);
      onUpdate?.();
    } catch (err: unknown) {
      alert(`Failed to fork deck: ${getErrorMessage(err, 'Unknown error')}`);
    }
  }

  async function handleToggleDeck(deckId: string, currentEnabled: boolean) {
    try {
      await updateDeck(deckId, { enabled: !currentEnabled });
      await loadDecks(true);
      onUpdate?.();
    } catch (err: unknown) {
      alert(`Failed to toggle deck: ${getErrorMessage(err, 'Unknown error')}`);
    }
  }

  async function handleUpdateDeck(deckId: string, data: Partial<Deck>) {
    try {
      await updateDeck(deckId, data);
      await loadDecks(true);
      onUpdate?.();
    } catch (err: unknown) {
      alert(`Failed to update deck: ${getErrorMessage(err, 'Unknown error')}`);
    }
  }

  async function handleDeleteDeck(deckId: string) {
    if (!confirm(t('deck.confirm.delete'))) return;

    try {
      await deleteDeck(deckId);
      await loadDecks(true);
      onUpdate?.();
    } catch (err: unknown) {
      alert(`Failed to delete deck: ${getErrorMessage(err, 'Unknown error')}`);
    }
  }

  async function handleSyncDeck(deckId: string) {
    if (!confirm(t('deck.confirm.sync'))) return;

    try {
      const result = await syncDeck(deckId);
      alert(`✅ Synced ${result.synced_voices} voices with original template`);
      await loadDecks(true);
      onUpdate?.();
    } catch (err: unknown) {
      alert(`Failed to sync deck: ${getErrorMessage(err, 'Unknown error')}`);
    }
  }

  async function handleToggleVoice(voiceId: string, currentEnabled: boolean) {
    try {
      await updateVoice(voiceId, { enabled: !currentEnabled });
      await loadDecks(true);
      onUpdate?.();
    } catch (err: unknown) {
      alert(`Failed to toggle voice: ${getErrorMessage(err, 'Unknown error')}`);
    }
  }

  async function handleUpdateVoice(voiceId: string, data: Partial<Voice>) {
    try {
      await updateVoice(voiceId, data);
      await loadDecks(true);
      onUpdate?.();
    } catch (err: unknown) {
      alert(`Failed to update voice: ${getErrorMessage(err, 'Unknown error')}`);
    }
  }

  async function handleDeleteVoice(voiceId: string) {
    if (!confirm('Delete this voice?')) return;

    try {
      await deleteVoice(voiceId);
      await loadDecks(true);
      onUpdate?.();
    } catch (err: unknown) {
      alert(`Failed to delete voice: ${getErrorMessage(err, 'Unknown error')}`);
    }
  }

  async function loadCommunityDecks() {
    try {
      const published = await listDecks(true);
      setCommunityDecks(published);
    } catch (err: unknown) {
      console.error('Failed to load community decks:', err);
    }
  }

  async function handleCreateDeck() {
    setCreatingDeck(true);
    try {
      const newDeck = await createDeck({
        name: 'New Deck',
        description: 'Describe your deck here',
        icon: 'brain',
        color: 'blue'
      });
      await loadDecks(true);
      setActiveDeckId(newDeck.deck_id);
      onUpdate?.();
    } catch (err: unknown) {
      alert(`Failed to create deck: ${getErrorMessage(err, 'Unknown error')}`);
    } finally {
      setCreatingDeck(false);
    }
  }

  async function handleAddVoice(deckId: string) {
    setCreatingVoice(deckId);
    try {
      const { voice_id: newVoiceId } = await createVoice({
        deck_id: deckId,
        name: 'New Voice',
        system_prompt: 'You are a helpful assistant.',
        icon: 'brain',
        color: 'blue'
      });
      setSelectedVoiceByDeck(prev => ({ ...prev, [deckId]: newVoiceId }));
      await loadDecks(true);
      onUpdate?.();
    } catch (err: unknown) {
      alert(`Failed to create voice: ${getErrorMessage(err, 'Unknown error')}`);
    } finally {
      setCreatingVoice(null);
    }
  }

  async function handlePublishClick(deck: Deck) {
    if (deck.published) {
      handlePublishToggle(deck.id);
    } else {
      setPublishWarning(deck.id);
    }
  }

  async function handlePublishToggle(deckId: string) {
    try {
      const result = await publishDeck(deckId);
      alert(result.published ? t('deck.messages.publishSuccess') : t('deck.messages.unpublishSuccess'));
      await loadDecks(true);
      await loadCommunityDecks();
      onUpdate?.();
    } catch (err: unknown) {
      alert(`Failed: ${getErrorMessage(err, 'Unknown error')}`);
    } finally {
      setPublishWarning(null);
    }
  }

  async function handleInstallDeck(deckId: string) {
    try {
      await forkDeck(deckId);
      alert(t('deck.messages.installSuccess'));
      await loadDecks(true);
      await loadCommunityDecks();
      onUpdate?.();
    } catch (err: unknown) {
      alert(`Failed to install deck: ${getErrorMessage(err, 'Unknown error')}`);
    }
  }

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        width: '100%',
        minHeight: '100vh',
        background: 'var(--color-bg-app)'
      }}>
        <style>{spinnerKeyframes}</style>
        <div style={{
          fontSize: 18,
          color: 'var(--color-text-secondary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '0.75rem',
          textAlign: 'center'
        }}>
          <span style={{
            width: '18px',
            height: '18px',
            borderRadius: '50%',
            border: '2px solid var(--color-border-neutral)',
            borderTopColor: 'var(--color-text-secondary)',
            animation: 'deck-spin 0.9s linear infinite'
          }} />
          Loading decks…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        background: 'var(--color-bg-app)',
        gap: 16
      }}>
        <div style={{ fontSize: 18, color: 'var(--color-state-error)' }}>{error}</div>
        <button
          onClick={() => loadDecks()}
          style={{
            padding: '8px 16px',
            background: 'var(--color-text-primary)',
            color: 'var(--color-text-on-action)',
            border: 'none',
            borderRadius: '999px',
            cursor: 'pointer'
          }}
        >
          {t('deck.actions.retry')}
        </button>
      </div>
    );
  }

  const activeDeck = decks.find(d => d.id === activeDeckId) || null;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--color-bg-app)', overflow: 'hidden' }}>
      {/* Scrollable Content with embedded header */}
      <div ref={scrollContainerRef} style={{ flex: 1, overflowY: 'auto', padding: 'clamp(16px, 4vw, 32px)' }}>
        <div style={{
          maxWidth: 1200,
          margin: '0 auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 24,
          border: DECK_PAGE_BORDER,
          borderRadius: '1.05rem',
          padding: 'clamp(14px, 3vw, 24px)',
          background: 'transparent',
          boxShadow: 'none'
        }}>
          {/* Embedded Header */}
          <div style={{
            padding: '0 0 4px 0'
          }}>
            <h1 style={{
              margin: 0,
              fontSize: 28,
              fontWeight: 700,
              color: 'var(--color-text-primary)',
              fontFamily: 'Georgia, serif',
              letterSpacing: 0
            }}>
              {t('deck.heading')}
            </h1>
            <p style={{
              margin: '6px 0 0',
              fontSize: 14,
              color: 'var(--color-text-secondary)',
              fontStyle: 'italic'
            }}>
              {t('deck.subheading')}
            </p>
          </div>
          {/* Create New Deck Button */}
          <button
            onClick={handleCreateDeck}
            disabled={creatingDeck}
            style={{
              padding: '14px 28px',
              marginBottom: '8px',
              background: 'var(--color-text-primary)',
              color: 'var(--color-bg-app)',
              border: '1px solid color-mix(in srgb, var(--color-text-primary) 22%, var(--color-border-paper))',
              borderRadius: '999px',
              cursor: creatingDeck ? 'not-allowed' : 'pointer',
              fontSize: '15px',
              fontWeight: '600',
              opacity: creatingDeck ? 0.6 : 1,
              transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              alignSelf: 'flex-start',
              boxShadow: 'none',
              letterSpacing: 0
            }}
            onMouseEnter={(e) => {
              if (!creatingDeck) {
                e.currentTarget.style.transform = 'translateY(-1px)';
                e.currentTarget.style.boxShadow = 'none';
              }
            }}
            onMouseLeave={(e) => {
              if (!creatingDeck) {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = 'none';
              }
            }}
          >
            {creatingDeck ? t('deck.actions.creating') : t('deck.actions.create')}
          </button>

          {/* My Decks Section Header */}
          <h3 style={{
            margin: '8px 0',
            fontSize: '16px',
            fontWeight: '500',
            color: 'var(--color-text-primary)'
          }}>
            {t('deck.sections.myDecks')}
          </h3>

          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 14,
            alignItems: 'stretch'
          }}>
            {decks.map(deck => {
              const isSystem = !!deck.is_system;
              const Icon = iconMap[deck.icon as keyof typeof iconMap] || iconMap.brain;
              const colorHex = COLORS[deck.color as keyof typeof COLORS]?.hex || 'var(--color-action-link)';
              const voiceCount = deck.voice_count || deck.voices?.length || 0;
              const voiceCountLabel = t('deck.labels.voiceCount', { count: voiceCount });

              return (
                <div
                  key={deck.id}
                  onClick={() => toggleDeck(deck.id)}
                  style={{
                    background: DECK_LIST_SURFACE,
                    border: DECK_ITEM_BORDER,
                    borderLeft: `3px solid ${isSystem ? 'color-mix(in srgb, var(--color-border-paper) 82%, transparent)' : colorHex}`,
                    borderRadius: '0.75rem',
                    boxShadow: 'none',
                    padding: '0.82rem 0.9rem',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 10,
                    cursor: 'pointer',
                    transition: 'transform 0.15s, background 0.15s',
                    flex: '1 1 320px',
                    minWidth: 0,
                    maxWidth: '100%'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.transform = 'translateY(-1px)';
                    e.currentTarget.style.background = DECK_ITEM_HOVER_SURFACE;
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'translateY(0)';
                    e.currentTarget.style.background = DECK_LIST_SURFACE;
                  }}
                >
                  <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                    <div
                      style={{ position: 'relative' }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div
                        data-deck-icon={deck.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (!isSystem) {
                            setDeckIconPickerOpen(deckIconPickerOpen === deck.id ? null : deck.id);
                          }
                        }}
                        style={{
                          width: 46,
                          height: 46,
                          borderRadius: '0.72rem',
                          border: `1px solid color-mix(in srgb, ${colorHex} 24%, var(--color-border-paper))`,
                          background: `color-mix(in srgb, ${colorHex} 12%, var(--color-bg-paper))`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: colorHex,
                          flexShrink: 0,
                          boxShadow: 'none',
                          cursor: isSystem ? 'default' : 'pointer',
                          transition: 'transform 0.2s, background 0.2s'
                        }}
                      >
                        <Icon size={22} />
                      </div>
                    </div>

                    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                        <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--color-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {deck.name}
                        </div>
                        {isSystem && (
                          <span style={{
                            fontSize: 10,
                            fontWeight: 700,
                            color: 'var(--color-text-secondary)',
                            background: 'var(--color-bg-hover)',
                            padding: '2px 6px',
                            borderRadius: 6
                          }}>
                            System
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', lineHeight: 1.4, maxHeight: 36, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {deck.description || t('deck.labels.noDescription')}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>{voiceCountLabel}</div>
                    </div>

                    <div
                      onClick={(e) => {
                        e.stopPropagation();
                        handleToggleDeck(deck.id, deck.enabled);
                      }}
                      style={{
                        width: 42,
                        height: 20,
                        borderRadius: 10,
                        background: deck.enabled
                          ? `color-mix(in srgb, ${colorHex} 38%, var(--color-bg-surface))`
                          : 'color-mix(in srgb, var(--color-border-paper) 32%, transparent)',
                        border: DECK_CONTROL_BORDER,
                        position: 'relative',
                        cursor: 'pointer',
                        transition: 'background 0.3s',
                        flexShrink: 0
                      }}
                      title={deck.enabled ? 'Disable deck' : 'Enable deck'}
                    >
                      <div style={{
                        position: 'absolute',
                        top: 2,
                        left: deck.enabled ? 22 : 2,
                        width: 16,
                        height: 16,
                        borderRadius: 8,
                        background: 'var(--color-bg-paper)',
                        transition: 'left 0.3s',
                        boxShadow: 'none'
                      }} />
                    </div>
                  </div>

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }} onClick={(e) => e.stopPropagation()}>
                    {isSystem ? (
                      <button
                        onClick={() => handleForkDeck(deck.id)}
                        style={{
                          padding: '6px 10px',
                          background: 'transparent',
                          color: 'var(--color-text-primary)',
                          border: DECK_CONTROL_BORDER,
                          borderRadius: '999px',
                          cursor: 'pointer',
                          fontSize: 12,
                          fontWeight: 600
                        }}
                      >
                        Fork
                      </button>
                    ) : (
                      <>
                        {deck.parent_id && (
                          <button
                            onClick={() => handleSyncDeck(deck.id)}
                            style={{
                              padding: '6px 10px',
                              background: 'transparent',
                              color: 'var(--color-text-primary)',
                              border: DECK_CONTROL_BORDER,
                              borderRadius: '999px',
                              cursor: 'pointer',
                              fontSize: 12,
                              fontWeight: 600
                            }}
                          >
                            Sync
                          </button>
                        )}
                        <button
                          onClick={() => handlePublishClick(deck)}
                          style={{
                            padding: '6px 10px',
                            background: deck.published
                              ? 'color-mix(in srgb, var(--color-state-warning) 14%, var(--color-bg-surface))'
                              : 'transparent',
                            color: deck.published ? 'var(--color-state-warning)' : 'var(--color-text-primary)',
                            border: DECK_CONTROL_BORDER,
                            borderRadius: '999px',
                            cursor: 'pointer',
                            fontSize: 12,
                            fontWeight: 600
                          }}
                        >
                          {deck.published ? 'Unpub' : 'Pub'}
                        </button>
                        <button
                          onClick={() => handleDeleteDeck(deck.id)}
                          style={{
                            padding: '6px 10px',
                            background: 'transparent',
                            color: 'var(--color-state-danger)',
                            border: '1px solid color-mix(in srgb, var(--color-state-danger) 38%, var(--color-border-paper))',
                            borderRadius: '999px',
                            cursor: 'pointer',
                            fontSize: 12,
                            fontWeight: 600
                          }}
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* @@@ Community Decks Section */}
          <hr style={{ margin: '1rem 0 0', border: 0, borderTop: DECK_ITEM_BORDER }} />

          <h3 style={{
            margin: '16px 0',
            fontSize: '16px',
            fontWeight: '500',
            color: 'var(--color-text-primary)'
          }}>
            {t('deck.sections.community', { count: communityDecks.length })}
          </h3>

          {communityDecks.length === 0 ? (
            <p style={{
              color: 'var(--color-text-muted)',
              fontSize: '14px',
              fontStyle: 'italic',
              textAlign: 'center',
              padding: '1.2rem',
              borderRadius: '0.75rem',
              background: DECK_LIST_SURFACE
            }}>
              {t('deck.communityEmpty')}
            </p>
          ) : (
            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 14,
              alignItems: 'stretch'
            }}>
              {communityDecks.map(deck => {
                const Icon = iconMap[deck.icon as keyof typeof iconMap] || iconMap.brain;
                const colorHex = COLORS[deck.color as keyof typeof COLORS]?.hex || 'var(--color-action-link)';

                return (
                  <div
                    key={deck.id}
                    style={{
                      background: DECK_LIST_SURFACE,
                      border: DECK_ITEM_BORDER,
                      borderLeft: `3px solid ${colorHex}`,
                      borderRadius: '0.75rem',
                      padding: '0.82rem 0.9rem',
                      boxShadow: 'none',
                      transition: 'transform 0.15s, background 0.15s',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 10,
                      flex: '1 1 320px',
                      minWidth: 0,
                      maxWidth: '100%'
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-1px)';
                      (e.currentTarget as HTMLDivElement).style.background = DECK_ITEM_HOVER_SURFACE;
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLDivElement).style.transform = 'translateY(0)';
                      (e.currentTarget as HTMLDivElement).style.background = DECK_LIST_SURFACE;
                    }}
                  >
                    <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                      <div style={{
                        width: 50,
                        height: 50,
                        borderRadius: '0.72rem',
                        border: `1px solid color-mix(in srgb, ${colorHex} 24%, var(--color-border-paper))`,
                        background: `color-mix(in srgb, ${colorHex} 12%, var(--color-bg-paper))`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: colorHex,
                        flexShrink: 0,
                        boxShadow: 'none'
                      }}>
                        <Icon size={24} />
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontSize: 17,
                          fontWeight: 700,
                          color: 'var(--color-text-primary)',
                          marginBottom: 4,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }}>
                          {deck.name}
                        </div>
                        <div style={{
                          fontSize: 12,
                          color: 'var(--color-text-secondary)',
                          marginBottom: 4,
                          lineHeight: 1.4,
                          maxHeight: 32,
                          overflow: 'hidden'
                        }}>
                          {deck.description || 'No description'}
                        </div>
                        <div style={{
                          fontSize: 11,
                          color: 'var(--color-text-muted)'
                        }}>
                          {t('deck.communityMeta', {
                            author: deck.author_name || t('deck.labels.anonymous'),
                            voices: deck.voice_count || 0,
                            installs: deck.install_count || 0
                          })}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-start' }}>
                      <button
                        onClick={() => handleInstallDeck(deck.id)}
                        style={{
                          padding: '6px 12px',
                          background: 'var(--color-text-primary)',
                          color: 'var(--color-bg-app)',
                          border: 'none',
                          borderRadius: '999px',
                          fontSize: 12,
                          fontWeight: 600,
                          cursor: 'pointer',
                          transition: 'all 0.2s'
                        }}
                      >
                        Install
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Deck editor modal */}
      {activeDeck && (
        <DeckEditorModal
          deck={activeDeck}
          isSystem={!!activeDeck.is_system}
          selectedVoiceId={selectedVoiceByDeck[activeDeck.id] || activeDeck.voices?.[0]?.id || null}
          onSelectVoice={(voiceId) => setSelectedVoiceByDeck(prev => ({ ...prev, [activeDeck.id]: voiceId }))}
          onClose={() => setActiveDeckId(null)}
          creatingVoiceId={creatingVoice}
          onAddVoice={handleAddVoice}
          onUpdateDeck={handleUpdateDeck}
          onUpdateVoice={handleUpdateVoice}
          onToggleVoice={handleToggleVoice}
          onDeleteVoice={handleDeleteVoice}
          onOpenChat={onOpenChat}
        />
      )}

      {/* @@@ Publish Warning Modal */}
      {publishWarning && (
        <div
          className="modal-overlay"
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'var(--color-bg-overlay)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999
          }}
          onClick={() => setPublishWarning(null)}
        >
          <div
            className="modal-content"
            style={{
              background: 'var(--color-bg-surface-solid)',
              color: 'var(--color-text-primary)',
              border: DECK_CONTROL_BORDER,
              padding: '24px',
              borderRadius: '0.9rem',
              maxWidth: '400px',
              boxShadow: '0 4px 12px var(--color-shadow-medium)'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ marginBottom: '16px', fontSize: '18px', fontWeight: 600 }}>
              {t('deck.publishWarning.heading')}
            </h3>

            <p style={{ marginBottom: '16px', lineHeight: '1.5', fontSize: '14px' }}>
              <span dangerouslySetInnerHTML={{ __html: t('deck.publishWarning.body') }} />
            </p>

            <p style={{ marginBottom: '16px', color: 'var(--color-state-error)', fontSize: '13px', lineHeight: '1.5' }}>
              {t('deck.publishWarning.note')}
            </p>

            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setPublishWarning(null)}
                style={{
                  padding: '8px 16px',
                  background: 'transparent',
                  color: 'var(--color-text-primary)',
                  border: DECK_CONTROL_BORDER,
                  borderRadius: '999px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 500
                }}
              >
                {t('deck.publishWarning.cancel')}
              </button>
              <button
                onClick={() => handlePublishToggle(publishWarning)}
                style={{
                  padding: '8px 16px',
                  background: 'var(--color-text-primary)',
                  color: 'var(--color-bg-app)',
                  border: 'none',
                  borderRadius: '999px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 500
                }}
              >
                {t('deck.publishWarning.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

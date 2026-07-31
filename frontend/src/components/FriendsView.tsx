import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  generateInviteCode,
  useInviteCode,
  getFriendRequests,
  acceptFriendRequest,
  rejectFriendRequest,
  getFriends,
  removeFriend,
  type FriendInvite,
  type FriendRequest,
  type Friend
} from '../api/voiceApi';

interface Props {
  isVisible: boolean;
  onViewFriendTimeline?: (friendId: number, friendName: string) => void;
}

export default function FriendsView({ isVisible, onViewFriendTimeline }: Props) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<'friends' | 'requests' | 'invite'>('friends');

  // Invite state
  const [inviteCode, setInviteCode] = useState<FriendInvite | null>(null);
  const [generatingInvite, setGeneratingInvite] = useState(false);
  const [inputCode, setInputCode] = useState('');
  const [usingCode, setUsingCode] = useState(false);
  const [codeMessage, setCodeMessage] = useState('');

  // Friends state
  const [friends, setFriends] = useState<Friend[]>([]);
  const [loadingFriends, setLoadingFriends] = useState(false);

  // Requests state
  const [requests, setRequests] = useState<FriendRequest[]>([]);
  const [loadingRequests, setLoadingRequests] = useState(false);

  // Load friends on mount
  useEffect(() => {
    if (isVisible && activeTab === 'friends') {
      loadFriends();
    }
  }, [isVisible, activeTab]);

  // Load requests on mount
  useEffect(() => {
    if (isVisible && activeTab === 'requests') {
      loadRequests();
    }
  }, [isVisible, activeTab]);

  const loadFriends = async () => {
    setLoadingFriends(true);
    try {
      const data = await getFriends();
      setFriends(data);
    } catch (err) {
      console.error('Failed to load friends:', err);
    } finally {
      setLoadingFriends(false);
    }
  };

  const loadRequests = async () => {
    setLoadingRequests(true);
    try {
      const data = await getFriendRequests();
      setRequests(data);
    } catch (err) {
      console.error('Failed to load requests:', err);
    } finally {
      setLoadingRequests(false);
    }
  };

  const handleGenerateInvite = async () => {
    setGeneratingInvite(true);
    try {
      const invite = await generateInviteCode();
      setInviteCode(invite);
    } catch (err) {
      console.error('Failed to generate invite:', err);
      alert(t('friends.generateError') || 'Failed to generate invite code');
    } finally {
      setGeneratingInvite(false);
    }
  };

  const handleUseCode = async () => {
    if (!inputCode.trim()) return;

    setUsingCode(true);
    setCodeMessage('');
    try {
      const result = await useInviteCode(inputCode.trim());
      setCodeMessage(result.message || t('friends.requestSent') || 'Friend request sent!');
      setInputCode('');
      // Refresh requests to see if there are any new ones
      setTimeout(() => loadRequests(), 500);
    } catch (err: any) {
      setCodeMessage(err.message || t('friends.useCodeError') || 'Invalid or expired code');
    } finally {
      setUsingCode(false);
    }
  };

  const handleAcceptRequest = async (requestId: number) => {
    try {
      await acceptFriendRequest(requestId);
      // Refresh both requests and friends
      loadRequests();
      loadFriends();
    } catch (err) {
      console.error('Failed to accept request:', err);
      alert(t('friends.acceptError') || 'Failed to accept request');
    }
  };

  const handleRejectRequest = async (requestId: number) => {
    try {
      await rejectFriendRequest(requestId);
      loadRequests();
    } catch (err) {
      console.error('Failed to reject request:', err);
      alert(t('friends.rejectError') || 'Failed to reject request');
    }
  };

  const handleRemoveFriend = async (friendId: number) => {
    if (!confirm(t('friends.confirmRemove') || 'Remove this friend?')) return;

    try {
      await removeFriend(friendId);
      loadFriends();
    } catch (err) {
      console.error('Failed to remove friend:', err);
      alert(t('friends.removeError') || 'Failed to remove friend');
    }
  };

  const handleCopyCode = () => {
    if (inviteCode) {
      navigator.clipboard.writeText(inviteCode.code);
      alert(t('friends.codeCopied') || 'Code copied to clipboard!');
    }
  };

  if (!isVisible) return null;

  return (
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
      background: 'var(--color-bg-app)',
      overflow: 'hidden'
    }}>
      {/* Tab Navigation */}
      <div style={{
        display: 'flex',
        gap: 16,
        padding: '24px 32px 0',
        borderBottom: '1px solid var(--color-border-paper)'
      }}>
        <button
          onClick={() => setActiveTab('friends')}
          style={{
            padding: '12px 24px',
            border: 'none',
            background: 'transparent',
            fontSize: 15,
            fontWeight: activeTab === 'friends' ? 600 : 400,
            cursor: 'pointer',
            color: activeTab === 'friends' ? 'var(--color-text-primary)' : '#888',
            borderBottom: activeTab === 'friends' ? '3px solid var(--color-text-primary)' : '3px solid transparent',
            transition: 'all 0.2s'
          }}
        >
          {t('friends.myFriends') || 'My Friends'} {friends.length > 0 && `(${friends.length})`}
        </button>
        <button
          onClick={() => setActiveTab('requests')}
          style={{
            padding: '12px 24px',
            border: 'none',
            background: 'transparent',
            fontSize: 15,
            fontWeight: activeTab === 'requests' ? 600 : 400,
            cursor: 'pointer',
            color: activeTab === 'requests' ? 'var(--color-text-primary)' : '#888',
            borderBottom: activeTab === 'requests' ? '3px solid var(--color-text-primary)' : '3px solid transparent',
            transition: 'all 0.2s'
          }}
        >
          {t('friends.requests') || 'Requests'} {requests.length > 0 && `(${requests.length})`}
        </button>
        <button
          onClick={() => setActiveTab('invite')}
          style={{
            padding: '12px 24px',
            border: 'none',
            background: 'transparent',
            fontSize: 15,
            fontWeight: activeTab === 'invite' ? 600 : 400,
            cursor: 'pointer',
            color: activeTab === 'invite' ? 'var(--color-text-primary)' : '#888',
            borderBottom: activeTab === 'invite' ? '3px solid var(--color-text-primary)' : '3px solid transparent',
            transition: 'all 0.2s'
          }}
        >
          {t('friends.addFriend') || 'Add Friend'}
        </button>
      </div>

      {/* Content Area */}
      <div style={{
        flex: 1,
        overflow: 'auto',
        padding: 32
      }}>
        {/* Friends Tab */}
        {activeTab === 'friends' && (
          <div>
            <h2 style={{ fontSize: 24, marginBottom: 24, fontWeight: 600 }}>
              {t('friends.myFriends') || 'My Friends'}
            </h2>

            {loadingFriends ? (
              <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
                {t('friends.loading') || 'Loading...'}
              </div>
            ) : friends.length === 0 ? (
              <div style={{
                textAlign: 'center',
                padding: 60,
                color: '#888',
                fontSize: 15
              }}>
                {t('friends.noFriends') || 'No friends yet. Use an invite code to add your first friend!'}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {friends.map(friend => (
                  <div
                    key={friend.friend_id ?? friend.id ?? ('friend-' + (friend.friend_email ?? 'unknown'))}
                    style={{
                    background: '#fff',
                    border: '1px solid var(--color-border-paper)',
                    borderRadius: 8,
                    padding: 20,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 16
                  }}>
                    <div style={{
                      width: 48,
                      height: 48,
                      borderRadius: 24,
                      background: 'var(--color-state-success)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#fff',
                      fontSize: 20,
                      fontWeight: 600
                    }}>
                      {friend.friend_name?.[0]?.toUpperCase() || friend.friend_email?.[0]?.toUpperCase() || 'F'}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 4 }}>
                        {friend.friend_name}
                      </div>
                      <div style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                        {friend.friend_email}
                      </div>
                    </div>
                    <button
                      onClick={() => onViewFriendTimeline?.(friend.friend_id, friend.friend_name)}
                      style={{
                        padding: '8px 16px',
                        background: 'var(--color-state-success)',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 6,
                        cursor: 'pointer',
                        fontSize: 14,
                        fontWeight: 500,
                        transition: 'background 0.2s'
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = '#45a049'}
                      onMouseLeave={e => e.currentTarget.style.background = 'var(--color-state-success)'}
                    >
                      {t('friends.viewTimeline') || 'View Timeline'}
                    </button>
                    <button
                      onClick={() => handleRemoveFriend(friend.friend_id)}
                      style={{
                        padding: '8px 16px',
                        background: 'var(--color-state-error)',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 6,
                        cursor: 'pointer',
                        fontSize: 14,
                        fontWeight: 500,
                        transition: 'background 0.2s'
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = '#da190b'}
                      onMouseLeave={e => e.currentTarget.style.background = 'var(--color-state-error)'}
                    >
                      {t('friends.remove') || 'Remove'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Requests Tab */}
        {activeTab === 'requests' && (
          <div>
            <h2 style={{ fontSize: 24, marginBottom: 24, fontWeight: 600 }}>
              {t('friends.requests') || 'Friend Requests'}
            </h2>

            {loadingRequests ? (
              <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
                {t('friends.loading') || 'Loading...'}
              </div>
            ) : requests.length === 0 ? (
              <div style={{
                textAlign: 'center',
                padding: 60,
                color: '#888',
                fontSize: 15
              }}>
                {t('friends.noRequests') || 'No pending friend requests'}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {requests.map(request => (
                  <div
                    key={request.id ?? ('request-' + (request.requester_email ?? 'unknown'))}
                    style={{
                    background: '#fff',
                    border: '1px solid var(--color-border-paper)',
                    borderRadius: 8,
                    padding: 20,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 16
                  }}>
                    <div style={{
                      width: 48,
                      height: 48,
                      borderRadius: 24,
                      background: '#2196F3',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#fff',
                      fontSize: 20,
                      fontWeight: 600
                    }}>
                      {request.requester_name?.[0]?.toUpperCase() || request.requester_email?.[0]?.toUpperCase() || 'R'}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 4 }}>
                        {request.requester_name}
                      </div>
                      <div style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                        {request.requester_email}
                      </div>
                    </div>
                    <button
                      onClick={() => handleAcceptRequest(request.id)}
                      style={{
                        padding: '8px 16px',
                        background: 'var(--color-state-success)',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 6,
                        cursor: 'pointer',
                        fontSize: 14,
                        fontWeight: 500,
                        transition: 'background 0.2s'
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = '#45a049'}
                      onMouseLeave={e => e.currentTarget.style.background = 'var(--color-state-success)'}
                    >
                      {t('friends.accept') || 'Accept'}
                    </button>
                    <button
                      onClick={() => handleRejectRequest(request.id)}
                      style={{
                        padding: '8px 16px',
                        background: 'var(--color-state-error)',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 6,
                        cursor: 'pointer',
                        fontSize: 14,
                        fontWeight: 500,
                        transition: 'background 0.2s'
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = '#da190b'}
                      onMouseLeave={e => e.currentTarget.style.background = 'var(--color-state-error)'}
                    >
                      {t('friends.reject') || 'Reject'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Invite Tab */}
        {activeTab === 'invite' && (
          <div>
            <h2 style={{ fontSize: 24, marginBottom: 24, fontWeight: 600 }}>
              {t('friends.addFriend') || 'Add Friend'}
            </h2>

            {/* Generate Invite Code */}
            <div style={{
              background: '#fff',
              border: '1px solid var(--color-border-paper)',
              borderRadius: 8,
              padding: 24,
              marginBottom: 32
            }}>
              <h3 style={{ fontSize: 18, marginBottom: 12, fontWeight: 600 }}>
                {t('friends.generateInvite') || 'Generate Invite Code'}
              </h3>
              <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', marginBottom: 16 }}>
                {t('friends.generateHint') || 'Share this code with someone to let them send you a friend request. Code expires in 7 days.'}
              </p>

              {inviteCode ? (
                <div>
                  <div style={{
                    background: '#f5f5f5',
                    padding: 16,
                    borderRadius: 6,
                    marginBottom: 12,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12
                  }}>
                    <div style={{
                      flex: 1,
                      fontSize: 24,
                      fontWeight: 700,
                      fontFamily: 'monospace',
                      letterSpacing: 4,
                      textAlign: 'center'
                    }}>
                      {inviteCode.code}
                    </div>
                    <button
                      onClick={handleCopyCode}
                      style={{
                        padding: '8px 16px',
                        background: '#2196F3',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 6,
                        cursor: 'pointer',
                        fontSize: 14,
                        fontWeight: 500
                      }}
                    >
                      {t('friends.copy') || 'Copy'}
                    </button>
                  </div>
                  <div style={{ fontSize: 12, color: '#888' }}>
                    {t('friends.expiresAt') || 'Expires'}: {new Date(inviteCode.expires_at).toLocaleString()}
                  </div>
                </div>
              ) : (
                <button
                  onClick={handleGenerateInvite}
                  disabled={generatingInvite}
                  style={{
                    padding: '12px 24px',
                    background: generatingInvite ? '#ccc' : 'var(--color-state-success)',
                    color: '#fff',
                    border: 'none',
                    borderRadius: 6,
                    cursor: generatingInvite ? 'not-allowed' : 'pointer',
                    fontSize: 15,
                    fontWeight: 500
                  }}
                >
                  {generatingInvite ? (t('friends.generating') || 'Generating...') : (t('friends.generate') || 'Generate Code')}
                </button>
              )}
            </div>

            {/* Use Invite Code */}
            <div style={{
              background: '#fff',
              border: '1px solid var(--color-border-paper)',
              borderRadius: 8,
              padding: 24
            }}>
              <h3 style={{ fontSize: 18, marginBottom: 12, fontWeight: 600 }}>
                {t('friends.useInvite') || 'Use Invite Code'}
              </h3>
              <p style={{ fontSize: 14, color: 'var(--color-text-secondary)', marginBottom: 16 }}>
                {t('friends.useHint') || 'Enter a friend\'s invite code to send them a friend request.'}
              </p>

              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <input
                  type="text"
                  value={inputCode}
                  onChange={e => setInputCode(e.target.value.toUpperCase())}
                  placeholder={t('friends.codePlaceholder') || 'Enter 6-character code'}
                  maxLength={6}
                  style={{
                    flex: 1,
                    padding: '12px 16px',
                    border: '1px solid var(--color-border-paper)',
                    borderRadius: 6,
                    fontSize: 16,
                    fontFamily: 'monospace',
                    letterSpacing: 2,
                    textTransform: 'uppercase'
                  }}
                />
                <button
                  onClick={handleUseCode}
                  disabled={usingCode || inputCode.length !== 6}
                  style={{
                    padding: '12px 24px',
                    background: (usingCode || inputCode.length !== 6) ? '#ccc' : '#2196F3',
                    color: '#fff',
                    border: 'none',
                    borderRadius: 6,
                    cursor: (usingCode || inputCode.length !== 6) ? 'not-allowed' : 'pointer',
                    fontSize: 15,
                    fontWeight: 500
                  }}
                >
                  {usingCode ? (t('friends.sending') || 'Sending...') : (t('friends.send') || 'Send Request')}
                </button>
              </div>

              {codeMessage && (
                <div style={{
                  marginTop: 12,
                  padding: 12,
                  background: codeMessage.includes('sent') || codeMessage.includes('成功') ? '#e8f5e9' : '#ffebee',
                  color: codeMessage.includes('sent') || codeMessage.includes('成功') ? '#2e7d32' : '#c62828',
                  borderRadius: 6,
                  fontSize: 14
                }}>
                  {codeMessage}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

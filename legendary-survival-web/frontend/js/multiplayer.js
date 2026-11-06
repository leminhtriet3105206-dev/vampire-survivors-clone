// Real-Time Co-op Multiplayer Manager (Socket.io)
// Handles party creation, room code joining, lobby readiness, and transition to co-op dungeon.

import { getSocket } from './chat.js';
import { store } from './store.js';
import { toast, skinAvatar, setBusy } from './ui.js';

let currentRoom = null;
let isHost = false;
let isReady = false;
let onStartDungeonCallback = null;
let onStartRankedMatchCallback = null;

// Ranked Matchmaking Queue State
let inRankedQueue = false;
let queueStartTime = 0;
let queueTimerInterval = null;

// DOM Element cache
let modalEntry = null;
let modalLobby = null;
let inputCode = null;
let errorEntry = null;
let errorLobby = null;
let codeDisplay = null;
let playerCount = null;
let playersGrid = null;
let lobbyStatus = null;
let btnToggleReady = null;
let btnStartDungeon = null;

// Ranked Queue DOM cache
let modalRankedQueue = null;
let rankedQueueTimer = null;
let rankedQueueCount = null;
let rankedQueueFill = null;
let btnFillQueueBots = null;
let btnCancelQueue = null;
let btnRanked3v3 = null;

let socketListenersAttached = false;

function showError(target, message) {
  if (!target) return;
  if (!message) {
    target.textContent = '';
    target.classList.add('hidden');
  } else {
    target.textContent = message;
    target.classList.remove('hidden');
  }
}

export function openCoopEntry() {
  if (!modalEntry) return;
  showError(errorEntry, '');
  if (inputCode) inputCode.value = '';
  modalEntry.classList.remove('hidden');
}

export function closeCoopEntry() {
  if (modalEntry) modalEntry.classList.add('hidden');
}

export function closeCoopLobby() {
  if (modalLobby) modalLobby.classList.add('hidden');
}

export function getCurrentRoom() {
  return currentRoom;
}

export function isCurrentHost() {
  return isHost;
}

function attachSocketListeners() {
  const socket = getSocket();
  if (!socket || socketListenersAttached) return;

  socket.on('room:update', (room) => {
    currentRoom = room;
    renderLobby(room);
  });

  socket.on('room:playerLeft', ({ username, reason, room }) => {
    toast(`👋 ${username} left the room (${reason})`, 'info', 3000);
    currentRoom = room;
    renderLobby(room);
  });

  socket.on('room:started', (room) => {
    currentRoom = room;
    closeCoopLobby();
    closeCoopEntry();
    if (typeof onStartDungeonCallback === 'function') {
      const sock = getSocket();
      onStartDungeonCallback({
        room,
        isHost: room.hostSocketId === sock.id,
        socket: sock,
      });
    }
  });

  // ── Phase 4: 3v3 Ranked Matchmaking Listeners ─────────────
  socket.on('ranked:queueStatus', (data) => {
    updateRankedQueueUI(data?.queueSize ?? 0, data?.target || 6);
  });

  const onMatch = (matchPayload) => {
    stopRankedQueueTimer();
    closeRankedQueue();
    toast(`🏆 MATCH FOUND! Red vs Blue 3v3 PvE Race!`, 'success', 3500);
    if (typeof onStartRankedMatchCallback === 'function') {
      const sock = getSocket();
      onStartRankedMatchCallback({
        matchData: matchPayload,
        socket: sock,
      });
    }
  };

  socket.on('ranked:matchFound', onMatch);
  socket.on('matchFound', onMatch);

  socketListenersAttached = true;
}

function startRankedQueueTimer() {
  stopRankedQueueTimer();
  queueStartTime = Date.now();
  if (rankedQueueTimer) rankedQueueTimer.textContent = 'Searching: 00:00';
  queueTimerInterval = setInterval(() => {
    const elapsedSecs = Math.floor((Date.now() - queueStartTime) / 1000);
    const mins = Math.floor(elapsedSecs / 60);
    const secs = elapsedSecs % 60;
    if (rankedQueueTimer) {
      rankedQueueTimer.textContent = `Searching: ${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }
  }, 1000);
}

function stopRankedQueueTimer() {
  if (queueTimerInterval) {
    clearInterval(queueTimerInterval);
    queueTimerInterval = null;
  }
}

export function openRankedQueue() {
  const socket = getSocket();
  if (!socket || !socket.connected) {
    toast('Connecting to multiplayer server, please wait...', 'warning');
    return;
  }
  attachSocketListeners();

  inRankedQueue = true;
  if (modalRankedQueue) modalRankedQueue.classList.remove('hidden');
  startRankedQueueTimer();
  socket.emit('ranked:joinQueue', {}, (res) => {
    if (res && res.queueSize !== undefined) {
      updateRankedQueueUI(res.queueSize, res.target || 6);
    }
  });
}

export function closeRankedQueue() {
  inRankedQueue = false;
  stopRankedQueueTimer();
  if (modalRankedQueue) modalRankedQueue.classList.add('hidden');
}

function updateRankedQueueUI(queueSize, target = 6) {
  if (rankedQueueCount) {
    rankedQueueCount.textContent = `${queueSize} / ${target}`;
  }
  if (rankedQueueFill) {
    const pct = Math.min(100, Math.max(0, (queueSize / target) * 100));
    rankedQueueFill.style.width = `${pct}%`;
  }
}

function handleFillQueueBots() {
  const socket = getSocket();
  if (!socket || !socket.connected) return;
  if (btnFillQueueBots) btnFillQueueBots.disabled = true;
  socket.emit('ranked:fillQueueBots', {}, (res) => {
    if (btnFillQueueBots) btnFillQueueBots.disabled = false;
    if (res && !res.ok) {
      toast(res.error || 'Failed to fill queue with AI', 'error');
    }
  });
}

function handleLeaveRankedQueue() {
  const socket = getSocket();
  if (socket && socket.connected) {
    socket.emit('ranked:leaveQueue', {});
  }
  closeRankedQueue();
  toast('Left 3v3 ranked queue', 'info', 2000);
}

export function initMultiplayer({ onStartDungeon, onStartRankedMatch } = {}) {
  onStartDungeonCallback = onStartDungeon;
  onStartRankedMatchCallback = onStartRankedMatch;

  modalEntry = document.getElementById('coop-entry-modal');
  modalLobby = document.getElementById('coop-lobby-modal');
  inputCode = document.getElementById('join-room-code');
  errorEntry = document.getElementById('coop-entry-error');
  errorLobby = document.getElementById('room-lobby-error');
  codeDisplay = document.getElementById('room-code-display');
  playerCount = document.getElementById('lobby-player-count');
  playersGrid = document.getElementById('room-players-grid');
  lobbyStatus = document.getElementById('room-lobby-status');
  btnToggleReady = document.getElementById('btn-toggle-ready');
  btnStartDungeon = document.getElementById('btn-start-dungeon');

  modalRankedQueue = document.getElementById('ranked-queue-modal');
  rankedQueueTimer = document.getElementById('ranked-queue-timer');
  rankedQueueCount = document.getElementById('ranked-queue-count');
  rankedQueueFill = document.getElementById('ranked-queue-fill');
  btnFillQueueBots = document.getElementById('btn-fill-queue-bots');
  btnCancelQueue = document.getElementById('btn-cancel-queue');
  btnRanked3v3 = document.getElementById('ranked-3v3-btn');

  if (btnRanked3v3) btnRanked3v3.addEventListener('click', openRankedQueue);
  if (btnFillQueueBots) btnFillQueueBots.addEventListener('click', handleFillQueueBots);
  if (btnCancelQueue) btnCancelQueue.addEventListener('click', handleLeaveRankedQueue);

  const btnCoop = document.getElementById('coop-dungeon-btn');
  const btnCloseEntry = document.getElementById('btn-close-coop-entry');
  const btnCreate = document.getElementById('btn-create-room');
  const btnJoin = document.getElementById('btn-join-room');
  const btnCopy = document.getElementById('btn-copy-code');
  const btnLeave = document.getElementById('btn-leave-room');

  if (btnCoop) btnCoop.addEventListener('click', openCoopEntry);
  if (btnCloseEntry) btnCloseEntry.addEventListener('click', closeCoopEntry);

  if (inputCode) {
    inputCode.addEventListener('input', () => {
      inputCode.value = inputCode.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
    });
    inputCode.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleJoinRoom();
      }
    });
  }

  if (btnCreate) btnCreate.addEventListener('click', handleCreateRoom);
  if (btnJoin) btnJoin.addEventListener('click', handleJoinRoom);

  if (btnCopy) {
    btnCopy.addEventListener('click', () => {
      if (!currentRoom) return;
      navigator.clipboard?.writeText(currentRoom.code).then(() => {
        toast(`Room code ${currentRoom.code} copied!`, 'info', 2000);
      }).catch(() => {
        toast(`Code: ${currentRoom.code}`, 'info', 4000);
      });
    });
  }

  if (btnToggleReady) {
    btnToggleReady.addEventListener('click', handleToggleReady);
  }

  if (btnStartDungeon) {
    btnStartDungeon.addEventListener('click', handleStartDungeon);
  }

  if (btnLeave) {
    btnLeave.addEventListener('click', handleLeaveRoom);
  }
}

async function handleCreateRoom(e) {
  const socket = getSocket();
  if (!socket || !socket.connected) {
    showError(errorEntry, 'Cannot connect to multiplayer server. Please wait...');
    return;
  }
  attachSocketListeners();

  const restore = setBusy(e.currentTarget, 'Creating...');
  showError(errorEntry, '');

  socket.timeout(6000).emit('room:create', {}, (err, res) => {
    restore();
    if (err) return showError(errorEntry, 'Server timeout. Please try again.');
    if (!res || !res.ok) return showError(errorEntry, (res && res.error) || 'Could not create room');

    currentRoom = res.room;
    isHost = true;
    isReady = true;
    closeCoopEntry();
    openLobby();
  });
}

async function handleJoinRoom() {
  const socket = getSocket();
  if (!socket || !socket.connected) {
    showError(errorEntry, 'Cannot connect to multiplayer server. Please wait...');
    return;
  }
  attachSocketListeners();

  const code = (inputCode?.value || '').trim().toUpperCase();
  if (!code || code.length < 3) {
    showError(errorEntry, 'Please enter a valid room code (e.g. X7B9Q)');
    return;
  }

  const joinBtn = document.getElementById('btn-join-room');
  const restore = setBusy(joinBtn, 'Joining...');
  showError(errorEntry, '');

  socket.timeout(6000).emit('room:join', { code }, (err, res) => {
    restore();
    if (err) return showError(errorEntry, 'Server timeout. Please try again.');
    if (!res || !res.ok) return showError(errorEntry, (res && res.error) || 'Failed to join room');

    currentRoom = res.room;
    isHost = currentRoom.hostSocketId === socket.id;
    isReady = false;
    closeCoopEntry();
    openLobby();
  });
}

function handleToggleReady() {
  const socket = getSocket();
  if (!socket || !socket.connected || !currentRoom) return;

  const nextReady = !isReady;
  socket.emit('room:ready', { ready: nextReady }, (res) => {
    if (res && res.ok) {
      isReady = res.ready;
      if (btnToggleReady) {
        btnToggleReady.textContent = isReady ? 'Cancel Ready' : 'Mark Ready';
        btnToggleReady.className = isReady ? 'btn btn-primary' : 'btn btn-secondary';
      }
    }
  });
}

function handleStartDungeon(e) {
  const socket = getSocket();
  if (!socket || !socket.connected || !currentRoom) return;

  const restore = setBusy(e.currentTarget, 'Launching...');
  showError(errorLobby, '');

  socket.timeout(6000).emit('room:start', {}, (err, res) => {
    restore();
    if (err) return showError(errorLobby, 'Server timeout starting dungeon');
    if (!res || !res.ok) {
      showError(errorLobby, (res && res.error) || 'Could not start dungeon');
    }
  });
}

function handleLeaveRoom() {
  const socket = getSocket();
  if (socket && currentRoom) {
    socket.emit('room:leave', {});
  }
  currentRoom = null;
  isHost = false;
  isReady = false;
  closeCoopLobby();
  toast('Left the dungeon party', 'info', 2000);
}

function openLobby() {
  if (!modalLobby) return;
  modalLobby.classList.remove('hidden');
  renderLobby(currentRoom);
}

function renderLobby(room) {
  if (!room || !modalLobby) return;
  const socket = getSocket();
  const myId = socket ? socket.id : null;

  isHost = room.hostSocketId === myId;
  const me = room.players.find((p) => p.socketId === myId);
  if (me) isReady = me.ready;

  // Header code & count
  if (codeDisplay) codeDisplay.textContent = room.code;
  if (playerCount) playerCount.textContent = String(room.players.length);

  // 4 Player Slots
  if (playersGrid) {
    playersGrid.replaceChildren();

    for (let i = 0; i < room.maxPlayers; i++) {
      const p = room.players[i];
      const slot = document.createElement('div');

      if (p) {
        slot.className = `player-slot${p.ready ? ' slot-ready' : ''}${p.isHost ? ' slot-host' : ''}`;

        const avatarWrapper = document.createElement('div');
        avatarWrapper.className = 'slot-avatar';
        const skin = store.skinBySlug(p.skin) || { colors: undefined, emblem: p.username[0] };
        avatarWrapper.appendChild(skinAvatar(skin, 'md'));

        const nameLabel = document.createElement('span');
        nameLabel.className = 'slot-name';
        nameLabel.textContent = p.username + (p.socketId === myId ? ' (You)' : '');

        const tag = document.createElement('span');
        if (p.isHost) {
          tag.className = 'slot-tag tag-host';
          tag.textContent = 'HOST';
        } else if (p.ready) {
          tag.className = 'slot-tag tag-ready';
          tag.textContent = 'READY';
        } else {
          tag.className = 'slot-tag tag-waiting';
          tag.textContent = 'WAITING';
        }

        slot.appendChild(avatarWrapper);
        slot.appendChild(nameLabel);
        slot.appendChild(tag);
      } else {
        slot.className = 'player-slot slot-empty';
        slot.innerHTML = `
          <div class="slot-avatar" style="font-size: 1.5rem; color: var(--muted);">➕</div>
          <span class="slot-name" style="color: var(--muted);">Open Slot</span>
          <span class="slot-tag tag-waiting">EMPTY</span>
        `;
      }
      playersGrid.appendChild(slot);
    }
  }

  // Action controls based on Host vs Client
  const allNonHostsReady = room.players.every((p) => p.isHost || p.ready);

  if (isHost) {
    if (btnToggleReady) btnToggleReady.classList.add('hidden');
    if (btnStartDungeon) {
      btnStartDungeon.classList.remove('hidden');
      btnStartDungeon.disabled = !allNonHostsReady;
    }
    if (lobbyStatus) {
      lobbyStatus.textContent = allNonHostsReady
        ? '👑 All party members are ready! You can now start the dungeon.'
        : '⏳ Waiting for party members to mark Ready...';
      lobbyStatus.style.color = allNonHostsReady ? '#72ffb8' : '#ffd87a';
    }
  } else {
    if (btnStartDungeon) btnStartDungeon.classList.add('hidden');
    if (btnToggleReady) {
      btnToggleReady.classList.remove('hidden');
      btnToggleReady.textContent = isReady ? 'Cancel Ready' : 'Mark Ready';
      btnToggleReady.className = isReady ? 'btn btn-primary' : 'btn btn-secondary';
    }
    if (lobbyStatus) {
      lobbyStatus.textContent = isReady
        ? '✅ You are ready! Waiting for Host to start...'
        : '⚠️ Click "Mark Ready" when you are set to enter the dungeon!';
      lobbyStatus.style.color = isReady ? '#72ffb8' : '#ffd87a';
    }
  }
}


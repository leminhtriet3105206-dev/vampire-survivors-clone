'use strict';

const User = require('../models/User');
const { getRankTier } = require('../models/User');

const QUEUE_TARGET_SIZE = 6;
const MATCH_DURATION_SECONDS = 180; // 3 minutes
const WIN_RP = 25;
const WIN_RUBIES = 5;
const LOSS_RP = -15;
const LOSS_RUBIES = 0;
const TIE_RP = 5;
const TIE_RUBIES = 1;

const VALID_EMOJIS = ['😡', '😭', '💀', '❤️', '🤡'];

const rankedQueue = []; // array of player queue descriptors
const socketToRankedRoom = new Map(); // socketId -> roomId
const rankedRooms = new Map(); // roomId -> RankedRoom

const BOT_TEMPLATES = [
  { username: 'Shadow_Ninja', skin: 'shadow-shinobi', frame: 'default', rankPoints: 140 },
  { username: 'Demon_Slayer', skin: 'flame-slayer', frame: 'frame-challenger', rankPoints: 320 },
  { username: 'Super_Saiyan', skin: 'golden-saiyan', frame: 'frame-diamond', rankPoints: 450 },
  { username: 'Soul_Reaper', skin: 'soul-reaper', frame: 'default', rankPoints: 210 },
  { username: 'Titan_Hunter', skin: 'titan-scout', frame: 'default', rankPoints: 95 },
  { username: 'Pirate_King', skin: 'rubber-pirate-king', frame: 'frame-challenger', rankPoints: 680 },
];

function sanitizePlayer(p) {
  return {
    socketId: p.socketId,
    userId: p.userId,
    username: p.username,
    skin: p.skin,
    frame: p.frame,
    rankPoints: p.rankPoints,
    rankTier: getRankTier(p.rankPoints || 0),
    team: p.team,
    isBot: Boolean(p.isBot),
  };
}

function broadcastQueueStatus(io) {
  io.emit('ranked:queueStatus', {
    queueSize: rankedQueue.length,
    target: QUEUE_TARGET_SIZE,
  });
}

async function resolveRankedMatch(io, room) {
  if (!room || room.rewardGranted) return;
  room.rewardGranted = true;
  room.state = 'ended';
  if (room.timerInterval) clearInterval(room.timerInterval);

  let winner = 'tie';
  if (room.redScore > room.blueScore) winner = 'red';
  else if (room.blueScore > room.redScore) winner = 'blue';

  const userUpdates = [];
  const allPlayers = [...room.redTeam, ...room.blueTeam];

  for (const p of allPlayers) {
    if (p.isBot || !p.userId) continue;

    const isWinner = winner !== 'tie' && p.team === winner;
    const isTie = winner === 'tie';

    const rpChange = isTie ? TIE_RP : (isWinner ? WIN_RP : LOSS_RP);
    const rubiesEarned = isTie ? TIE_RUBIES : (isWinner ? WIN_RUBIES : LOSS_RUBIES);

    try {
      const userDoc = await User.findById(p.userId);
      if (userDoc) {
        const currentRP = userDoc.rankPoints || 0;
        const nextRP = Math.max(0, currentRP + rpChange);
        userDoc.rankPoints = nextRP;
        if (rubiesEarned > 0) {
          userDoc.currencies.rubies = (userDoc.currencies.rubies || 0) + rubiesEarned;
        }
        await userDoc.save();

        userUpdates.push({
          userId: p.userId,
          socketId: p.socketId,
          username: p.username,
          team: p.team,
          rpChange,
          rubiesEarned,
          newRankPoints: nextRP,
          newRankTier: getRankTier(nextRP),
          rubiesTotal: userDoc.currencies.rubies,
        });
      }
    } catch (err) {
      console.error(`[ranked] Failed to update rewards for user ${p.userId}:`, err.message);
    }
  }

  const endPayload = {
    roomId: room.roomId,
    winner,
    redScore: room.redScore,
    blueScore: room.blueScore,
    userUpdates,
    summary: {
      winRP: WIN_RP,
      winRubies: WIN_RUBIES,
      lossRP: LOSS_RP,
      lossRubies: LOSS_RUBIES,
    },
  };

  io.to(room.roomId).emit('ranked:matchEnded', endPayload);
  io.to(room.roomId).emit('matchEnded', endPayload);

  // Clean up room after 15 seconds
  setTimeout(() => {
    for (const p of allPlayers) {
      if (p.socketId) socketToRankedRoom.delete(p.socketId);
    }
    rankedRooms.delete(room.roomId);
  }, 15000);
}

function createRankedMatch(io) {
  if (rankedQueue.length < QUEUE_TARGET_SIZE) return;

  const matchCandidates = rankedQueue.splice(0, QUEUE_TARGET_SIZE);
  broadcastQueueStatus(io);

  // Shuffle candidates slightly
  for (let i = matchCandidates.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [matchCandidates[i], matchCandidates[j]] = [matchCandidates[j], matchCandidates[i]];
  }

  const roomId = 'RANKED_' + Date.now().toString(36).toUpperCase();
  const redTeam = matchCandidates.slice(0, 3).map((p) => ({ ...p, team: 'red' }));
  const blueTeam = matchCandidates.slice(3, 6).map((p) => ({ ...p, team: 'blue' }));

  const room = {
    roomId,
    redTeam,
    blueTeam,
    redScore: 0,
    blueScore: 0,
    duration: MATCH_DURATION_SECONDS,
    remainingSeconds: MATCH_DURATION_SECONDS,
    state: 'playing',
    rewardGranted: false,
    createdAt: Date.now(),
    timerInterval: null,
  };

  rankedRooms.set(roomId, room);

  // Join sockets & notify match found
  for (const p of [...redTeam, ...blueTeam]) {
    if (!p.isBot && p.socketId) {
      socketToRankedRoom.set(p.socketId, roomId);
      const socket = io.sockets.sockets.get(p.socketId);
      if (socket) {
        socket.join(roomId);
        const matchPayload = {
          roomId,
          duration: MATCH_DURATION_SECONDS,
          yourTeam: p.team,
          redTeam: redTeam.map(sanitizePlayer),
          blueTeam: blueTeam.map(sanitizePlayer),
        };
        socket.emit('ranked:matchFound', matchPayload);
        socket.emit('matchFound', matchPayload);
      }
    }
  }

  // 1-second countdown and 10Hz/1s score sync
  room.timerInterval = setInterval(() => {
    room.remainingSeconds -= 1;

    io.to(roomId).emit('ranked:scoreSync', {
      redScore: room.redScore,
      blueScore: room.blueScore,
      remainingSeconds: room.remainingSeconds,
    });

    if (room.remainingSeconds <= 0) {
      resolveRankedMatch(io, room);
    }
  }, 1000);
}

function registerMatchmakingSocket(io) {
  io.on('connection', (socket) => {
    const user = socket.data.user;

    // Send current queue count on connect
    socket.emit('ranked:queueStatus', {
      queueSize: rankedQueue.length,
      target: QUEUE_TARGET_SIZE,
    });

    // ── 1. Join Matchmaking Queue ────────────────────────────
    const onJoinQueue = async (payload, ack) => {
      const reply = typeof ack === 'function' ? ack : () => {};
      try {
        if (!user) return reply({ ok: false, error: 'Authentication required' });

        // If already in queue, ignore
        if (rankedQueue.some((q) => q.userId === user.id || q.socketId === socket.id)) {
          return reply({ ok: true, inQueue: true, queueSize: rankedQueue.length });
        }

        const fresh = await User.findById(user.id)
          .select('username equippedSkin equippedFrame rankPoints')
          .lean();

        rankedQueue.push({
          socketId: socket.id,
          userId: user.id,
          username: user.username,
          skin: fresh?.equippedSkin || 'default',
          frame: fresh?.equippedFrame || 'default',
          rankPoints: fresh?.rankPoints || 0,
          isBot: false,
          joinedAt: Date.now(),
        });

        reply({ ok: true, queueSize: rankedQueue.length, target: QUEUE_TARGET_SIZE });
        broadcastQueueStatus(io);

        if (rankedQueue.length >= QUEUE_TARGET_SIZE) {
          createRankedMatch(io);
        }
      } catch (err) {
        console.error('[ranked:joinQueue error]', err);
        return reply({ ok: false, error: 'Could not join queue' });
      }
    };
    socket.on('ranked:joinQueue', onJoinQueue);
    socket.on('joinRankedQueue', onJoinQueue);

    // ── 2. Leave Matchmaking Queue ───────────────────────────
    const onLeaveQueue = (payload, ack) => {
      const reply = typeof ack === 'function' ? ack : () => {};
      const idx = rankedQueue.findIndex((q) => q.socketId === socket.id || (user && q.userId === user.id));
      if (idx !== -1) {
        rankedQueue.splice(idx, 1);
        broadcastQueueStatus(io);
      }
      return reply({ ok: true });
    };
    socket.on('ranked:leaveQueue', onLeaveQueue);
    socket.on('leaveRankedQueue', onLeaveQueue);

    // ── 3. Fill Queue with Bots (Instant Testing) ────────────
    socket.on('ranked:fillQueueBots', async (payload, ack) => {
      const reply = typeof ack === 'function' ? ack : () => {};
      try {
        if (!user) return reply({ ok: false, error: 'Authentication required' });

        // Ensure current player is in queue
        if (!rankedQueue.some((q) => q.socketId === socket.id)) {
          const fresh = await User.findById(user.id)
            .select('username equippedSkin equippedFrame rankPoints')
            .lean();
          rankedQueue.push({
            socketId: socket.id,
            userId: user.id,
            username: user.username,
            skin: fresh?.equippedSkin || 'default',
            frame: fresh?.equippedFrame || 'default',
            rankPoints: fresh?.rankPoints || 0,
            isBot: false,
            joinedAt: Date.now(),
          });
        }

        // Fill remaining slots up to 6 with bots
        let botIndex = 0;
        while (rankedQueue.length < QUEUE_TARGET_SIZE) {
          const template = BOT_TEMPLATES[botIndex % BOT_TEMPLATES.length];
          rankedQueue.push({
            socketId: `bot_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
            userId: null,
            username: `${template.username}_${Math.floor(Math.random() * 90 + 10)}`,
            skin: template.skin,
            frame: template.frame,
            rankPoints: template.rankPoints,
            isBot: true,
            joinedAt: Date.now(),
          });
          botIndex++;
        }

        broadcastQueueStatus(io);
        createRankedMatch(io);
        return reply({ ok: true });
      } catch (err) {
        console.error('[ranked:fillQueueBots error]', err);
        return reply({ ok: false, error: 'Failed to fill queue with bots' });
      }
    });

    // ── 4. Live Score Update ─────────────────────────────────
    const onScoreUpdate = (data) => {
      const roomId = data?.roomId || socketToRankedRoom.get(socket.id);
      if (!roomId) return;
      const room = rankedRooms.get(roomId);
      if (!room || room.state !== 'playing') return;

      const team = data?.team === 'blue' ? 'blue' : 'red';
      const points = Math.max(0, Number(data?.points) || 10);

      if (team === 'red') room.redScore += points;
      else room.blueScore += points;

      io.to(roomId).emit('ranked:scoreSync', {
        redScore: room.redScore,
        blueScore: room.blueScore,
        remainingSeconds: room.remainingSeconds,
      });
    };
    socket.on('ranked:scoreUpdate', onScoreUpdate);
    socket.on('scoreUpdate', onScoreUpdate);

    // ── 5. In-Game Interactive Emojis (1, 2, 3, 4, 5) ────────
    const onEmoji = (data) => {
      const roomId = data?.roomId || socketToRankedRoom.get(socket.id);
      if (!roomId) return;

      const emoji = data?.emoji;
      if (!VALID_EMOJIS.includes(emoji)) return;

      const room = rankedRooms.get(roomId);
      let team = 'spectator';
      let username = user?.username || 'Player';
      if (room) {
        const pRed = room.redTeam.find((p) => p.socketId === socket.id);
        const pBlue = room.blueTeam.find((p) => p.socketId === socket.id);
        if (pRed) {
          team = 'red';
          username = pRed.username;
        } else if (pBlue) {
          team = 'blue';
          username = pBlue.username;
        }
      }

      io.to(roomId).emit('ranked:emojiBroadcast', {
        socketId: socket.id,
        username,
        team,
        emoji,
        x: data?.x ?? 0,
        y: data?.y ?? 0,
      });
    };
    socket.on('ranked:emoji', onEmoji);
    socket.on('room:emoji', onEmoji);

    // ── 6. In-Game Movement & Attack Relays ───────────────────
    socket.on('ranked:playerMove', (data) => {
      const roomId = data?.roomId || socketToRankedRoom.get(socket.id);
      if (!roomId) return;
      socket.to(roomId).emit('ranked:playerMoved', {
        socketId: socket.id,
        team: data?.team || 'red',
        x: data?.x ?? 0,
        y: data?.y ?? 0,
        vx: data?.vx ?? 0,
        vy: data?.vy ?? 0,
        isMoving: Boolean(data?.isMoving),
        angle: data?.angle ?? 0,
        hp: data?.hp ?? 100,
        maxHp: data?.maxHp ?? 100,
      });
    });

    socket.on('ranked:playerAttack', (data) => {
      const roomId = data?.roomId || socketToRankedRoom.get(socket.id);
      if (!roomId) return;
      socket.to(roomId).emit('ranked:playerAttacked', {
        socketId: socket.id,
        team: data?.team || 'red',
        originX: data?.originX ?? 0,
        originY: data?.originY ?? 0,
        targetX: data?.targetX ?? 0,
        targetY: data?.targetY ?? 0,
        damage: data?.damage ?? 30,
        colors: data?.colors || null,
        count: data?.count ?? 1,
      });
    });

    // ── 7. Disconnect Cleanup ─────────────────────────────────
    socket.on('disconnect', () => {
      const qIdx = rankedQueue.findIndex((q) => q.socketId === socket.id);
      if (qIdx !== -1) {
        rankedQueue.splice(qIdx, 1);
        broadcastQueueStatus(io);
      }

      const roomId = socketToRankedRoom.get(socket.id);
      if (roomId) {
        socketToRankedRoom.delete(socket.id);
        const room = rankedRooms.get(roomId);
        if (room && room.state === 'playing') {
          io.to(roomId).emit('ranked:playerLeft', {
            socketId: socket.id,
            username: user?.username || 'Player',
          });
        }
      }
    });
  });
}

module.exports = {
  registerMatchmakingSocket,
  rankedQueue,
  rankedRooms,
  socketToRankedRoom,
  VALID_EMOJIS,
};


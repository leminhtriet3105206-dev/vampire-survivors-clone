'use strict';

const User = require('../models/User');

const MAX_PLAYERS_PER_ROOM = 4;
const CODE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // Avoid ambiguous chars (O/0, I/1)
const QUEST_KILL_TARGET = 100;
const VICTORY_DIAMOND_REWARD = 15;

const rooms = new Map(); // roomCode -> Room
const socketToRoom = new Map(); // socketId -> roomCode

function generateRoomCode() {
  for (let attempt = 0; attempt < 50; attempt++) {
    let code = '';
    for (let i = 0; i < 5; i++) {
      code += CODE_CHARS.charAt(Math.floor(Math.random() * CODE_CHARS.length));
    }
    if (!rooms.has(code)) return code;
  }
  return `R${Date.now().toString().slice(-4)}`;
}

function getRoomPublicData(room) {
  return {
    code: room.code,
    state: room.state, // 'lobby' | 'playing' | 'victory'
    hostSocketId: room.hostSocketId,
    hostUserId: room.hostUserId,
    playerCount: room.players.size,
    maxPlayers: MAX_PLAYERS_PER_ROOM,
    players: Array.from(room.players.values()).map((p) => ({
      socketId: p.socketId,
      userId: p.userId,
      username: p.username,
      skin: p.skin,
      ready: p.ready,
      isHost: p.isHost,
    })),
    quest: {
      killsTarget: room.quest.killsTarget,
      currentKills: room.quest.currentKills,
      bossSpawned: room.quest.bossSpawned,
      bossDefeated: room.quest.bossDefeated,
    },
  };
}

async function removePlayerFromRoom(io, socket, reason = 'left') {
  const roomCode = socketToRoom.get(socket.id);
  if (!roomCode) return;

  socketToRoom.delete(socket.id);
  socket.leave(roomCode);

  const room = rooms.get(roomCode);
  if (!room) return;

  room.players.delete(socket.id);

  if (room.players.size === 0) {
    rooms.delete(roomCode);
    return;
  }

  // If the host left, migrate host to the next available player
  if (room.hostSocketId === socket.id) {
    const nextHost = room.players.values().next().value;
    if (nextHost) {
      room.hostSocketId = nextHost.socketId;
      room.hostUserId = nextHost.userId;
      nextHost.isHost = true;
      nextHost.ready = true;
    }
  }

  io.to(roomCode).emit('room:playerLeft', {
    socketId: socket.id,
    username: socket.data.user?.username || 'Player',
    reason,
    room: getRoomPublicData(room),
  });
  io.to(roomCode).emit('room:update', getRoomPublicData(room));
}

function registerRoomSocket(io) {
  io.on('connection', (socket) => {
    const user = socket.data.user;

    // ── 1. Create Room ───────────────────────────────────────
    socket.on('room:create', async (payload, ack) => {
      const reply = typeof ack === 'function' ? ack : () => {};
      try {
        if (!user) return reply({ ok: false, error: 'Authentication required' });

        // Clean up from any existing room
        await removePlayerFromRoom(io, socket, 'switch');

        const fresh = await User.findById(user.id).select('username equippedSkin').lean();
        const equippedSkin = fresh?.equippedSkin || 'default';

        const code = generateRoomCode();
        const room = {
          code,
          hostSocketId: socket.id,
          hostUserId: user.id,
          state: 'lobby',
          players: new Map(),
          quest: {
            killsTarget: QUEST_KILL_TARGET,
            currentKills: 0,
            bossSpawned: false,
            bossDefeated: false,
          },
          rewardGranted: false,
          createdAt: Date.now(),
        };

        const playerInfo = {
          socketId: socket.id,
          userId: user.id,
          username: user.username,
          skin: equippedSkin,
          ready: true,
          isHost: true,
        };

        room.players.set(socket.id, playerInfo);
        rooms.set(code, room);
        socketToRoom.set(socket.id, code);
        socket.join(code);

        return reply({ ok: true, room: getRoomPublicData(room) });
      } catch (err) {
        console.error('[room:create error]', err);
        return reply({ ok: false, error: 'Could not create room' });
      }
    });

    // ── 2. Join Room ─────────────────────────────────────────
    socket.on('room:join', async (payload, ack) => {
      const reply = typeof ack === 'function' ? ack : () => {};
      try {
        if (!user) return reply({ ok: false, error: 'Authentication required' });

        const rawCode = payload?.code;
        if (typeof rawCode !== 'string' || !rawCode.trim()) {
          return reply({ ok: false, error: 'Room code is required' });
        }
        const code = rawCode.trim().toUpperCase();

        const room = rooms.get(code);
        if (!room) return reply({ ok: false, error: 'Room not found' });
        if (room.state !== 'lobby') return reply({ ok: false, error: 'Dungeon match already in progress' });
        if (room.players.size >= MAX_PLAYERS_PER_ROOM) return reply({ ok: false, error: 'Room is full (max 4)' });

        await removePlayerFromRoom(io, socket, 'switch');

        const fresh = await User.findById(user.id).select('username equippedSkin').lean();
        const equippedSkin = fresh?.equippedSkin || 'default';

        const playerInfo = {
          socketId: socket.id,
          userId: user.id,
          username: user.username,
          skin: equippedSkin,
          ready: false,
          isHost: false,
        };

        room.players.set(socket.id, playerInfo);
        socketToRoom.set(socket.id, code);
        socket.join(code);

        const data = getRoomPublicData(room);
        io.to(code).emit('room:update', data);
        return reply({ ok: true, room: data });
      } catch (err) {
        console.error('[room:join error]', err);
        return reply({ ok: false, error: 'Could not join room' });
      }
    });

    // ── 3. Toggle Ready ──────────────────────────────────────
    socket.on('room:ready', (payload, ack) => {
      const reply = typeof ack === 'function' ? ack : () => {};
      const roomCode = socketToRoom.get(socket.id);
      if (!roomCode) return reply({ ok: false, error: 'Not in a room' });

      const room = rooms.get(roomCode);
      if (!room || room.state !== 'lobby') return reply({ ok: false, error: 'Invalid room state' });

      const p = room.players.get(socket.id);
      if (!p) return reply({ ok: false, error: 'Player not found in room' });

      p.ready = Boolean(payload?.ready);
      const data = getRoomPublicData(room);
      io.to(roomCode).emit('room:update', data);
      return reply({ ok: true, ready: p.ready });
    });

    // ── 4. Leave Room ────────────────────────────────────────
    socket.on('room:leave', async (payload, ack) => {
      const reply = typeof ack === 'function' ? ack : () => {};
      await removePlayerFromRoom(io, socket, 'user_left');
      return reply({ ok: true });
    });

    // ── 5. Start Dungeon (Host Only) ─────────────────────────
    socket.on('room:start', (payload, ack) => {
      const reply = typeof ack === 'function' ? ack : () => {};
      const roomCode = socketToRoom.get(socket.id);
      if (!roomCode) return reply({ ok: false, error: 'Not in a room' });

      const room = rooms.get(roomCode);
      if (!room) return reply({ ok: false, error: 'Room does not exist' });
      if (room.hostSocketId !== socket.id) return reply({ ok: false, error: 'Only the host can start the dungeon' });

      // Check all non-hosts are ready
      for (const p of room.players.values()) {
        if (!p.isHost && !p.ready) {
          return reply({ ok: false, error: `Waiting for ${p.username} to be Ready!` });
        }
      }

      room.state = 'playing';
      room.quest.currentKills = 0;
      room.quest.bossSpawned = false;
      room.quest.bossDefeated = false;
      room.rewardGranted = false;

      const data = getRoomPublicData(room);
      io.to(roomCode).emit('room:started', data);
      return reply({ ok: true });
    });

    // ── 6. In-Game Sync: Position Updates (~20Hz) ────────────
    socket.on('room:playerMove', (data) => {
      const roomCode = socketToRoom.get(socket.id);
      if (!roomCode) return;
      socket.to(roomCode).emit('room:playerMoved', {
        socketId: socket.id,
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

    // ── 7. In-Game Sync: Attack Projectiles Visuals ──────────
    socket.on('room:playerAttack', (data) => {
      const roomCode = socketToRoom.get(socket.id);
      if (!roomCode) return;
      socket.to(roomCode).emit('room:playerAttacked', {
        socketId: socket.id,
        originX: data?.originX ?? 0,
        originY: data?.originY ?? 0,
        targetX: data?.targetX ?? 0,
        targetY: data?.targetY ?? 0,
        damage: data?.damage ?? 30,
        colors: data?.colors || null,
        count: data?.count ?? 1,
      });
    });

    // ── 8. Host-Authoritative Enemies & Boss Broadcast ───────
    socket.on('room:enemiesUpdate', (data) => {
      const roomCode = socketToRoom.get(socket.id);
      if (!roomCode) return;
      const room = rooms.get(roomCode);
      if (!room || room.hostSocketId !== socket.id) return;

      if (data?.questKills !== undefined) {
        room.quest.currentKills = data.questKills;
      }
      if (data?.boss) {
        room.quest.bossSpawned = true;
      }

      socket.to(roomCode).emit('room:enemiesSync', {
        enemies: data?.enemies || [],
        questKills: room.quest.currentKills,
        boss: data?.boss || null,
      });
    });

    // ── 9. Non-Host Enemy Hit Forwarded to Host ──────────────
    socket.on('room:enemyHit', (data) => {
      const roomCode = socketToRoom.get(socket.id);
      if (!roomCode) return;
      const room = rooms.get(roomCode);
      if (!room) return;

      // Send to room host
      io.to(room.hostSocketId).emit('room:hostEnemyHit', {
        enemyId: data?.enemyId,
        damage: data?.damage ?? 10,
        isCrit: Boolean(data?.isCrit),
        fromSocketId: socket.id,
      });
    });

    // ── 10. Boss Defeated & Diamond Reward ───────────────────
    socket.on('room:bossDefeated', async (payload, ack) => {
      const reply = typeof ack === 'function' ? ack : () => {};
      const roomCode = socketToRoom.get(socket.id);
      if (!roomCode) return reply({ ok: false, error: 'Not in a room' });

      const room = rooms.get(roomCode);
      if (!room || room.hostSocketId !== socket.id) {
        return reply({ ok: false, error: 'Unauthorized or invalid room' });
      }

      if (room.rewardGranted) {
        return reply({ ok: true, alreadyRewarded: true });
      }

      room.rewardGranted = true;
      room.state = 'victory';
      room.quest.bossDefeated = true;

      // Securely grant +15 Diamonds to every participant in MongoDB
      const rewardResults = [];
      const userIds = Array.from(room.players.values()).map((p) => p.userId);

      try {
        await User.updateMany(
          { _id: { $in: userIds } },
          { $inc: { 'currencies.diamonds': VICTORY_DIAMOND_REWARD } }
        );

        for (const p of room.players.values()) {
          const fresh = await User.findById(p.userId).select('currencies').lean();
          rewardResults.push({
            userId: p.userId,
            username: p.username,
            diamonds: fresh?.currencies?.diamonds ?? 0,
          });
        }
      } catch (dbErr) {
        console.error('[room:bossDefeated DB error]', dbErr);
      }

      // Broadcast Victory to the entire room
      io.to(roomCode).emit('room:victory', {
        reward: { diamonds: VICTORY_DIAMOND_REWARD },
        players: rewardResults,
        message: `VICTORY! All survivors earned +${VICTORY_DIAMOND_REWARD} Diamonds!`,
      });

      return reply({ ok: true });
    });

    // ── 11. Disconnect Cleanup ───────────────────────────────
    socket.on('disconnect', async () => {
      await removePlayerFromRoom(io, socket, 'disconnected');
    });
  });
}

module.exports = { registerRoomSocket, rooms, socketToRoom };


'use strict';

const User = require('../models/User');
const { getRankTier } = require('../models/User');
const ChatMessage = require('../models/ChatMessage');
const config = require('../config/env');
const { verifyToken } = require('../utils/jwt');
const { getRecentMessages } = require('../controllers/chatController');

const WORLD_ROOM = 'world';

// Strip ASCII control characters (keeps normal unicode / emoji / Vietnamese).
// eslint-disable-next-line no-control-regex
const CONTROL_CHARS = /[\u0000-\u0008\u000B-\u001F\u007F]/g;

function sanitizeText(raw) {
  if (typeof raw !== 'string') return '';
  return raw.replace(CONTROL_CHARS, '').replace(/\s+/g, ' ').trim();
}

/** Counts unique logged-in users (a user may have several tabs open). */
async function broadcastOnline(io) {
  const sockets = await io.in(WORLD_ROOM).fetchSockets();
  const unique = new Set(sockets.map((s) => s.data.user?.id).filter(Boolean));
  io.to(WORLD_ROOM).emit('chat:online', { count: unique.size });
}

/** Socket.io handshake authentication: client passes { auth: { token } }. */
async function authenticateSocket(socket, next) {
  try {
    const token = socket.handshake.auth?.token;
    if (!token || typeof token !== 'string') return next(new Error('AUTH_REQUIRED'));
    const payload = verifyToken(token);
    const user = await User.findById(payload.sub).select('username equippedSkin role').lean();
    if (!user) return next(new Error('AUTH_INVALID'));
    socket.data.user = { id: user._id.toString(), username: user.username, role: user.role || 'player' };
    socket.data.lastMessageAt = 0;
    return next();
  } catch (err) {
    return next(new Error(err.name === 'TokenExpiredError' ? 'AUTH_EXPIRED' : 'AUTH_INVALID'));
  }
}

/** Handles GM commands executed by admins in World Chat (e.g. /give Player1 gold 5000). */
async function handleAdminCommand(io, socket, adminUser, rawCommand, reply) {
  const trimmed = rawCommand.trim();
  const parts = trimmed.split(/\s+/);
  const cmd = parts[0].toLowerCase();

  if (cmd === '/give') {
    if (parts.length < 4) {
      const errText = '⚠️ [GM System] Invalid syntax. Usage: /give <username> <gold|diamonds|rubies> <amount>';
      socket.emit('chat:systemMessage', { text: errText });
      return reply({ ok: false, error: errText });
    }

    const targetUsername = parts[1];
    let currency = parts[2].toLowerCase();
    if (currency === 'diamond') currency = 'diamonds';
    if (currency === 'ruby') currency = 'rubies';

    if (!['gold', 'diamonds', 'rubies'].includes(currency)) {
      const errText = `⚠️ [GM System] Unknown currency "${parts[2]}". Must be gold, diamonds, or rubies.`;
      socket.emit('chat:systemMessage', { text: errText });
      return reply({ ok: false, error: errText });
    }

    const amount = Number.parseInt(parts[3], 10);
    if (!Number.isFinite(amount) || amount === 0) {
      const errText = '⚠️ [GM System] Amount must be a non-zero integer.';
      socket.emit('chat:systemMessage', { text: errText });
      return reply({ ok: false, error: errText });
    }

    const targetDoc = await User.findOne({ usernameLower: targetUsername.toLowerCase() });
    if (!targetDoc) {
      const errText = `⚠️ [GM System] Player "${targetUsername}" not found.`;
      socket.emit('chat:systemMessage', { text: errText });
      return reply({ ok: false, error: errText });
    }

    if (!targetDoc.currencies) {
      targetDoc.currencies = { gold: 0, diamonds: 0, rubies: 0 };
    }
    const currentVal = targetDoc.currencies[currency] || 0;
    const nextVal = Math.max(0, currentVal + amount);
    targetDoc.currencies[currency] = nextVal;
    await targetDoc.save();

    // 1. Private confirmation message to the Admin
    const adminMsg = `👑 [GM Command Executed] Granted ${amount >= 0 ? '+' : ''}${amount} ${currency} to ${targetDoc.username}. New balance: ${nextVal}.`;
    socket.emit('chat:systemMessage', { text: adminMsg });

    // 2. Real-time notification to the target user if connected
    const targetNotice = `🎉 [Game Master] You were granted ${amount >= 0 ? '+' : ''}${amount} ${currency} by GM ${adminUser.username}! New balance: ${nextVal}.`;
    io.to(`username:${targetDoc.username.toLowerCase()}`).emit('admin:currencyReceived', {
      currency,
      amount,
      newBalance: nextVal,
      message: targetNotice,
      user: targetDoc.toPublicJSON(),
    });

    return reply({
      ok: true,
      command: 'give',
      target: targetDoc.username,
      currency,
      amount,
      newBalance: nextVal,
    });
  }

  const unknownMsg = `⚠️ [GM System] Unknown command "${cmd}". Available commands: /give <username> <currency> <amount>`;
  socket.emit('chat:systemMessage', { text: unknownMsg });
  return reply({ ok: false, error: unknownMsg });
}

function registerChatSocket(io) {
  io.use(authenticateSocket);

  io.on('connection', async (socket) => {
    const { user } = socket.data;
    socket.join(WORLD_ROOM);
    if (user?.username) {
      socket.join(`username:${user.username.toLowerCase()}`);
    }

    try {
      socket.emit('chat:history', await getRecentMessages());
    } catch (err) {
      console.error('[socket] history error:', err.message);
      socket.emit('chat:error', { message: 'Could not load chat history' });
    }
    broadcastOnline(io).catch(() => {});

    socket.on('chat:send', async (payload, ack) => {
      const reply = typeof ack === 'function' ? ack : () => {};
      try {
        const text = sanitizeText(payload?.text);
        if (!text) return reply({ ok: false, error: 'Message cannot be empty' });
        if (text.length > config.chat.maxLength) {
          return reply({ ok: false, error: `Message too long (max ${config.chat.maxLength} characters)` });
        }

        // Intercept GM commands (must start with '/')
        if (text.startsWith('/')) {
          const freshUser = await User.findById(user.id);
          if (freshUser && freshUser.role === 'admin') {
            return handleAdminCommand(io, socket, freshUser, text, reply);
          }
          return reply({ ok: false, error: 'Only Game Masters can execute chat commands' });
        }

        const now = Date.now();
        if (now - socket.data.lastMessageAt < config.chat.minIntervalMs) {
          return reply({ ok: false, error: 'You are sending messages too fast' });
        }
        socket.data.lastMessageAt = now;

        // Read the equipped skin, frame and rank fresh so chat shows the latest profile.
        const fresh = await User.findById(user.id).select('equippedSkin equippedFrame rankPoints').lean();
        if (!fresh) return reply({ ok: false, error: 'Account no longer exists' });

        const msg = await ChatMessage.create({
          user: user.id,
          username: user.username,
          skin: fresh.equippedSkin || 'default',
          frame: fresh.equippedFrame || 'default',
          rankTier: getRankTier(fresh.rankPoints || 0),
          text,
          channel: WORLD_ROOM,
        });

        io.to(WORLD_ROOM).emit('chat:message', msg.toPublicJSON());
        return reply({ ok: true });
      } catch (err) {
        console.error('[socket] chat:send error:', err.message);
        return reply({ ok: false, error: 'Message could not be sent' });
      }
    });

    socket.on('disconnect', () => {
      broadcastOnline(io).catch(() => {});
    });
  });
}

module.exports = { registerChatSocket, sanitizeText };


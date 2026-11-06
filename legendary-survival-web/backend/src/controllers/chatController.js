'use strict';

const ChatMessage = require('../models/ChatMessage');
const config = require('../config/env');
const asyncHandler = require('../utils/asyncHandler');

/** Shared helper used by both the REST endpoint and the socket handler. */
async function getRecentMessages(limit = config.chat.historySize, channel = 'world') {
  const docs = await ChatMessage.find({ channel }).sort({ createdAt: -1 }).limit(limit);
  return docs.reverse().map((m) => m.toPublicJSON());
}

/** GET /api/chat/messages?limit=50 */
exports.listMessages = asyncHandler(async (req, res) => {
  const requested = Number.parseInt(req.query.limit, 10);
  const limit = Number.isFinite(requested)
    ? Math.min(Math.max(requested, 1), 100)
    : config.chat.historySize;
  res.json({ success: true, messages: await getRecentMessages(limit) });
});

exports.getRecentMessages = getRecentMessages;


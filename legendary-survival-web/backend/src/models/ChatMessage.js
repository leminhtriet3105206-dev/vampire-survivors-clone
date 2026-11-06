'use strict';

const mongoose = require('mongoose');

const MESSAGE_TTL_SECONDS = 60 * 60 * 24 * 7; // keep world chat for 7 days

const chatMessageSchema = new mongoose.Schema({
  user: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  username: { type: String, required: true },
  skin: { type: String, default: 'default' },
  rankTier: { type: String, default: 'Bronze' },
  frame: { type: String, default: 'default' },
  text: { type: String, required: true, trim: true, minlength: 1, maxlength: 300 },
  channel: { type: String, default: 'world', index: true },
  createdAt: { type: Date, default: Date.now, expires: MESSAGE_TTL_SECONDS },
});

chatMessageSchema.index({ channel: 1, createdAt: -1 });

chatMessageSchema.methods.toPublicJSON = function toPublicJSON() {
  return {
    id: this._id.toString(),
    userId: this.user.toString(),
    username: this.username,
    skin: this.skin,
    rankTier: this.rankTier || 'Bronze',
    frame: this.frame || 'default',
    text: this.text,
    createdAt: this.createdAt,
  };
};

module.exports = mongoose.model('ChatMessage', chatMessageSchema);


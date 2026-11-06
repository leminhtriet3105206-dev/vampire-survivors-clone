'use strict';

const mongoose = require('mongoose');
const bcrypt = require('bcryptjs');
const config = require('../config/env');

const CURRENCIES = ['gold', 'diamonds', 'rubies'];
const USERNAME_REGEX = /^[a-zA-Z0-9_]{3,20}$/;
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

const currencySchema = new mongoose.Schema(
  {
    gold: { type: Number, default: 0, min: 0 },
    diamonds: { type: Number, default: 0, min: 0 },
    rubies: { type: Number, default: 0, min: 0 },
  },
  { _id: false }
);

const matchRecordSchema = new mongoose.Schema(
  {
    mode: { type: String, enum: ['solo', 'coop', 'ranked'], required: true },
    result: { type: String, enum: ['win', 'loss', 'draw'], default: 'loss' },
    score: { type: Number, default: 0 },
    kills: { type: Number, default: 0 },
    survivalTime: { type: Number, default: 0 }, // in seconds
    skin: { type: String, default: 'default' },
    rewardText: { type: String, default: '' },
    date: { type: Date, default: Date.now },
  },
  { _id: true }
);

const cloudSaveSchema = new mongoose.Schema(
  {
    highScore: { type: Number, default: 0, min: 0 },
    unlockedChars: { type: [String], default: ['warrior', 'mage'] },
    permLevels: {
      type: Map,
      of: Number,
      default: () => ({
        health: 0,
        damage: 0,
        speed: 0,
        magnet: 0,
        greed: 0,
        cooldown: 0,
        armor: 0,
        curse: 0,
        revival: 0,
        growth: 0,
      }),
    },
    achievements: { type: [String], default: [] },
    campaignProgress: { type: Number, default: 1, min: 1 },
    version: { type: Number, default: 1, min: 1 },
    lastSyncedAt: { type: Date, default: Date.now },
  },
  { _id: false }
);

const userSchema = new mongoose.Schema(
  {
    username: {
      type: String,
      required: [true, 'Username is required'],
      trim: true,
      match: [USERNAME_REGEX, 'Username must be 3-20 characters (letters, numbers, underscore)'],
    },
    // Lower-cased copy used for case-insensitive uniqueness and lookup.
    usernameLower: { type: String, required: true, unique: true, index: true },
    email: {
      type: String,
      required: [true, 'Email is required'],
      unique: true,
      trim: true,
      lowercase: true,
      maxlength: 254,
      match: [EMAIL_REGEX, 'Email address is invalid'],
    },
    password: {
      type: String,
      required: [true, 'Password is required'],
      minlength: 8,
      select: false, // never returned unless explicitly requested
    },
    currencies: { type: currencySchema, default: () => ({}) },
    ownedSkins: { type: [String], default: ['default'] },
    equippedSkin: { type: String, default: 'default' },
    ownedFrames: { type: [String], default: ['default'] },
    equippedFrame: { type: String, default: 'default' },
    role: {
      type: String,
      enum: ['player', 'admin'],
      default: 'player',
      index: true,
    },
    adminBuffs: {
      bonusHp: { type: Number, default: 0, min: 0 },
      bonusDamage: { type: Number, default: 0, min: 0 },
    },
    rankPoints: { type: Number, default: 0, min: 0 },
    lastDailyClaim: { type: Date, default: null },
    lastLoginAt: { type: Date, default: null },

    // Player aggregate stats & match history
    totalPlaytime: { type: Number, default: 0, min: 0 }, // in seconds
    totalKills: { type: Number, default: 0, min: 0 },
    totalWins: { type: Number, default: 0, min: 0 },
    totalMatches: { type: Number, default: 0, min: 0 },
    totalBossesDefeated: { type: Number, default: 0, min: 0 },
    matchHistory: { type: [matchRecordSchema], default: [] },
    cloudSave: { type: cloudSaveSchema, default: () => ({}) },
  },
  { timestamps: true }
);

function getRankTier(rp = 0) {
  if (rp >= 600) return 'Diamond';
  if (rp >= 300) return 'Gold';
  if (rp >= 100) return 'Silver';
  return 'Bronze';
}

userSchema.pre('validate', function setUsernameLower(next) {
  if (this.username) this.usernameLower = this.username.toLowerCase();
  next();
});

userSchema.pre('save', async function hashPassword(next) {
  if (!this.isModified('password')) return next();
  try {
    this.password = await bcrypt.hash(this.password, config.bcryptRounds);
    return next();
  } catch (err) {
    return next(err);
  }
});

userSchema.methods.comparePassword = function comparePassword(candidate) {
  return bcrypt.compare(candidate, this.password);
};

userSchema.methods.toPublicJSON = function toPublicJSON() {
  const rp = this.rankPoints ?? 0;
  return {
    id: this._id.toString(),
    username: this.username,
    email: this.email,
    currencies: {
      gold: this.currencies?.gold ?? 0,
      diamonds: this.currencies?.diamonds ?? 0,
      rubies: this.currencies?.rubies ?? 0,
    },
    ownedSkins: this.ownedSkins,
    equippedSkin: this.equippedSkin,
    ownedFrames: this.ownedFrames || ['default'],
    equippedFrame: this.equippedFrame || 'default',
    role: this.role || 'player',
    adminBuffs: {
      bonusHp: this.adminBuffs?.bonusHp ?? 0,
      bonusDamage: this.adminBuffs?.bonusDamage ?? 0,
    },
    rankPoints: rp,
    rankTier: getRankTier(rp),
    stats: {
      totalPlaytime: this.totalPlaytime ?? 0,
      totalKills: this.totalKills ?? 0,
      totalWins: this.totalWins ?? 0,
      totalMatches: this.totalMatches ?? 0,
      totalBossesDefeated: this.totalBossesDefeated ?? 0,
      winRate: (this.totalMatches > 0)
        ? Math.round(((this.totalWins ?? 0) / this.totalMatches) * 100)
        : 0,
    },
    lastDailyClaim: this.lastDailyClaim,
    cloudSave: this.cloudSave ? {
      highScore: this.cloudSave.highScore || 0,
      unlockedChars: this.cloudSave.unlockedChars || ['warrior', 'mage'],
      permLevels: (this.cloudSave.permLevels instanceof Map)
        ? Object.fromEntries(this.cloudSave.permLevels)
        : (this.cloudSave.permLevels || {}),
      achievements: this.cloudSave.achievements || [],
      campaignProgress: this.cloudSave.campaignProgress || 1,
      version: this.cloudSave.version || 1,
      lastSyncedAt: this.cloudSave.lastSyncedAt || this.updatedAt,
    } : null,
    createdAt: this.createdAt,
  };
};

const User = mongoose.model('User', userSchema);

module.exports = User;
module.exports.CURRENCIES = CURRENCIES;
module.exports.USERNAME_REGEX = USERNAME_REGEX;
module.exports.EMAIL_REGEX = EMAIL_REGEX;
module.exports.getRankTier = getRankTier;


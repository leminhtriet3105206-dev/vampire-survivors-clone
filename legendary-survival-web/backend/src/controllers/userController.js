'use strict';

const User = require('../models/User');
const Skin = require('../models/Skin');
const AppError = require('../utils/AppError');
const asyncHandler = require('../utils/asyncHandler');

const DAILY_COOLDOWN_MS = 24 * 60 * 60 * 1000;
const DAILY_REWARD = { gold: 500, diamonds: 10, rubies: 2 };

/** PATCH /api/users/me/equipped-skin   body: { slug } */
exports.equipSkin = asyncHandler(async (req, res) => {
  const { slug } = req.body;
  if (!req.user.ownedSkins.includes(slug)) throw new AppError('You do not own this skin', 403);

  const exists = await Skin.exists({ slug, isActive: true });
  if (!exists) throw new AppError('Skin not found', 404);

  req.user.equippedSkin = slug;
  await req.user.save();
  res.json({ success: true, message: 'Skin equipped', user: req.user.toPublicJSON() });
});

/** PATCH /api/users/me/equipped-frame   body: { slug } */
exports.equipFrame = asyncHandler(async (req, res) => {
  const { slug } = req.body;
  if (slug !== 'default') {
    const owned = req.user.ownedFrames || ['default'];
    if (!owned.includes(slug)) throw new AppError('You do not own this avatar frame', 403);
    const exists = await Skin.exists({ slug, isActive: true, itemType: 'frame' });
    if (!exists) throw new AppError('Avatar frame not found', 404);
  }

  req.user.equippedFrame = slug;
  await req.user.save();
  res.json({ success: true, message: 'Avatar frame equipped', user: req.user.toPublicJSON() });
});

/**
 * POST /api/users/me/daily-reward
 * Grants a currency bundle once every 24h (atomic, race-safe).
 */
exports.claimDailyReward = asyncHandler(async (req, res) => {
  const now = new Date();
  const threshold = new Date(now.getTime() - DAILY_COOLDOWN_MS);

  const updated = await User.findOneAndUpdate(
    {
      _id: req.user._id,
      $or: [{ lastDailyClaim: null }, { lastDailyClaim: { $lte: threshold } }],
    },
    {
      $inc: {
        'currencies.gold': DAILY_REWARD.gold,
        'currencies.diamonds': DAILY_REWARD.diamonds,
        'currencies.rubies': DAILY_REWARD.rubies,
      },
      $set: { lastDailyClaim: now },
    },
    { new: true }
  );

  if (!updated) {
    const last = req.user.lastDailyClaim ? req.user.lastDailyClaim.getTime() : 0;
    const nextAt = new Date(last + DAILY_COOLDOWN_MS);
    throw new AppError('Daily reward already claimed', 429, { nextClaimAt: nextAt.toISOString() });
  }

  res.json({
    success: true,
    message: `Daily reward: +${DAILY_REWARD.gold} Gold, +${DAILY_REWARD.diamonds} Diamonds, +${DAILY_REWARD.rubies} Rubies`,
    reward: DAILY_REWARD,
    user: updated.toPublicJSON(),
  });
});

/**
 * POST /api/users/me/add-gold
 * Adds gold earned from a survival run to the player's account.
 */
exports.addGold = asyncHandler(async (req, res) => {
  const rawGold = req.body.gold;
  const amount = Number.parseInt(rawGold, 10);
  if (!Number.isFinite(amount) || amount <= 0) {
    throw new AppError('Invalid gold amount', 400);
  }

  // Safety cap per single match
  const safeAmount = Math.min(amount, 50000);

  const updated = await User.findByIdAndUpdate(
    req.user._id,
    { $inc: { 'currencies.gold': safeAmount } },
    { new: true, runValidators: true }
  );

  if (!updated) throw new AppError('Account no longer exists', 401);

  res.json({
    success: true,
    message: `+${safeAmount} Gold collected from battle!`,
    addedGold: safeAmount,
    user: updated.toPublicJSON(),
  });
});

/**
 * POST /api/users/me/add-diamonds
 * Adds diamonds earned from boss victory / co-op dungeons.
 */
exports.addDiamonds = asyncHandler(async (req, res) => {
  const rawDiamonds = req.body.diamonds;
  const amount = Number.parseInt(rawDiamonds, 10);
  if (!Number.isFinite(amount) || amount <= 0) {
    throw new AppError('Invalid diamonds amount', 400);
  }

  // Safety cap per reward event
  const safeAmount = Math.min(amount, 1000);

  const updated = await User.findByIdAndUpdate(
    req.user._id,
    { $inc: { 'currencies.diamonds': safeAmount } },
    { new: true, runValidators: true }
  );

  if (!updated) throw new AppError('Account no longer exists', 401);

  res.json({
    success: true,
    message: `+${safeAmount} Diamonds earned!`,
    addedDiamonds: safeAmount,
    user: updated.toPublicJSON(),
  });
});

/**
 * GET /api/users/me/history
 * Retrieves the user's match history and aggregate combat stats.
 */
exports.getMatchHistory = asyncHandler(async (req, res) => {
  const user = await User.findById(req.user._id).lean();
  if (!user) throw new AppError('User not found', 404);

  const history = (user.matchHistory || []).slice(-30).reverse();
  const totalMatches = user.totalMatches || 0;
  const totalWins = user.totalWins || 0;
  const winRate = totalMatches > 0 ? Math.round((totalWins / totalMatches) * 100) : 0;

  res.json({
    success: true,
    history,
    stats: {
      totalPlaytime: user.totalPlaytime || 0,
      totalKills: user.totalKills || 0,
      totalWins,
      totalMatches,
      totalBossesDefeated: user.totalBossesDefeated || 0,
      winRate,
    },
  });
});

/**
 * POST /api/users/me/record-match
 * Records a completed combat session into match history and updates player statistics.
 */
exports.recordMatch = asyncHandler(async (req, res) => {
  const {
    mode = 'solo',
    result = 'loss',
    score = 0,
    kills = 0,
    survivalTime = 0,
    skin = 'default',
    bossDefeated = false,
    rewardText = '',
  } = req.body;

  const validModes = ['solo', 'coop', 'ranked'];
  const validResults = ['win', 'loss', 'draw'];

  const safeMode = validModes.includes(mode) ? mode : 'solo';
  const safeResult = validResults.includes(result) ? result : 'loss';
  const safeScore = Math.max(0, Number(score) || 0);
  const safeKills = Math.max(0, Number(kills) || 0);
  const safeSurvival = Math.max(0, Number(survivalTime) || 0);
  const isWin = safeResult === 'win';

  const newMatch = {
    mode: safeMode,
    result: safeResult,
    score: safeScore,
    kills: safeKills,
    survivalTime: safeSurvival,
    skin: String(skin || 'default'),
    rewardText: String(rewardText || ''),
    date: new Date(),
  };

  const incFields = {
    totalPlaytime: safeSurvival,
    totalKills: safeKills,
    totalMatches: 1,
  };
  if (isWin) incFields.totalWins = 1;
  if (bossDefeated) incFields.totalBossesDefeated = 1;

  const updated = await User.findByIdAndUpdate(
    req.user._id,
    {
      $inc: incFields,
      $push: {
        matchHistory: {
          $each: [newMatch],
          $position: 0,
          $slice: 50, // Keep last 50 matches
        },
      },
    },
    { new: true, runValidators: true }
  );

  if (!updated) throw new AppError('User not found', 404);

  res.json({
    success: true,
    message: 'Match recorded successfully',
    match: newMatch,
    user: updated.toPublicJSON(),
  });
});

/**
 * GET /api/users/leaderboard
 * Fetches the top survivors ranked by Rank Points, Rubies, Gold, or Kills.
 */
exports.getLeaderboard = asyncHandler(async (req, res) => {
  const { sortBy = 'rp', limit = 25, mode = 'all' } = req.query || {};

  const safeLimit = Math.max(1, Math.min(Number(limit) || 25, 100));

  let sortCriteria = { rankPoints: -1, 'currencies.rubies': -1, totalKills: -1 };
  if (sortBy === 'kills') {
    sortCriteria = { totalKills: -1, rankPoints: -1 };
  } else if (sortBy === 'gold') {
    sortCriteria = { 'currencies.gold': -1, rankPoints: -1 };
  } else if (sortBy === 'score') {
    sortCriteria = { 'cloudSave.highScore': -1, rankPoints: -1 };
  }

  const query = {};
  if (mode !== 'all') {
    query['matchHistory.mode'] = mode;
  }

  const topUsers = await User.find(query)
    .sort(sortCriteria)
    .limit(safeLimit)
    .lean();

  const leaderboard = topUsers.map((u, idx) => ({
    rankPosition: idx + 1,
    id: u._id.toString(),
    username: u.username,
    role: u.role || 'player',
    rankPoints: u.rankPoints || 0,
    rankTier: User.getRankTier(u.rankPoints || 0),
    highScore: u.cloudSave?.highScore || 0,
    currencies: {
      gold: u.currencies?.gold || 0,
      diamonds: u.currencies?.diamonds || 0,
      rubies: u.currencies?.rubies || 0,
    },
    equippedSkin: u.equippedSkin || 'default',
    equippedFrame: u.equippedFrame || 'default',
    totalKills: u.totalKills || 0,
    totalWins: u.totalWins || 0,
    totalMatches: u.totalMatches || 0,
  }));

  res.json({
    success: true,
    filter: { sortBy, limit: safeLimit, mode },
    leaderboard,
  });
});

/**
 * GET /api/users/me/save
 * Retrieves the player's cloud save state and currency balances.
 */
exports.getCloudSave = asyncHandler(async (req, res) => {
  const user = await User.findById(req.user._id).lean();
  if (!user) throw new AppError('User not found', 404);

  const save = user.cloudSave || {};
  const permLevels = (save.permLevels instanceof Map)
    ? Object.fromEntries(save.permLevels)
    : (save.permLevels || {});

  res.json({
    success: true,
    cloudSave: {
      highScore: save.highScore || 0,
      unlockedChars: save.unlockedChars || ['warrior', 'mage'],
      permLevels,
      achievements: save.achievements || [],
      campaignProgress: save.campaignProgress || 1,
      version: save.version || 1,
      lastSyncedAt: save.lastSyncedAt || user.updatedAt,
    },
    currencies: {
      gold: user.currencies?.gold || 0,
      diamonds: user.currencies?.diamonds || 0,
      rubies: user.currencies?.rubies || 0,
    },
  });
});

/**
 * PUT /api/users/me/save
 * Reconciles & updates cloud save data uploaded from the Python game client or Web Hub.
 */
exports.syncCloudSave = asyncHandler(async (req, res) => {
  const {
    highScore = 0,
    unlockedChars = [],
    permLevels = {},
    achievements = [],
    campaignProgress = 1,
    goldEarned = 0,
    version = 1,
  } = req.body || {};

  const user = await User.findById(req.user._id);
  if (!user) throw new AppError('User not found', 404);

  if (!user.cloudSave) {
    user.cloudSave = {};
  }

  // 1. Reconcile High Score (keep highest)
  const safeHighScore = Math.max(0, Number(highScore) || 0);
  user.cloudSave.highScore = Math.max(user.cloudSave.highScore || 0, safeHighScore);

  // 2. Reconcile Unlocked Characters (union set)
  const defaultChars = ['warrior', 'mage'];
  const curChars = user.cloudSave.unlockedChars || defaultChars;
  const newChars = Array.isArray(unlockedChars) ? unlockedChars : [];
  user.cloudSave.unlockedChars = Array.from(new Set([...curChars, ...newChars]));

  // 3. Reconcile Permanent Upgrades (keep highest level per stat)
  const curPerm = (user.cloudSave.permLevels instanceof Map)
    ? Object.fromEntries(user.cloudSave.permLevels)
    : (user.cloudSave.permLevels || {});
  const uploadPerm = (permLevels && typeof permLevels === 'object') ? permLevels : {};

  const mergedPerm = { ...curPerm };
  for (const [key, val] of Object.entries(uploadPerm)) {
    const numVal = Math.max(0, Math.min(20, Number(val) || 0));
    mergedPerm[key] = Math.max(mergedPerm[key] || 0, numVal);
  }
  user.cloudSave.permLevels = mergedPerm;

  // 4. Reconcile Achievements (union set)
  const curAch = user.cloudSave.achievements || [];
  const newAch = Array.isArray(achievements) ? achievements : [];
  user.cloudSave.achievements = Array.from(new Set([...curAch, ...newAch]));

  // 5. Reconcile Campaign Progress (keep highest stage)
  const safeCamp = Math.max(1, Number(campaignProgress) || 1);
  user.cloudSave.campaignProgress = Math.max(user.cloudSave.campaignProgress || 1, safeCamp);

  // 6. Safe gold addition
  const safeGold = Math.max(0, Math.min(Number(goldEarned) || 0, 50000));
  if (safeGold > 0) {
    user.currencies.gold = (user.currencies.gold || 0) + safeGold;
  }

  user.cloudSave.version = Math.max(user.cloudSave.version || 1, Number(version) || 1) + 1;
  user.cloudSave.lastSyncedAt = new Date();

  await user.save();

  res.json({
    success: true,
    message: 'Cloud save synchronized successfully',
    cloudSave: {
      highScore: user.cloudSave.highScore,
      unlockedChars: user.cloudSave.unlockedChars,
      permLevels: (user.cloudSave.permLevels instanceof Map)
        ? Object.fromEntries(user.cloudSave.permLevels)
        : user.cloudSave.permLevels,
      achievements: user.cloudSave.achievements,
      campaignProgress: user.cloudSave.campaignProgress,
      version: user.cloudSave.version,
      lastSyncedAt: user.cloudSave.lastSyncedAt,
    },
    currencies: {
      gold: user.currencies.gold,
      diamonds: user.currencies.diamonds,
      rubies: user.currencies.rubies,
    },
  });
});

/**
 * POST /api/users/me/achievements
 * Validates and grants rewards for newly unlocked achievements.
 */
exports.unlockAchievement = asyncHandler(async (req, res) => {
  const { achievementId } = req.body || {};
  if (!achievementId || typeof achievementId !== 'string') {
    throw new AppError('Achievement ID is required', 400);
  }

  const user = await User.findById(req.user._id);
  if (!user) throw new AppError('User not found', 404);

  if (!user.cloudSave) user.cloudSave = {};
  const currentAchievements = user.cloudSave.achievements || [];

  if (currentAchievements.includes(achievementId)) {
    return res.json({
      success: true,
      message: 'Achievement already claimed',
      alreadyClaimed: true,
      achievementId,
      user: user.toPublicJSON(),
    });
  }

  // Award rewards: +10 diamonds, +250 gold, +15 rankPoints
  const reward = { diamonds: 10, gold: 250, rankPoints: 15 };
  user.cloudSave.achievements.push(achievementId);
  user.currencies.diamonds = (user.currencies.diamonds || 0) + reward.diamonds;
  user.currencies.gold = (user.currencies.gold || 0) + reward.gold;
  user.rankPoints = (user.rankPoints || 0) + reward.rankPoints;

  await user.save();

  res.json({
    success: true,
    message: `Achievement unlocked: ${achievementId}! Granted +${reward.diamonds} Diamonds, +${reward.gold} Gold, +${reward.rankPoints} RP`,
    alreadyClaimed: false,
    achievementId,
    reward,
    user: user.toPublicJSON(),
  });
});

exports.DAILY_COOLDOWN_MS = DAILY_COOLDOWN_MS;


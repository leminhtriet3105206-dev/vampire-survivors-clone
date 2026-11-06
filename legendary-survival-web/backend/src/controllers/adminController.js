'use strict';

const User = require('../models/User');
const { getRankTier } = require('../models/User');
const AppError = require('../utils/AppError');
const asyncHandler = require('../utils/asyncHandler');

const VALID_CURRENCIES = ['gold', 'diamonds', 'rubies'];

function normalizeCurrency(raw) {
  if (typeof raw !== 'string') return null;
  const lower = raw.trim().toLowerCase();
  if (lower === 'diamond') return 'diamonds';
  if (lower === 'ruby') return 'rubies';
  return VALID_CURRENCIES.includes(lower) ? lower : null;
}

/**
 * GET /api/admin/users
 * Returns a list of all registered users with role, currencies, and stats.
 */
exports.getUsers = asyncHandler(async (req, res) => {
  const users = await User.find({})
    .select('username email role currencies adminBuffs rankPoints equippedSkin equippedFrame createdAt')
    .sort({ createdAt: -1 })
    .lean();

  res.json({
    success: true,
    count: users.length,
    users: users.map((u) => ({
      id: u._id.toString(),
      username: u.username,
      email: u.email,
      role: u.role || 'player',
      currencies: {
        gold: u.currencies?.gold || 0,
        diamonds: u.currencies?.diamonds || 0,
        rubies: u.currencies?.rubies || 0,
      },
      gold: u.currencies?.gold || 0,
      diamonds: u.currencies?.diamonds || 0,
      rubies: u.currencies?.rubies || 0,
      adminBuffs: {
        bonusHp: u.adminBuffs?.bonusHp || 0,
        bonusDamage: u.adminBuffs?.bonusDamage || 0,
      },
      bonusHp: u.adminBuffs?.bonusHp || 0,
      bonusDamage: u.adminBuffs?.bonusDamage || 0,
      rankPoints: u.rankPoints || 0,
      rankTier: getRankTier(u.rankPoints || 0),
      createdAt: u.createdAt,
    })),
  });
});

/**
 * POST /api/admin/give-currency
 * Body: { targetUsername, currencyType, amount }
 * Safely increments/decrements a user's currency balance.
 */
exports.giveCurrency = asyncHandler(async (req, res) => {
  const { targetUsername, currencyType, amount } = req.body;

  if (!targetUsername || typeof targetUsername !== 'string' || !targetUsername.trim()) {
    throw new AppError('Target username is required', 400);
  }

  const currency = normalizeCurrency(currencyType);
  if (!currency) {
    throw new AppError(`Invalid currency type: "${currencyType}". Must be gold, diamonds, or rubies.`, 400);
  }

  const parsedAmount = Number.parseInt(amount, 10);
  if (!Number.isFinite(parsedAmount) || parsedAmount === 0) {
    throw new AppError('Amount must be a non-zero integer', 400);
  }

  const user = await User.findOne({ usernameLower: targetUsername.trim().toLowerCase() });
  if (!user) {
    throw new AppError(`User "${targetUsername}" not found`, 404);
  }

  if (!user.currencies) {
    user.currencies = { gold: 0, diamonds: 0, rubies: 0 };
  }

  const current = user.currencies[currency] || 0;
  const nextVal = Math.max(0, current + parsedAmount);
  user.currencies[currency] = nextVal;
  await user.save();

  res.json({
    success: true,
    message: `Successfully adjusted ${currency} for ${user.username} by ${parsedAmount >= 0 ? '+' : ''}${parsedAmount}. New balance: ${nextVal}`,
    user: user.toPublicJSON(),
    granted: {
      targetUsername: user.username,
      currency,
      amount: parsedAmount,
      newBalance: nextVal,
    },
  });
});

/**
 * POST /api/admin/set-stats
 * Body: { targetUsername, bonusHp, bonusDamage }
 * Updates target user's admin power buffs.
 */
exports.setStats = asyncHandler(async (req, res) => {
  const { targetUsername, bonusHp, bonusDamage } = req.body;

  if (!targetUsername || typeof targetUsername !== 'string' || !targetUsername.trim()) {
    throw new AppError('Target username is required', 400);
  }

  const hpVal = Math.max(0, Number.parseInt(bonusHp, 10) || 0);
  const dmgVal = Math.max(0, Number.parseInt(bonusDamage, 10) || 0);

  const user = await User.findOne({ usernameLower: targetUsername.trim().toLowerCase() });
  if (!user) {
    throw new AppError(`User "${targetUsername}" not found`, 404);
  }

  user.adminBuffs = {
    bonusHp: hpVal,
    bonusDamage: dmgVal,
  };
  await user.save();

  res.json({
    success: true,
    message: `Updated GM buffs for ${user.username}: +${hpVal} HP, +${dmgVal} Damage`,
    user: user.toPublicJSON(),
    adminBuffs: user.adminBuffs,
  });
});

module.exports.normalizeCurrency = normalizeCurrency;


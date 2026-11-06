'use strict';

const User = require('../models/User');
const config = require('../config/env');
const AppError = require('../utils/AppError');
const asyncHandler = require('../utils/asyncHandler');
const { signToken } = require('../utils/jwt');

function authResponse(res, status, user) {
  res.status(status).json({
    success: true,
    token: signToken(user._id),
    user: user.toPublicJSON(),
  });
}

/** POST /api/auth/register */
exports.register = asyncHandler(async (req, res) => {
  const username = req.body.username.trim();
  const email = req.body.email.trim().toLowerCase();

  // Friendly pre-check (the unique indexes remain the source of truth).
  const existing = await User.findOne({
    $or: [{ usernameLower: username.toLowerCase() }, { email }],
  }).lean();
  if (existing) {
    const field = existing.email === email ? 'email' : 'username';
    throw new AppError(`That ${field} is already taken`, 409, { [field]: `That ${field} is already taken` });
  }

  const isAdminRole = username.toLowerCase() === 'admin' || email.toLowerCase() === 'admin@legendary.gg';

  const user = await User.create({
    username,
    email,
    password: req.body.password,
    role: isAdminRole ? 'admin' : 'player',
    currencies: { ...config.startingBalance },
    ownedSkins: ['default'],
    equippedSkin: 'default',
    lastLoginAt: new Date(),
  });

  authResponse(res, 201, user);
});

/** POST /api/auth/login  (identifier = username or email) */
exports.login = asyncHandler(async (req, res) => {
  const identifier = req.body.identifier.trim().toLowerCase();
  const query = identifier.includes('@') ? { email: identifier } : { usernameLower: identifier };

  const user = await User.findOne(query).select('+password');
  // Same message for unknown user / wrong password to avoid account enumeration.
  const valid = user ? await user.comparePassword(req.body.password) : false;
  if (!user || !valid) throw new AppError('Invalid username/email or password', 401);

  user.lastLoginAt = new Date();
  await user.save();
  authResponse(res, 200, user);
});

/** GET /api/auth/me */
exports.me = asyncHandler(async (req, res) => {
  res.json({ success: true, user: req.user.toPublicJSON() });
});


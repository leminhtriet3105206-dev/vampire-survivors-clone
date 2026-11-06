'use strict';

const User = require('../models/User');
const AppError = require('../utils/AppError');
const asyncHandler = require('../utils/asyncHandler');
const { verifyToken } = require('../utils/jwt');

function extractBearer(header) {
  if (typeof header !== 'string') return null;
  const [scheme, token] = header.split(' ');
  return scheme === 'Bearer' && token ? token.trim() : null;
}

/**
 * Requires a valid "Authorization: Bearer <jwt>" header and attaches req.user.
 * jsonwebtoken errors are translated to 401 by the error handler.
 */
const requireAuth = asyncHandler(async (req, res, next) => {
  const token = extractBearer(req.headers.authorization);
  if (!token) throw new AppError('Authentication required', 401);

  const payload = verifyToken(token);
  const user = await User.findById(payload.sub);
  if (!user) throw new AppError('Account no longer exists', 401);

  req.user = user;
  next();
});

/**
 * Requires the authenticated user to have the "admin" role.
 */
const isAdmin = (req, res, next) => {
  if (!req.user) {
    return next(new AppError('Authentication required', 401));
  }
  if (req.user.role !== 'admin') {
    return next(new AppError('Access denied: Administrator privileges required', 403));
  }
  next();
};

module.exports = { requireAuth, isAdmin, extractBearer };


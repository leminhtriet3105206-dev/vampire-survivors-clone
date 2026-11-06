'use strict';

const { rateLimit } = require('express-rate-limit');

const json429 = (message) => (req, res) =>
  res.status(429).json({ success: false, message });

/** Brute-force protection for login / register (relaxed for dev). */
const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  limit: 300,
  standardHeaders: 'draft-7',
  legacyHeaders: false,
  handler: json429('Too many authentication attempts, please try again later'),
});

/** General API limiter (relaxed to 600 requests/minute for smooth gameplay & dev). */
const apiLimiter = rateLimit({
  windowMs: 60 * 1000,
  limit: 600,
  standardHeaders: 'draft-7',
  legacyHeaders: false,
  handler: json429('Too many requests, slow down'),
});

module.exports = { authLimiter, apiLimiter };


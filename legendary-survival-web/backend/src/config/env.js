'use strict';

const path = require('path');
const dotenv = require('dotenv');

// Load backend/.env regardless of the current working directory.
dotenv.config({ path: path.resolve(__dirname, '../../.env') });

const DEV_JWT_SECRET = 'dev_only_insecure_secret_change_me';

function toInt(value, fallback) {
  const n = Number.parseInt(value, 10);
  return Number.isFinite(n) && n >= 0 ? n : fallback;
}

const nodeEnv = process.env.NODE_ENV || 'development';
const isProduction = nodeEnv === 'production';

const config = {
  nodeEnv,
  isProduction,
  port: toInt(process.env.PORT, 3000),
  mongoUri: process.env.MONGODB_URI || 'mongodb://127.0.0.1:27017/legendary_survival',
  jwtSecret: process.env.JWT_SECRET || '',
  jwtExpiresIn: process.env.JWT_EXPIRES_IN || '7d',
  bcryptRounds: Math.min(15, Math.max(8, toInt(process.env.BCRYPT_ROUNDS, 12))),
  clientOrigins: (process.env.CLIENT_ORIGIN || '')
    .split(',')
    .map((o) => o.trim())
    .filter(Boolean),
  startingBalance: {
    gold: toInt(process.env.STARTING_GOLD, 1500),
    diamonds: toInt(process.env.STARTING_DIAMONDS, 60),
    rubies: toInt(process.env.STARTING_RUBIES, 10),
  },
  chat: {
    maxLength: 300,
    historySize: 50,
    minIntervalMs: 800,
  },
};

// Validate configuration at startup so problems surface immediately.
if (!config.jwtSecret || config.jwtSecret === 'change_me_to_a_long_random_string') {
  if (isProduction) {
    throw new Error('JWT_SECRET must be set to a strong random value in production.');
  }
  // eslint-disable-next-line no-console
  console.warn('[config] JWT_SECRET not set - using an insecure development secret.');
  config.jwtSecret = DEV_JWT_SECRET;
}

module.exports = config;


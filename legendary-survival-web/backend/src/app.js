'use strict';

const path = require('path');
const express = require('express');
const helmet = require('helmet');
const cors = require('cors');

const config = require('./config/env');
const apiRoutes = require('./routes');
const { apiLimiter } = require('./middleware/rateLimiters');
const { notFound, errorHandler } = require('./middleware/errorHandler');

const FRONTEND_DIR = path.resolve(__dirname, '../../frontend');

function corsOptions() {
  // Same-origin (built-in static server) needs no CORS; extra origins come from CLIENT_ORIGIN.
  if (config.clientOrigins.length === 0) return { origin: false };
  return { origin: config.clientOrigins, credentials: false };
}

function createApp() {
  const app = express();

  app.disable('x-powered-by');
  app.set('trust proxy', 1);

  app.use(
    helmet({
      crossOriginEmbedderPolicy: false,
      crossOriginResourcePolicy: { policy: 'cross-origin' },
      contentSecurityPolicy: {
        useDefaults: true,
        directives: {
          'default-src': ["'self'"],
          'connect-src': ["'self'", 'ws:', 'wss:', 'blob:', 'data:', 'https://pygame-web.github.io', ...config.clientOrigins],
          'img-src': ["'self'", 'data:', 'blob:', 'https://pygame-web.github.io'],
          'script-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'", "'wasm-unsafe-eval'", 'blob:', 'https://pygame-web.github.io'],
          'worker-src': ["'self'", 'blob:'],
          'frame-src': ["'self'"],
          // Allow plain-HTTP usage (localhost / LAN) without forcing HTTPS upgrades.
          'upgrade-insecure-requests': null,
        },
      },
    })
  );
  app.use(cors(corsOptions()));
  app.use(express.json({ limit: '20kb' }));

  app.use('/api', apiLimiter, apiRoutes);
  app.use('/api', notFound); // unknown API routes -> JSON 404

  // Serve the vanilla-JS frontend.
  app.use(express.static(FRONTEND_DIR, { extensions: ['html'] }));
  app.get('/', (req, res) => res.sendFile(path.join(FRONTEND_DIR, 'index.html')));

  app.use(notFound);
  app.use(errorHandler);
  return app;
}

module.exports = { createApp, corsOptions };

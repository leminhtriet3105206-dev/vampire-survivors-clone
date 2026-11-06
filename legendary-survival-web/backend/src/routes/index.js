'use strict';

const router = require('express').Router();
const mongoose = require('mongoose');

router.get('/health', (req, res) => {
  res.json({
    success: true,
    status: 'ok',
    db: mongoose.connection.readyState === 1 ? 'connected' : 'disconnected',
    uptime: Math.round(process.uptime()),
  });
});

router.use('/auth', require('./authRoutes'));
router.use('/shop', require('./shopRoutes'));
router.use('/users', require('./userRoutes'));
router.use('/chat', require('./chatRoutes'));
router.use('/admin', require('./adminRoutes'));

module.exports = router;


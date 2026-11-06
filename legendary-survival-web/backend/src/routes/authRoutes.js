'use strict';

const router = require('express').Router();
const auth = require('../controllers/authController');
const { requireAuth } = require('../middleware/auth');
const { registerRules, loginRules } = require('../middleware/validate');
const { authLimiter } = require('../middleware/rateLimiters');

router.post('/register', authLimiter, registerRules, auth.register);
router.post('/login', authLimiter, loginRules, auth.login);
router.get('/me', requireAuth, auth.me);

module.exports = router;


'use strict';

const router = require('express').Router();
const chat = require('../controllers/chatController');
const { requireAuth } = require('../middleware/auth');

router.get('/messages', requireAuth, chat.listMessages);

module.exports = router;


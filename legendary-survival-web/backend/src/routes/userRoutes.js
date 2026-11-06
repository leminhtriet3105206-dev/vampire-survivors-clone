'use strict';

const router = require('express').Router();
const users = require('../controllers/userController');
const { requireAuth } = require('../middleware/auth');
const { equipRules, addGoldRules, addDiamondsRules } = require('../middleware/validate');

// Public routes
router.get('/leaderboard', users.getLeaderboard);

// Authenticated routes
router.use(requireAuth);
router.get('/me/save', users.getCloudSave);
router.put('/me/save', users.syncCloudSave);
router.post('/me/achievements', users.unlockAchievement);
router.get('/me/history', users.getMatchHistory);
router.post('/me/record-match', users.recordMatch);
router.patch('/me/equipped-skin', equipRules, users.equipSkin);
router.patch('/me/equipped-frame', equipRules, users.equipFrame);
router.post('/me/daily-reward', users.claimDailyReward);
router.post('/me/add-gold', addGoldRules, users.addGold);
router.post('/me/add-diamonds', addDiamondsRules, users.addDiamonds);

module.exports = router;


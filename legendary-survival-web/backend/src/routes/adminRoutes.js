'use strict';

const router = require('express').Router();
const adminController = require('../controllers/adminController');
const { requireAuth, isAdmin } = require('../middleware/auth');

// All admin routes require valid authentication and role === 'admin'
router.use(requireAuth);
router.use(isAdmin);

router.get('/users', adminController.getUsers);
router.post('/give-currency', adminController.giveCurrency);
router.post('/set-stats', adminController.setStats);

module.exports = router;


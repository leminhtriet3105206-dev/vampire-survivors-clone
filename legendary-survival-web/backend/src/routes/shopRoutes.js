'use strict';

const router = require('express').Router();
const shop = require('../controllers/shopController');
const { requireAuth } = require('../middleware/auth');
const { slugParamRules } = require('../middleware/validate');

router.get('/skins', shop.listSkins);
router.post('/skins/:slug/purchase', requireAuth, slugParamRules, shop.purchaseSkin);

module.exports = router;


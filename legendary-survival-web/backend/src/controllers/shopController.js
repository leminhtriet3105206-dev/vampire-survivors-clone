'use strict';

const Skin = require('../models/Skin');
const User = require('../models/User');
const AppError = require('../utils/AppError');
const asyncHandler = require('../utils/asyncHandler');

const CURRENCY_LABEL = { gold: 'Gold', diamonds: 'Diamonds', rubies: 'Rubies' };

/** GET /api/shop/skins */
exports.listSkins = asyncHandler(async (req, res) => {
  const skins = await Skin.find({ isActive: true }).sort({ sortOrder: 1, name: 1 });
  res.json({ success: true, skins: skins.map((s) => s.toPublicJSON()) });
});

/**
 * POST /api/shop/skins/:slug/purchase
 * Uses a single conditional atomic update so a player can never go negative
 * or buy the same skin twice, even with concurrent requests.
 */
exports.purchaseSkin = asyncHandler(async (req, res) => {
  const { slug } = req.params;
  const skin = await Skin.findOne({ slug, isActive: true });
  if (!skin) throw new AppError('Item not found', 404);

  const isFrame = skin.itemType === 'frame';
  const ownershipField = isFrame ? 'ownedFrames' : 'ownedSkins';
  const { currency, amount } = skin.price;
  const balancePath = `currencies.${currency}`;

  const updated = await User.findOneAndUpdate(
    { _id: req.user._id, [ownershipField]: { $ne: slug }, [balancePath]: { $gte: amount } },
    { $inc: { [balancePath]: -amount }, $addToSet: { [ownershipField]: slug } },
    { new: true, runValidators: true }
  );

  if (!updated) {
    const fresh = await User.findById(req.user._id);
    if (!fresh) throw new AppError('Account no longer exists', 401);
    const ownedList = isFrame ? fresh.ownedFrames : fresh.ownedSkins;
    if (ownedList && ownedList.includes(slug)) {
      throw new AppError(`You already own this ${isFrame ? 'avatar frame' : 'skin'}`, 409);
    }
    const have = fresh.currencies?.[currency] ?? 0;
    throw new AppError(
      `Not enough ${CURRENCY_LABEL[currency]}: need ${amount}, you have ${have}`,
      400,
      { currency, required: amount, balance: have }
    );
  }

  res.json({
    success: true,
    message: `Purchased ${skin.name}!`,
    skin: skin.toPublicJSON(),
    user: updated.toPublicJSON(),
  });
});


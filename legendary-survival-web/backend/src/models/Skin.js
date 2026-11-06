'use strict';

const mongoose = require('mongoose');

const RARITIES = ['common', 'rare', 'epic', 'legendary', 'mythic'];
const CURRENCIES = ['gold', 'diamonds', 'rubies'];
const HEX_COLOR = /^#[0-9a-fA-F]{6}$/;

const skinSchema = new mongoose.Schema(
  {
    slug: {
      type: String,
      required: true,
      unique: true,
      lowercase: true,
      trim: true,
      match: /^[a-z0-9-]{2,40}$/,
    },
    name: { type: String, required: true, trim: true, maxlength: 60 },
    inspiredBy: { type: String, trim: true, maxlength: 60, default: '' },
    description: { type: String, trim: true, maxlength: 300, default: '' },
    rarity: { type: String, enum: RARITIES, default: 'common' },
    price: {
      currency: { type: String, enum: CURRENCIES, required: true },
      amount: { type: Number, required: true, min: 0 },
    },
    colors: {
      primary: { type: String, match: HEX_COLOR, default: '#6c7cff' },
      secondary: { type: String, match: HEX_COLOR, default: '#2b2f6b' },
      accent: { type: String, match: HEX_COLOR, default: '#ffd34d' },
    },
    emblem: { type: String, trim: true, maxlength: 3, default: '★' },
    itemType: { type: String, enum: ['skin', 'frame'], default: 'skin' },
    sortOrder: { type: Number, default: 0 },
    isActive: { type: Boolean, default: true },
  },
  { timestamps: true }
);

skinSchema.methods.toPublicJSON = function toPublicJSON() {
  return {
    slug: this.slug,
    name: this.name,
    inspiredBy: this.inspiredBy,
    description: this.description,
    rarity: this.rarity,
    itemType: this.itemType || 'skin',
    price: { currency: this.price.currency, amount: this.price.amount },
    colors: {
      primary: this.colors?.primary,
      secondary: this.colors?.secondary,
      accent: this.colors?.accent,
    },
    emblem: this.emblem,
  };
};

module.exports = mongoose.model('Skin', skinSchema);
module.exports.RARITIES = RARITIES;

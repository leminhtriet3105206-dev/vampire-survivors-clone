'use strict';

const Skin = require('../models/Skin');
const skins = require('./skins.data');

/** Upserts the skin catalogue by slug. Safe to run on every startup. */
async function seedSkins() {
  const ops = skins.map((skin) => ({
    updateOne: {
      filter: { slug: skin.slug },
      update: { $set: { ...skin, isActive: true } },
      upsert: true,
    },
  }));
  const result = await Skin.bulkWrite(ops, { ordered: false });
  console.log(
    `[seed] Skins synced: ${skins.length} total (${result.upsertedCount} new, ${result.modifiedCount} updated)`
  );
}

module.exports = { seedSkins };


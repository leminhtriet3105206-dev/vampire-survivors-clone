'use strict';

// Standalone seeding script: `npm run seed`
const { connectDB, disconnectDB } = require('../config/db');
const { seedSkins } = require('./seedSkins');

(async () => {
  try {
    await connectDB();
    await seedSkins();
    await disconnectDB();
    process.exit(0);
  } catch (err) {
    console.error('[seed] Failed:', err.message);
    process.exit(1);
  }
})();


'use strict';

const mongoose = require('mongoose');
const config = require('./env');

mongoose.set('strictQuery', true);

async function connectDB() {
  mongoose.connection.on('disconnected', () => console.warn('[db] MongoDB disconnected'));
  mongoose.connection.on('reconnected', () => console.log('[db] MongoDB reconnected'));
  mongoose.connection.on('error', (err) => console.error('[db] MongoDB error:', err.message));

  await mongoose.connect(config.mongoUri, { serverSelectionTimeoutMS: 8000 });
  const { host, port, name } = mongoose.connection;
  console.log(`[db] Connected to MongoDB ${host}:${port}/${name}`);
  return mongoose.connection;
}

async function disconnectDB() {
  await mongoose.connection.close();
}

module.exports = { connectDB, disconnectDB };


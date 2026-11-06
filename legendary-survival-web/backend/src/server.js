'use strict';

const http = require('http');
const { Server } = require('socket.io');

const config = require('./config/env');
const { connectDB, disconnectDB } = require('./config/db');
const { createApp, corsOptions } = require('./app');
const { seedSkins } = require('./seed/seedSkins');
const { registerChatSocket } = require('./sockets/chatSocket');
const { registerRoomSocket } = require('./sockets/roomSocket');
const { registerMatchmakingSocket } = require('./sockets/matchmakingSocket');

async function start() {
  await connectDB();
  await seedSkins();

  const app = createApp();
  const server = http.createServer(app);

  const io = new Server(server, {
    cors: corsOptions(),
    maxHttpBufferSize: 16 * 1024,
  });
  registerChatSocket(io);
  registerRoomSocket(io);
  registerMatchmakingSocket(io);

  server.listen(config.port, () => {
    console.log(`[server] Legendary Survival running at http://localhost:${config.port} (${config.nodeEnv})`);
  });

  const shutdown = async (signal) => {
    console.log(`[server] ${signal} received, shutting down...`);
    io.close();
    server.close(async () => {
      await disconnectDB().catch(() => {});
      process.exit(0);
    });
    setTimeout(() => process.exit(1), 10000).unref();
  };
  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));
}

process.on('unhandledRejection', (reason) => {
  console.error('[server] Unhandled rejection:', reason);
});

start().catch((err) => {
  console.error('[server] Failed to start:', err.message);
  if (/ECONNREFUSED|Server selection timed out/i.test(err.message)) {
    console.error('  -> Is MongoDB running? Check MONGODB_URI in backend/.env');
  }
  process.exit(1);
});


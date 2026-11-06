'use strict';

const jwt = require('jsonwebtoken');
const config = require('../config/env');

function signToken(userId) {
  return jwt.sign({ sub: String(userId) }, config.jwtSecret, {
    expiresIn: config.jwtExpiresIn,
  });
}

/** Returns the decoded payload or throws a jsonwebtoken error. */
function verifyToken(token) {
  return jwt.verify(token, config.jwtSecret);
}

module.exports = { signToken, verifyToken };


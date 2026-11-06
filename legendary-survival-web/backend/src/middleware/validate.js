'use strict';

const AppError = require('../utils/AppError');
const { USERNAME_REGEX, EMAIL_REGEX } = require('../models/User');

const SLUG_REGEX = /^[a-z0-9-]{2,40}$/;

const isNonEmptyString = (v) => typeof v === 'string' && v.trim().length > 0;

/**
 * Builds an Express middleware from a validator function.
 * The validator receives req and returns an object of { field: message }.
 */
function validate(validator) {
  return (req, res, next) => {
    const errors = validator(req) || {};
    if (Object.keys(errors).length > 0) {
      return next(new AppError('Validation failed', 400, errors));
    }
    return next();
  };
}

const registerRules = validate((req) => {
  const { username, email, password, confirmPassword } = req.body || {};
  const errors = {};

  if (!isNonEmptyString(username)) errors.username = 'Username is required';
  else if (!USERNAME_REGEX.test(username.trim()))
    errors.username = 'Username must be 3-20 characters (letters, numbers, underscore)';

  if (!isNonEmptyString(email)) errors.email = 'Email is required';
  else if (email.length > 254 || !EMAIL_REGEX.test(email.trim()))
    errors.email = 'Email address is invalid';

  if (typeof password !== 'string' || password.length === 0) errors.password = 'Password is required';
  else if (password.length < 8 || password.length > 72)
    errors.password = 'Password must be 8-72 characters';
  else if (!/[A-Za-z]/.test(password) || !/\d/.test(password))
    errors.password = 'Password must contain at least one letter and one number';

  if (confirmPassword !== undefined && confirmPassword !== password)
    errors.confirmPassword = 'Passwords do not match';

  return errors;
});

const loginRules = validate((req) => {
  const { identifier, password } = req.body || {};
  const errors = {};
  if (!isNonEmptyString(identifier)) errors.identifier = 'Username or email is required';
  else if (identifier.length > 254) errors.identifier = 'Username or email is too long';
  if (typeof password !== 'string' || password.length === 0) errors.password = 'Password is required';
  else if (password.length > 72) errors.password = 'Password is too long';
  return errors;
});

const slugParamRules = validate((req) => {
  const { slug } = req.params;
  return SLUG_REGEX.test(slug || '') ? {} : { slug: 'Invalid skin id' };
});

const equipRules = validate((req) => {
  const { slug } = req.body || {};
  return typeof slug === 'string' && SLUG_REGEX.test(slug) ? {} : { slug: 'Invalid skin id' };
});

const addGoldRules = validate((req) => {
  const gold = Number.parseInt(req.body?.gold, 10);
  if (!Number.isFinite(gold) || gold <= 0) {
    return { gold: 'Gold must be a positive integer' };
  }
  return {};
});

const addDiamondsRules = validate((req) => {
  const diamonds = Number.parseInt(req.body?.diamonds, 10);
  if (!Number.isFinite(diamonds) || diamonds <= 0) {
    return { diamonds: 'Diamonds must be a positive integer' };
  }
  return {};
});

module.exports = {
  validate,
  registerRules,
  loginRules,
  slugParamRules,
  equipRules,
  addGoldRules,
  addDiamondsRules,
  SLUG_REGEX,
};


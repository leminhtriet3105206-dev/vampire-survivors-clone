// Login / register page logic (index.html).
import { api, session, ApiError } from './api.js';
import { toast, setBusy } from './ui.js';

const USERNAME_RE = /^[a-zA-Z0-9_]{3,20}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

const tabs = document.querySelectorAll('[data-tab]');
const forms = {
  login: document.getElementById('login-form'),
  register: document.getElementById('register-form'),
};

function showTab(name) {
  tabs.forEach((t) => {
    const active = t.dataset.tab === name;
    t.classList.toggle('active', active);
    t.setAttribute('aria-selected', String(active));
  });
  Object.entries(forms).forEach(([key, form]) => form.classList.toggle('hidden', key !== name));
  clearErrors(forms[name]);
}

function clearErrors(form) {
  form.querySelectorAll('.field-error').forEach((n) => (n.textContent = ''));
  form.querySelectorAll('.invalid').forEach((n) => n.classList.remove('invalid'));
  const banner = form.querySelector('.form-error');
  if (banner) banner.textContent = '';
}

function showErrors(form, errors = {}, banner = '') {
  for (const [field, message] of Object.entries(errors)) {
    const input = form.querySelector(`[name="${field}"]`);
    const slot = form.querySelector(`[data-error-for="${field}"]`);
    if (input) input.classList.add('invalid');
    if (slot) slot.textContent = message;
  }
  const bannerNode = form.querySelector('.form-error');
  if (bannerNode) bannerNode.textContent = banner;
}

function validateRegister({ username, email, password, confirmPassword }) {
  const errors = {};
  if (!USERNAME_RE.test(username)) errors.username = '3-20 characters: letters, numbers, underscore';
  if (!EMAIL_RE.test(email)) errors.email = 'Enter a valid email address';
  if (password.length < 8 || password.length > 72) errors.password = 'Password must be 8-72 characters';
  else if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) errors.password = 'Use at least one letter and one number';
  if (confirmPassword !== password) errors.confirmPassword = 'Passwords do not match';
  return errors;
}

function enterGame(data) {
  session.save(data.token, data.user);
  window.location.replace('/game.html');
}

async function handleSubmit(form, kind) {
  clearErrors(form);
  const values = Object.fromEntries(new FormData(form).entries());
  Object.keys(values).forEach((k) => {
    if (k !== 'password' && k !== 'confirmPassword') values[k] = String(values[k]).trim();
  });

  const clientErrors =
    kind === 'register'
      ? validateRegister(values)
      : {
          ...(values.identifier ? {} : { identifier: 'Username or email is required' }),
          ...(values.password ? {} : { password: 'Password is required' }),
        };
  if (Object.keys(clientErrors).length) return showErrors(form, clientErrors);

  const restore = setBusy(form.querySelector('button[type="submit"]'));
  try {
    const data = kind === 'register' ? await api.register(values) : await api.login(values);
    toast(kind === 'register' ? 'Account created! Welcome, legend.' : 'Welcome back!', 'success');
    enterGame(data);
  } catch (err) {
    restore();
    if (err instanceof ApiError) showErrors(form, err.details || {}, err.message);
    else showErrors(form, {}, 'Unexpected error, please try again.');
  }
}

tabs.forEach((t) => t.addEventListener('click', () => showTab(t.dataset.tab)));
forms.login.addEventListener('submit', (e) => {
  e.preventDefault();
  handleSubmit(forms.login, 'login');
});
forms.register.addEventListener('submit', (e) => {
  e.preventDefault();
  handleSubmit(forms.register, 'register');
});

document.querySelectorAll('[data-toggle-password]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const input = document.getElementById(btn.dataset.togglePassword);
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    btn.textContent = show ? 'Hide' : 'Show';
  });
});

// Message left by the game page (logout / expired session).
const flash = sessionStorage.getItem('ls_flash');
if (flash) {
  sessionStorage.removeItem('ls_flash');
  toast(flash, 'info');
}

// Already logged in with a valid token? Skip straight to the game.
(async () => {
  if (!session.token) return;
  try {
    const { user } = await api.me();
    session.save(null, user);
    window.location.replace('/game.html');
  } catch {
    session.clear();
  }
})();

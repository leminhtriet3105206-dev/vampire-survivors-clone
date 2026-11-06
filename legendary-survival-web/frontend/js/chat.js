// World chat over Socket.io.
import { API_BASE, session } from './api.js';
import { store } from './store.js';
import { el, toast, skinAvatar, rankBadge } from './ui.js';

const MAX_LEN = 300;
let socket = null;
let list;
let input;
let sendBtn;
let statusNode;
let onlineNode;
const seen = new Set();

function timeLabel(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function setStatus(state, text) {
  statusNode.className = `chat-status status-${state}`;
  statusNode.textContent = text;
  const enabled = state === 'online';
  input.disabled = !enabled;
  sendBtn.disabled = !enabled;
}

function isNearBottom() {
  return list.scrollHeight - list.scrollTop - list.clientHeight < 80;
}

function messageNode(msg) {
  const mine = store.user && msg.userId === store.user.id;
  const skin = store.skinBySlug(msg.skin) || { colors: undefined, emblem: msg.username[0] };
  const frame = msg.frame || 'default';
  const tier = msg.rankTier || 'Bronze';

  return el('li', { class: `chat-msg${mine ? ' mine' : ''}` }, [
    skinAvatar(skin, 'xs', frame),
    el('div', { class: 'chat-bubble' }, [
      el('div', { class: 'chat-meta' }, [
        rankBadge(tier),
        el('span', { class: 'chat-user', text: msg.username }),
        el('time', { class: 'chat-time', datetime: msg.createdAt, text: timeLabel(msg.createdAt) }),
      ]),
      // textContent only -> user input can never inject HTML.
      el('p', { class: 'chat-text', text: msg.text }),
    ]),
  ]);
}

function appendMessage(msg, { forceScroll = false } = {}) {
  if (!msg || seen.has(msg.id)) return;
  seen.add(msg.id);
  const stick = forceScroll || isNearBottom();
  list.append(messageNode(msg));
  while (list.children.length > 200) list.firstElementChild.remove();
  if (stick) list.scrollTop = list.scrollHeight;
}

function systemLine(text) {
  list.append(el('li', { class: 'chat-system', text }));
  list.scrollTop = list.scrollHeight;
}

function send() {
  const text = input.value.replace(/\s+/g, ' ').trim();
  if (!text) return;
  if (text.length > MAX_LEN) {
    toast(`Message too long (max ${MAX_LEN} characters)`, 'error');
    return;
  }
  if (!socket || !socket.connected) {
    toast('Chat is offline', 'error');
    return;
  }
  sendBtn.disabled = true;
  socket.timeout(5000).emit('chat:send', { text }, (err, res) => {
    sendBtn.disabled = !socket.connected;
    if (err) return toast('Server did not respond, try again', 'error');
    if (!res || !res.ok) return toast((res && res.error) || 'Message not sent', 'error');
    input.value = '';
    updateCounter();
    input.focus();
  });
}

function updateCounter() {
  const counter = document.getElementById('chat-counter');
  if (!counter) return;
  counter.textContent = `${input.value.length}/${MAX_LEN}`;
  counter.classList.toggle('over', input.value.length > MAX_LEN);
}

export function initChat() {
  if (socket) return socket;

  list = document.getElementById('chat-list');
  input = document.getElementById('chat-input');
  sendBtn = document.getElementById('chat-send');
  statusNode = document.getElementById('chat-status');
  onlineNode = document.getElementById('chat-online');

  input.maxLength = MAX_LEN;
  input.addEventListener('input', updateCounter);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });
  document.getElementById('chat-form').addEventListener('submit', (e) => {
    e.preventDefault();
    send();
  });

  if (typeof window.io !== 'function') {
    setStatus('offline', 'Offline');
    systemLine('Socket.io client failed to load - chat unavailable.');
    return;
  }

  setStatus('connecting', 'Connecting...');
  socket = window.io(API_BASE || undefined, {
    auth: { token: session.token },
    reconnectionDelayMax: 8000,
  });

  socket.on('connect', () => setStatus('online', 'Online'));
  socket.on('disconnect', (reason) => {
    setStatus('connecting', 'Reconnecting...');
    if (reason === 'io server disconnect') socket.connect();
  });
  socket.on('connect_error', (err) => {
    if (String(err.message).startsWith('AUTH_')) {
      setStatus('offline', 'Offline');
      window.dispatchEvent(new CustomEvent('ls:unauthorized', { detail: 'Session expired, please log in again' }));
      socket.disconnect();
    } else {
      setStatus('connecting', 'Reconnecting...');
    }
  });

  socket.on('chat:history', (messages) => {
    list.replaceChildren();
    seen.clear();
    systemLine('Welcome to World Chat! Be kind to fellow survivors.');
    (messages || []).forEach((m) => appendMessage(m, { forceScroll: true }));
  });
  socket.on('chat:message', (msg) => appendMessage(msg));
  socket.on('chat:systemMessage', ({ text }) => {
    systemLine(text);
  });
  socket.on('admin:currencyReceived', ({ currency, amount, message, user }) => {
    if (user && store.user && store.user.id === user.id) {
      store.setUser(user);
    }
    toast(message || `Received ${amount} ${currency}!`, 'success', 5000);
    systemLine(`💰 ${message || `Received ${amount} ${currency}!`}`);
  });
  socket.on('chat:online', ({ count }) => {
    onlineNode.textContent = `${count} online`;
  });
  socket.on('chat:error', ({ message }) => toast(message, 'error'));
}

export function disconnectChat() {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
}

export function getSocket() {
  return socket;
}

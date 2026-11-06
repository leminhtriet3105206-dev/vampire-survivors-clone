// Game Master (GM) Control Panel & RBAC Admin System
import { api, ApiError } from './api.js';
import { store } from './store.js';
import { el, toast, setBusy, formatNumber } from './ui.js';

let modal = null;
let btnHeaderGM = null;
let btnHubGM = null;
let btnCloseModal = null;

// Tab elements
let tabButtons = [];
let tabPanels = {};

// Currency form elements
let formCurrency = null;
let selectCurrencyUser = null;
let inputCurrencyTarget = null;
let selectCurrencyType = null;
let inputCurrencyAmount = null;
let bannerCurrencyStatus = null;

// Power form elements
let formPower = null;
let selectPowerUser = null;
let inputPowerTarget = null;
let inputPowerHp = null;
let inputPowerDmg = null;
let bannerPowerStatus = null;

// Roster elements
let rosterTbody = null;
let btnRefreshRoster = null;
let userCountBadge = null;

let cachedUsers = [];

function showBanner(banner, text, isError = false) {
  if (!banner) return;
  if (!text) {
    banner.textContent = '';
    banner.className = 'gm-status-banner hidden';
  } else {
    banner.textContent = text;
    banner.className = `gm-status-banner ${isError ? 'error' : 'success'}`;
  }
}

export function openGmPanel(defaultTab = 'currency') {
  if (!store.user || store.user.role !== 'admin') {
    toast('Access denied: Administrator privileges required.', 'error');
    return;
  }
  if (!modal) return;
  modal.classList.remove('hidden');
  switchTab(defaultTab);
  loadRoster().catch(console.error);
}

export function closeGmPanel() {
  if (modal) modal.classList.add('hidden');
  showBanner(bannerCurrencyStatus, '');
  showBanner(bannerPowerStatus, '');
}

function switchTab(tabKey) {
  tabButtons.forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.gmTab === tabKey);
  });
  Object.keys(tabPanels).forEach((key) => {
    if (tabPanels[key]) {
      tabPanels[key].classList.toggle('hidden', key !== tabKey);
    }
  });

  if (tabKey === 'roster') {
    loadRoster().catch(console.error);
  }
}

async function loadRoster() {
  if (!store.user || store.user.role !== 'admin') return;
  try {
    const res = await api.getAdminUsers();
    cachedUsers = res.users || [];

    if (userCountBadge) userCountBadge.textContent = String(cachedUsers.length);

    // Populate user selects
    populateUserSelect(selectCurrencyUser);
    populateUserSelect(selectPowerUser);

    // Render roster table
    renderRosterTable(cachedUsers);
  } catch (err) {
    console.error('Failed to load user roster:', err);
    if (rosterTbody) {
      rosterTbody.innerHTML = `<tr><td colspan="8" class="text-center" style="color:#ff8899;">Error loading users: ${err.message}</td></tr>`;
    }
  }
}

function populateUserSelect(selectElem) {
  if (!selectElem) return;
  const currentVal = selectElem.value;
  selectElem.replaceChildren();

  const defaultOpt = document.createElement('option');
  defaultOpt.value = '';
  defaultOpt.textContent = '-- Select Player from Roster --';
  selectElem.appendChild(defaultOpt);

  for (const u of cachedUsers) {
    const opt = document.createElement('option');
    opt.value = u.username;
    opt.textContent = `${u.username} (${u.role.toUpperCase()}) - ${formatNumber(u.gold)}G | ${u.diamonds}D | ${u.rubies}R`;
    selectElem.appendChild(opt);
  }

  if (currentVal) selectElem.value = currentVal;
}

function renderRosterTable(users) {
  if (!rosterTbody) return;
  rosterTbody.replaceChildren();

  if (!users.length) {
    const row = document.createElement('tr');
    row.innerHTML = '<td colspan="8" class="text-center muted">No registered survivors found.</td>';
    rosterTbody.appendChild(row);
    return;
  }

  for (const u of users) {
    const tr = document.createElement('tr');

    const tdUser = el('td', { class: 'font-bold' }, [
      el('span', { text: u.username }),
      u.username === store.user?.username ? el('span', { class: 'slot-tag tag-host', style: 'margin-left:6px;', text: 'YOU' }) : null,
    ]);

    const tdRole = el('td', {}, [
      el('span', { class: `role-badge ${u.role === 'admin' ? 'admin' : 'player'}`, text: u.role.toUpperCase() }),
    ]);

    const tdGold = el('td', { text: formatNumber(u.gold) });
    const tdDiamonds = el('td', { text: formatNumber(u.diamonds) });
    const tdRubies = el('td', { text: formatNumber(u.rubies) });

    const hpBuff = u.bonusHp || u.adminBuffs?.bonusHp || 0;
    const dmgBuff = u.bonusDamage || u.adminBuffs?.bonusDamage || 0;
    const tdBuffs = el('td', {
      style: hpBuff || dmgBuff ? 'color: #72ffb8; font-weight: 700;' : 'color: var(--muted);',
      text: hpBuff || dmgBuff ? `+${hpBuff} HP / +${dmgBuff} DMG` : 'None',
    });

    const tdRank = el('td', { text: `${u.rankTier || 'Bronze'} (${u.rankPoints || 0} RP)` });

    const btnSelect = el('button', {
      class: 'btn btn-sm btn-ghost',
      type: 'button',
      text: 'Select',
    });
    btnSelect.addEventListener('click', () => {
      selectTargetUser(u.username);
    });

    const tdAction = el('td', {}, [btnSelect]);

    tr.appendChild(tdUser);
    tr.appendChild(tdRole);
    tr.appendChild(tdGold);
    tr.appendChild(tdDiamonds);
    tr.appendChild(tdRubies);
    tr.appendChild(tdBuffs);
    tr.appendChild(tdRank);
    tr.appendChild(tdAction);

    rosterTbody.appendChild(tr);
  }
}

function selectTargetUser(username) {
  if (inputCurrencyTarget) inputCurrencyTarget.value = username;
  if (selectCurrencyUser) selectCurrencyUser.value = username;
  if (inputPowerTarget) inputPowerTarget.value = username;
  if (selectPowerUser) selectPowerUser.value = username;

  toast(`Selected user "${username}" in GM Panel`, 'info', 2000);
  switchTab('currency');
}

async function handleExecuteCurrency(e) {
  e.preventDefault();
  const targetUsername = (inputCurrencyTarget?.value || '').trim();
  const currencyType = selectCurrencyType?.value || 'gold';
  const amount = Number.parseInt(inputCurrencyAmount?.value, 10);

  if (!targetUsername) {
    showBanner(bannerCurrencyStatus, 'Please enter or select a target username.', true);
    return;
  }
  if (!Number.isFinite(amount) || amount === 0) {
    showBanner(bannerCurrencyStatus, 'Please enter a non-zero integer amount.', true);
    return;
  }

  const btn = document.getElementById('btn-exec-currency');
  const restore = setBusy(btn, 'Processing...');
  showBanner(bannerCurrencyStatus, '');

  try {
    const res = await api.adminGiveCurrency({
      targetUsername,
      currencyType,
      amount,
    });

    showBanner(bannerCurrencyStatus, res.message || 'Currency successfully adjusted!');
    toast(res.message, 'success', 4000);

    // If target was current user, refresh store
    if (res.user && store.user && store.user.username.toLowerCase() === targetUsername.toLowerCase()) {
      store.setUser(res.user);
    }

    loadRoster().catch(console.error);
  } catch (err) {
    showBanner(bannerCurrencyStatus, err instanceof ApiError ? err.message : 'Action failed', true);
    toast(err.message || 'Failed to adjust currency', 'error');
  } finally {
    restore();
  }
}

async function handleExecutePower(e) {
  e.preventDefault();
  const targetUsername = (inputPowerTarget?.value || '').trim();
  const bonusHp = Math.max(0, Number.parseInt(inputPowerHp?.value, 10) || 0);
  const bonusDamage = Math.max(0, Number.parseInt(inputPowerDmg?.value, 10) || 0);

  if (!targetUsername) {
    showBanner(bannerPowerStatus, 'Please enter or select a target username.', true);
    return;
  }

  const btn = document.getElementById('btn-exec-power');
  const restore = setBusy(btn, 'Calibrating...');
  showBanner(bannerPowerStatus, '');

  try {
    const res = await api.adminSetStats({
      targetUsername,
      bonusHp,
      bonusDamage,
    });

    showBanner(bannerPowerStatus, res.message || 'Power buffs updated!');
    toast(res.message, 'success', 4000);

    if (res.user && store.user && store.user.username.toLowerCase() === targetUsername.toLowerCase()) {
      store.setUser(res.user);
    }

    loadRoster().catch(console.error);
  } catch (err) {
    showBanner(bannerPowerStatus, err instanceof ApiError ? err.message : 'Action failed', true);
    toast(err.message || 'Failed to apply power buffs', 'error');
  } finally {
    restore();
  }
}

export function updateAdminVisibility() {
  const isAdmin = store.user && store.user.role === 'admin';
  if (btnHeaderGM) {
    btnHeaderGM.classList.toggle('hidden', !isAdmin);
  }
  if (btnHubGM) {
    btnHubGM.classList.toggle('hidden', !isAdmin);
  }
  if (!isAdmin && modal && !modal.classList.contains('hidden')) {
    closeGmPanel();
  }
}

export function initAdminPanel() {
  modal = document.getElementById('gm-control-modal');
  btnHeaderGM = document.getElementById('admin-panel-btn');
  btnHubGM = document.getElementById('gm-hub-btn');
  btnCloseModal = document.getElementById('btn-close-gm-modal');

  tabButtons = Array.from(document.querySelectorAll('.gm-tab-btn'));
  tabPanels = {
    currency: document.getElementById('gm-panel-currency'),
    power: document.getElementById('gm-panel-power'),
    roster: document.getElementById('gm-panel-roster'),
  };

  formCurrency = document.getElementById('gm-currency-form');
  selectCurrencyUser = document.getElementById('gm-currency-user-select');
  inputCurrencyTarget = document.getElementById('gm-currency-target');
  selectCurrencyType = document.getElementById('gm-currency-type');
  inputCurrencyAmount = document.getElementById('gm-currency-amount');
  bannerCurrencyStatus = document.getElementById('gm-currency-status');

  formPower = document.getElementById('gm-power-form');
  selectPowerUser = document.getElementById('gm-power-user-select');
  inputPowerTarget = document.getElementById('gm-power-target');
  inputPowerHp = document.getElementById('gm-power-hp');
  inputPowerDmg = document.getElementById('gm-power-dmg');
  bannerPowerStatus = document.getElementById('gm-power-status');

  rosterTbody = document.getElementById('gm-roster-tbody');
  btnRefreshRoster = document.getElementById('btn-refresh-roster');
  userCountBadge = document.getElementById('gm-user-count');

  if (btnHeaderGM) btnHeaderGM.addEventListener('click', () => openGmPanel('currency'));
  if (btnHubGM) btnHubGM.addEventListener('click', () => openGmPanel('currency'));
  if (btnCloseModal) btnCloseModal.addEventListener('click', closeGmPanel);

  tabButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.gmTab;
      if (tab) switchTab(tab);
    });
  });

  // Select user dropdown synchronization
  if (selectCurrencyUser && inputCurrencyTarget) {
    selectCurrencyUser.addEventListener('change', () => {
      if (selectCurrencyUser.value) {
        inputCurrencyTarget.value = selectCurrencyUser.value;
      }
    });
  }

  if (selectPowerUser && inputPowerTarget) {
    selectPowerUser.addEventListener('change', () => {
      if (selectPowerUser.value) {
        inputPowerTarget.value = selectPowerUser.value;
      }
    });
  }

  // Quick Amount chips
  document.querySelectorAll('#gm-panel-currency .gm-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const amt = chip.dataset.amt;
      const curr = chip.dataset.curr;
      if (amt && inputCurrencyAmount) inputCurrencyAmount.value = amt;
      if (curr && selectCurrencyType) selectCurrencyType.value = curr;
    });
  });

  // Power Presets
  document.querySelectorAll('#gm-panel-power .gm-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      const preset = chip.dataset.preset;
      if (preset === 'hero') {
        if (inputPowerHp) inputPowerHp.value = 200;
        if (inputPowerDmg) inputPowerDmg.value = 50;
      } else if (preset === 'god') {
        if (inputPowerHp) inputPowerHp.value = 5000;
        if (inputPowerDmg) inputPowerDmg.value = 500;
      } else if (preset === 'reset') {
        if (inputPowerHp) inputPowerHp.value = 0;
        if (inputPowerDmg) inputPowerDmg.value = 0;
      }
    });
  });

  if (formCurrency) formCurrency.addEventListener('submit', handleExecuteCurrency);
  if (formPower) formPower.addEventListener('submit', handleExecutePower);
  if (btnRefreshRoster) btnRefreshRoster.addEventListener('click', () => loadRoster());

  // Listen to store changes to toggle GM button visibility
  store.subscribe(() => {
    updateAdminVisibility();
  });

  updateAdminVisibility();
}


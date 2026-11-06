// Anime skin shop: browse, filter, purchase and equip.
import { api, ApiError } from './api.js';
import { store } from './store.js';
import {
  el, toast, confirmDialog, skinAvatar, currencyIcon, formatNumber, setBusy,
  CURRENCY_META, RARITY_LABEL, renderSkillIconBadge, getSkinSignatureSkill,
} from './ui.js';

const filters = { currency: 'all', ownership: 'all' };
let grid;

function priceTag(skin) {
  if (skin.price.amount === 0) return el('span', { class: 'price free', text: 'Free' });
  return el('span', { class: 'price' }, [
    currencyIcon(skin.price.currency, 'sm'),
    el('span', { text: formatNumber(skin.price.amount) }),
  ]);
}

function matchesFilters(skin, user) {
  const isFrame = skin.itemType === 'frame';
  const owned = isFrame
    ? (user.ownedFrames && user.ownedFrames.includes(skin.slug))
    : (user.ownedSkins && user.ownedSkins.includes(skin.slug));
  if (filters.currency !== 'all' && skin.price.currency !== filters.currency) return false;
  if (filters.ownership === 'owned' && !owned) return false;
  if (filters.ownership === 'locked' && owned) return false;
  return true;
}

async function buy(skin, button) {
  const user = store.user;
  const balance = user.currencies[skin.price.currency] ?? 0;
  const label = CURRENCY_META[skin.price.currency].label;
  if (balance < skin.price.amount) {
    toast(`Not enough ${label}: need ${formatNumber(skin.price.amount)}, you have ${formatNumber(balance)}`, 'error');
    return;
  }

  const isFrame = skin.itemType === 'frame';
  const previewAvatar = isFrame
    ? skinAvatar(store.skinBySlug(user.equippedSkin), 'md', skin.slug)
    : skinAvatar(skin, 'md');

  const ok = await confirmDialog({
    title: `Confirm purchase: ${skin.name}`,
    body: el('div', { class: 'confirm-skin' }, [
      previewAvatar,
      el('div', {}, [
        el('p', { class: 'confirm-name', text: skin.name }),
        el('p', { class: 'muted', text: `Buy for ${formatNumber(skin.price.amount)} ${label}?` }),
        el('p', { class: 'muted small', text: `Balance after: ${formatNumber(balance - skin.price.amount)} ${label}` }),
      ]),
    ]),
    confirmText: 'Buy',
  });
  if (!ok) return;

  const restore = setBusy(button, 'Buying...');
  try {
    const data = await api.purchaseSkin(skin.slug);
    store.setUser(data.user);
    toast(data.message, 'success');
  } catch (err) {
    restore();
    toast(err instanceof ApiError ? err.message : 'Purchase failed', 'error');
  }
}

async function equip(skin, button) {
  const restore = setBusy(button, 'Equipping...');
  try {
    const isFrame = skin.itemType === 'frame';
    const data = isFrame ? await api.equipFrame(skin.slug) : await api.equipSkin(skin.slug);
    store.setUser(data.user);
    toast(`${skin.name} ${isFrame ? 'avatar frame' : 'skin'} equipped!`, 'success');
  } catch (err) {
    restore();
    toast(err instanceof ApiError ? err.message : 'Could not equip item', 'error');
  }
}

function skinCard(skin, user) {
  const isFrame = skin.itemType === 'frame';
  const owned = isFrame
    ? (user.ownedFrames && user.ownedFrames.includes(skin.slug))
    : (user.ownedSkins && user.ownedSkins.includes(skin.slug));
  const equipped = isFrame
    ? (user.equippedFrame === skin.slug)
    : (user.equippedSkin === skin.slug);
  const affordable = (user.currencies[skin.price.currency] ?? 0) >= skin.price.amount;

  let action;
  if (equipped) {
    action = el('button', { class: 'btn btn-equipped', type: 'button', disabled: true, text: 'Equipped' });
  } else if (owned) {
    action = el('button', { class: 'btn btn-secondary', type: 'button', text: isFrame ? 'Equip Frame' : 'Equip' });
    action.addEventListener('click', () => equip(skin, action));
  } else {
    action = el('button', {
      class: `btn ${affordable ? 'btn-primary' : 'btn-disabled'}`,
      type: 'button',
      text: affordable ? 'Buy' : 'Not enough',
      title: affordable ? '' : `Requires ${formatNumber(skin.price.amount)} ${CURRENCY_META[skin.price.currency].label}`,
    });
    action.addEventListener('click', () => buy(skin, action));
  }

  const stageNode = isFrame
    ? skinAvatar(store.skinBySlug(user.equippedSkin), 'lg', skin.slug)
    : skinAvatar(skin, 'lg');

  const sigSkill = !isFrame ? getSkinSignatureSkill(skin.slug) : null;
  const skillNode = sigSkill
    ? el('div', { class: 'skin-skill-box' }, [
        renderSkillIconBadge(sigSkill.iconKey, 48, sigSkill.name),
        el('div', { class: 'skin-skill-details' }, [
          el('span', { class: 'skin-skill-tag', text: 'SIGNATURE WEAPON' }),
          el('strong', { class: 'skin-skill-name', text: sigSkill.name }),
          el('p', { class: 'skin-skill-desc', text: sigSkill.description }),
        ]),
      ])
    : null;

  return el('article', { class: `skin-card rarity-${skin.rarity}${equipped ? ' is-equipped' : ''}${isFrame ? ' is-frame-card' : ''}` }, [
    el('div', { class: 'skin-card-top' }, [
      el('span', { class: `rarity-badge rarity-${skin.rarity}`, text: isFrame ? `FRAME • ${RARITY_LABEL[skin.rarity] || skin.rarity}` : (RARITY_LABEL[skin.rarity] || skin.rarity) }),
      owned ? el('span', { class: 'owned-badge', text: 'Owned' }) : null,
    ]),
    el('div', { class: 'skin-stage' }, stageNode),
    el('h3', { class: 'skin-name', text: skin.name }),
    el('p', { class: 'skin-inspired', text: `Inspired by: ${skin.inspiredBy}` }),
    skillNode,
    el('p', { class: 'skin-desc', text: skin.description }),
    el('div', { class: 'skin-card-footer' }, [owned ? el('span', { class: 'price owned', text: 'In collection' }) : priceTag(skin), action]),
  ]);
}

function render() {
  const { user, skins } = store;
  if (!grid || !user) return;
  const visible = skins.filter((s) => matchesFilters(s, user));
  grid.replaceChildren(
    ...(visible.length
      ? visible.map((s) => skinCard(s, user))
      : [el('p', { class: 'empty-state', text: skins.length ? 'No skins match these filters.' : 'Loading skins...' })])
  );
  const counter = document.getElementById('shop-owned-count');
  if (counter) counter.textContent = `${user.ownedSkins.length}/${skins.length} owned`;
}

export async function initShop() {
  grid = document.getElementById('skin-grid');

  document.querySelectorAll('[data-filter]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const { filter, value } = btn.dataset;
      filters[filter] = value;
      document
        .querySelectorAll(`[data-filter="${filter}"]`)
        .forEach((b) => b.classList.toggle('active', b === btn));
      render();
    });
  });

  store.subscribe(render);
  try {
    const { skins } = await api.listSkins();
    store.setSkins(skins);
  } catch (err) {
    grid.replaceChildren(el('p', { class: 'empty-state error', text: `Could not load the shop: ${err.message}` }));
  }
}


// Player Profile & Match History module
import { api } from './api.js';
import { store } from './store.js';
import { el, skinAvatar, rankBadge, formatNumber } from './ui.js';

function formatPlaytime(seconds = 0) {
  const total = Math.max(0, Number(seconds) || 0);
  const m = Math.floor(total / 60);
  const s = total % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return `${h}h ${remM}m`;
}

function formatDuration(seconds = 0) {
  const s = Math.max(0, Math.floor(Number(seconds) || 0));
  const mins = Math.floor(s / 60).toString().padStart(2, '0');
  const secs = (s % 60).toString().padStart(2, '0');
  return `${mins}:${secs}`;
}

function formatDate(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '-';
  return d.toLocaleDateString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function modeBadge(mode) {
  switch (mode) {
    case 'coop':
      return el('span', { class: 'mode-badge badge-coop', text: '🤝 CO-OP' });
    case 'ranked':
      return el('span', { class: 'mode-badge badge-ranked', text: '🏆 RANKED 3v3' });
    case 'solo':
    default:
      return el('span', { class: 'mode-badge badge-solo', text: '⚔️ SOLO' });
  }
}

function resultBadge(result) {
  switch (result) {
    case 'win':
      return el('span', { class: 'match-result-pill result-win', text: 'VICTORY' });
    case 'draw':
      return el('span', { class: 'match-result-pill result-draw', text: 'DRAW' });
    case 'loss':
    default:
      return el('span', { class: 'match-result-pill result-loss', text: 'DEFEAT' });
  }
}

export async function loadProfile() {
  const user = store.user;
  if (!user) return;

  // 1. Update Profile Card Overview
  const avatarBox = document.getElementById('profile-full-avatar');
  const userTitle = document.getElementById('profile-full-username');
  const userRole = document.getElementById('profile-full-role');
  const skinName = document.getElementById('profile-full-skin');
  const rankBadgeBox = document.getElementById('profile-full-rank-badge');

  const skin = store.skinBySlug(user.equippedSkin);
  if (avatarBox) {
    avatarBox.replaceChildren(skinAvatar(skin, 'lg', user.equippedFrame || 'default'));
  }
  if (userTitle) {
    userTitle.textContent = user.username;
  }
  if (userRole) {
    userRole.textContent = (user.role || 'player').toUpperCase();
    userRole.className = `user-role-tag role-${user.role || 'player'}`;
  }
  if (skinName) {
    skinName.textContent = skin ? skin.name : 'Wandering Survivor';
  }
  if (rankBadgeBox) {
    rankBadgeBox.replaceChildren(rankBadge(user.rankTier || 'Bronze', user.rankPoints || 0));
  }

  // 2. Fetch Match History and Aggregated Stats
  const statKills = document.getElementById('stat-total-kills');
  const statWinRate = document.getElementById('stat-win-rate');
  const statBosses = document.getElementById('stat-bosses-defeated');
  const statPlaytime = document.getElementById('stat-playtime');
  const statMatches = document.getElementById('stat-total-matches');
  const tbody = document.getElementById('match-history-tbody');

  try {
    const data = await api.getMatchHistory();
    const stats = data.stats || {};
    const history = data.history || [];

    if (statKills) statKills.textContent = formatNumber(stats.totalKills || 0);
    if (statWinRate) statWinRate.textContent = `${stats.winRate || 0}%`;
    if (statBosses) statBosses.textContent = formatNumber(stats.totalBossesDefeated || 0);
    if (statPlaytime) statPlaytime.textContent = formatPlaytime(stats.totalPlaytime || 0);
    if (statMatches) statMatches.textContent = formatNumber(stats.totalMatches || 0);

    // Render table rows
    if (tbody) {
      if (history.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center muted" style="padding: 2.5rem 1rem;">No battle records found yet. Enter the battlefield to begin your saga!</td></tr>`;
        return;
      }

      tbody.replaceChildren(
        ...history.map((m) => {
          const matchSkin = store.skinBySlug(m.skin);
          return el('tr', { class: `match-row result-${m.result || 'loss'}` }, [
            el('td', {}, [modeBadge(m.mode)]),
            el('td', {}, [resultBadge(m.result)]),
            el('td', {}, [
              el('div', { class: 'score-cell' }, [
                el('span', { class: 'score-val', text: `${formatNumber(m.score || 0)} pts` }),
                el('span', { class: 'kills-val muted small', text: `💀 ${m.kills || 0}` }),
              ]),
            ]),
            el('td', { class: 'mono font-bold', text: formatDuration(m.survivalTime) }),
            el('td', {}, [
              el('div', { class: 'skin-cell' }, [
                skinAvatar(matchSkin, 'xs'),
                el('span', { text: matchSkin ? matchSkin.name : (m.skin || 'Default') }),
              ]),
            ]),
            el('td', { class: 'reward-cell', text: m.rewardText || '-' }),
            el('td', { class: 'date-cell muted small', text: formatDate(m.date) }),
          ]);
        })
      );
    }
  } catch (err) {
    console.error('Failed to load profile history:', err);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center" style="color: #ff8899; padding: 1.5rem;">Could not load match history: ${err.message}</td></tr>`;
    }
  }
}

export function initProfile() {
  const refreshBtn = document.getElementById('btn-refresh-history');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      loadProfile().catch(console.error);
    });
  }
}


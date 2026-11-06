// Leaderboard & Survivor Hall of Fame module
import { api } from './api.js';
import { store } from './store.js';
import { el, skinAvatar, rankBadge, formatNumber } from './ui.js';

function renderPodium(top3) {
  const container = document.getElementById('leaderboard-podium');
  if (!container) return;

  if (!top3 || top3.length === 0) {
    container.innerHTML = '';
    return;
  }

  const [first, second, third] = top3;

  const podiumSlots = [];

  // Slot 2: Silver (Left)
  if (second) {
    const skin2 = store.skinBySlug(second.equippedSkin);
    podiumSlots.push(
      el('div', { class: 'podium-card podium-silver' }, [
        el('div', { class: 'podium-medal' }, [el('span', { text: '🥈 2nd Place' })]),
        skinAvatar(skin2, 'md', second.equippedFrame),
        el('h4', { class: 'podium-username', text: second.username }),
        rankBadge(second.rankTier, second.rankPoints),
        el('div', { class: 'podium-stat' }, [
          el('span', { text: `🔻 ${formatNumber(second.currencies?.rubies || 0)} Rubies` }),
          el('span', { class: 'muted small', text: `💀 ${formatNumber(second.totalKills || 0)} Kills` }),
        ]),
      ])
    );
  }

  // Slot 1: Gold Champion (Center)
  if (first) {
    const skin1 = store.skinBySlug(first.equippedSkin);
    podiumSlots.push(
      el('div', { class: 'podium-card podium-gold champion' }, [
        el('div', { class: 'podium-crown' }, [el('span', { text: '👑 CHAMPION' })]),
        skinAvatar(skin1, 'lg', first.equippedFrame),
        el('h3', { class: 'podium-username champion-name', text: first.username }),
        rankBadge(first.rankTier, first.rankPoints),
        el('div', { class: 'podium-stat' }, [
          el('span', { class: 'highlight-ruby', text: `🔻 ${formatNumber(first.currencies?.rubies || 0)} Rubies` }),
          el('span', { class: 'gold-stat', text: `🪙 ${formatNumber(first.currencies?.gold || 0)} Gold` }),
          el('span', { class: 'muted small', text: `💀 ${formatNumber(first.totalKills || 0)} Kills` }),
        ]),
      ])
    );
  }

  // Slot 3: Bronze (Right)
  if (third) {
    const skin3 = store.skinBySlug(third.equippedSkin);
    podiumSlots.push(
      el('div', { class: 'podium-card podium-bronze' }, [
        el('div', { class: 'podium-medal' }, [el('span', { text: '🥉 3rd Place' })]),
        skinAvatar(skin3, 'md', third.equippedFrame),
        el('h4', { class: 'podium-username', text: third.username }),
        rankBadge(third.rankTier, third.rankPoints),
        el('div', { class: 'podium-stat' }, [
          el('span', { text: `🔻 ${formatNumber(third.currencies?.rubies || 0)} Rubies` }),
          el('span', { class: 'muted small', text: `💀 ${formatNumber(third.totalKills || 0)} Kills` }),
        ]),
      ])
    );
  }

  container.replaceChildren(...podiumSlots);
}

export async function loadLeaderboard() {
  const tbody = document.getElementById('leaderboard-tbody');

  try {
    const data = await api.getLeaderboard();
    const list = data.leaderboard || [];

    // Render podium with top 3
    renderPodium(list.slice(0, 3));

    if (!tbody) return;

    if (list.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center muted" style="padding: 2.5rem 1rem;">No competitors on the leaderboard yet.</td></tr>`;
      return;
    }

    tbody.replaceChildren(
      ...list.map((u, idx) => {
        const isSelf = store.user && store.user.id === u.id;
        const skin = store.skinBySlug(u.equippedSkin);
        const winRate = u.totalMatches > 0 ? Math.round((u.totalWins / u.totalMatches) * 100) : 0;

        let rankLabel = `#${idx + 1}`;
        if (idx === 0) rankLabel = '🥇 1';
        else if (idx === 1) rankLabel = '🥈 2';
        else if (idx === 2) rankLabel = '🥉 3';

        return el('tr', { class: `lb-row${isSelf ? ' lb-self' : ''}` }, [
          el('td', { class: `lb-rank rank-${idx + 1}`, text: rankLabel }),
          el('td', {}, [
            el('div', { class: 'lb-player-cell' }, [
              skinAvatar(skin, 'xs', u.equippedFrame),
              el('span', { class: `lb-username${isSelf ? ' font-bold' : ''}`, text: u.username }),
              u.role === 'admin' ? el('span', { class: 'gm-tag-pill', text: 'GM' }) : null,
              isSelf ? el('span', { class: 'you-pill', text: 'YOU' }) : null,
            ].filter(Boolean)),
          ]),
          el('td', {}, [rankBadge(u.rankTier, u.rankPoints)]),
          el('td', { class: 'cur-ruby-text font-bold', text: `🔻 ${formatNumber(u.currencies?.rubies || 0)}` }),
          el('td', { class: 'cur-diamond-text', text: `💎 ${formatNumber(u.currencies?.diamonds || 0)}` }),
          el('td', { class: 'cur-gold-text', text: `🪙 ${formatNumber(u.currencies?.gold || 0)}` }),
          el('td', { class: 'mono font-bold', text: formatNumber(u.totalKills || 0) }),
          el('td', {}, [
            el('span', { class: 'win-rate-text', text: `${winRate}%` }),
            el('span', { class: 'muted small ml-1', text: `(${u.totalWins}/${u.totalMatches})` }),
          ]),
        ]);
      })
    );
  } catch (err) {
    console.error('Failed to load leaderboard:', err);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center" style="color: #ff8899; padding: 1.5rem;">Could not load leaderboard: ${err.message}</td></tr>`;
    }
  }
}

export function initLeaderboard() {
  const refreshBtn = document.getElementById('btn-refresh-leaderboard');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      loadLeaderboard().catch(console.error);
    });
  }
}


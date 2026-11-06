// Game page bootstrap (game.html).
import { api, session, ApiError } from './api.js';
import { store } from './store.js';
import {
  toast, skinAvatar, rankBadge, setBusy, RARITY_LABEL,
  renderSkillIconBadge, getSkinSignatureSkill, el,
} from './ui.js';
import { initCurrencyBar } from './currency.js';
import { initShop } from './shop.js';
import { initChat, disconnectChat } from './chat.js';
import { GameEngine } from './engine.js';
import { initMultiplayer } from './multiplayer.js';
import { initAdminPanel } from './admin.js';
import { initRouter } from './ui-router.js';
import { initProfile, loadProfile } from './profile.js';
import { initLeaderboard, loadLeaderboard } from './leaderboard.js';

let engine = null;

function formatTime(totalSecs) {
  const mins = Math.floor(totalSecs / 60);
  const secs = totalSecs % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function logout(message) {
  if (engine) engine.stop();
  disconnectChat();
  session.clear();
  if (message) sessionStorage.setItem('ls_flash', message);
  window.location.replace('/index.html');
}

function renderProfile({ user }) {
  if (!user) return;
  const isAdmin = user.role === 'admin';
  const gmTag = isAdmin ? ' 👑 [GM]' : '';
  document.getElementById('profile-name').textContent = user.username + gmTag;
  document.getElementById('header-username').textContent = user.username + (isAdmin ? ' (GM)' : '');

  const skin = store.skinBySlug(user.equippedSkin);
  const frame = user.equippedFrame || 'default';
  document.getElementById('profile-avatar').replaceChildren(skinAvatar(skin, 'xl', frame));
  document.getElementById('profile-skin').textContent = skin ? skin.name : user.equippedSkin;
  document.getElementById('profile-rarity').textContent = skin ? RARITY_LABEL[skin.rarity] : '';
  document.getElementById('profile-rarity').className = `rarity-badge rarity-${skin ? skin.rarity : 'common'}`;

  const rankBadgeNode = document.getElementById('profile-rank-badge');
  if (rankBadgeNode) {
    rankBadgeNode.replaceChildren(rankBadge(user.rankTier || 'Bronze', user.rankPoints || 0));
  }
  const headerRankNode = document.getElementById('header-rank-badge');
  if (headerRankNode) {
    headerRankNode.replaceChildren(rankBadge(user.rankTier || 'Bronze'));
  }

  // Update Left Sidebar user brief
  const sidebarUser = document.getElementById('sidebar-username');
  const sidebarRank = document.getElementById('sidebar-rank');
  if (sidebarUser) sidebarUser.textContent = user.username + (isAdmin ? ' [GM]' : '');
  if (sidebarRank) sidebarRank.textContent = `${user.rankTier || 'Bronze'} (${user.rankPoints || 0} RP)`;

  // Profile Signature Weapon display (48x48 icon)
  const profileSkillBox = document.getElementById('profile-skill-box');
  if (profileSkillBox) {
    const sigSkill = getSkinSignatureSkill(user.equippedSkin);
    profileSkillBox.replaceChildren(
      el('div', { class: 'profile-skill-card' }, [
        renderSkillIconBadge(sigSkill.iconKey, 48, sigSkill.name),
        el('div', { class: 'profile-skill-info' }, [
          el('span', { class: 'profile-skill-tag', text: 'SIGNATURE WEAPON' }),
          el('strong', { class: 'profile-skill-name', text: sigSkill.name }),
          el('span', { class: 'profile-skill-stats', text: sigSkill.statUpgrade }),
        ]),
      ])
    );
  }

  document.getElementById('profile-owned').textContent = String(user.ownedSkins.length);
  document.getElementById('profile-since').textContent = user.createdAt
    ? new Date(user.createdAt).toLocaleDateString()
    : '-';

  const dailyBtn = document.getElementById('daily-btn');
  const last = user.lastDailyClaim ? new Date(user.lastDailyClaim).getTime() : 0;
  const ready = Date.now() - last >= 24 * 60 * 60 * 1000;
  dailyBtn.classList.toggle('ready', ready);
  dailyBtn.title = ready ? 'Claim your daily reward!' : `Next reward: ${new Date(last + 86400000).toLocaleString()}`;
}

async function claimDaily(e) {
  const last = store.user?.lastDailyClaim ? new Date(store.user.lastDailyClaim).getTime() : 0;
  const ready = Date.now() - last >= 24 * 60 * 60 * 1000;
  if (!ready && last > 0) {
    const nextAt = new Date(last + 24 * 60 * 60 * 1000);
    toast(`Daily reward already claimed! Next reward at ${nextAt.toLocaleString()}`, 'info', 3500);
    return;
  }

  const restore = setBusy(e.currentTarget, 'Claiming...');
  try {
    const data = await api.claimDaily();
    store.setUser(data.user);
    toast(data.message, 'success', 4500);
  } catch (err) {
    if (err instanceof ApiError && err.details && err.details.nextClaimAt) {
      toast(`Already claimed. Come back at ${new Date(err.details.nextClaimAt).toLocaleString()}`, 'info', 4500);
    } else {
      toast(err.message || 'Could not claim reward', 'error');
    }
  } finally {
    restore();
  }
}

async function boot() {
  if (!session.token) return logout();

  window.addEventListener('ls:unauthorized', (e) => logout(e.detail));
  document.getElementById('logout-btn').addEventListener('click', () => logout('You have logged out.'));
  document.getElementById('daily-btn').addEventListener('click', claimDaily);

  try {
    const { user } = await api.me(); // validates the token and refreshes balances
    store.setUser(user);
  } catch (err) {
    if (!(err instanceof ApiError) || err.status !== 401) toast(err.message, 'error');
    return; // 401 already triggers logout via ls:unauthorized
  }

  store.subscribe(renderProfile);
  initCurrencyBar();
  await initShop(); // load skins first so chat & profile avatars have colours
  renderProfile(store);
  initChat();
  initBattleSystem();
  initAdminPanel();
  initRouter();
  initProfile();
  initLeaderboard();
  document.body.classList.remove('booting');
}

function initBattleSystem() {
  const enterBtn = document.getElementById('enter-battle-btn');
  const container = document.getElementById('game-container');
  const canvas = document.getElementById('gameCanvas');

  const hud = {
    hpBar: document.getElementById('hud-hp-bar'),
    hpText: document.getElementById('hud-hp-text'),
    expBar: document.getElementById('hud-exp-bar'),
    expText: document.getElementById('hud-exp-text'),
    levelBadge: document.getElementById('hud-level'),
    timer: document.getElementById('hud-timer'),
    kills: document.getElementById('hud-kills'),
    gold: document.getElementById('hud-gold'),
    levelUpBanner: document.getElementById('hud-levelup-banner'),
    levelUpText: document.getElementById('hud-levelup-text'),
    levelupOverlay: document.getElementById('game-levelup-overlay'),
    levelupCardsContainer: document.getElementById('levelup-cards-container'),
    coopQuest: document.getElementById('hud-coop-quest'),
    coopQuestText: document.getElementById('coop-quest-text'),
    coopQuestFill: document.getElementById('coop-quest-fill'),
    bossContainer: document.getElementById('hud-boss-bar-container'),
    bossHpText: document.getElementById('hud-boss-hp-text'),
    bossHpBar: document.getElementById('hud-boss-hp-bar'),
    roundBadge: document.getElementById('hud-round-badge'),
    roundQuota: document.getElementById('hud-round-quota'),
    bossAlert: document.getElementById('hud-boss-alert'),
    roundClear: document.getElementById('hud-round-clear'),
    roundClearSub: document.getElementById('hud-round-clear-sub'),
    bossIcon: document.getElementById('hud-boss-icon'),
    bossName: document.getElementById('hud-boss-name'),
    skillBar: document.getElementById('hud-skill-bar'),
    victoryOverlay: document.getElementById('game-victory-overlay'),
    victoryCountdown: document.getElementById('victory-countdown'),
    btnVictoryHub: document.getElementById('btn-victory-hub'),

    // Phase 4 Ranked 3v3 HUD & Results Overlay
    hudRankedScoreboard: document.getElementById('hud-ranked-scoreboard'),
    redScore: document.getElementById('hud-red-score'),
    blueScore: document.getElementById('hud-blue-score'),
    rankedTimer: document.getElementById('hud-ranked-timer'),
    hudEmojiBar: document.getElementById('hud-emoji-bar'),
    rankedResultsOverlay: document.getElementById('game-ranked-results-overlay'),
    resultsRedScore: document.getElementById('results-red-score'),
    resultsBlueScore: document.getElementById('results-blue-score'),
    rankedResultTitle: document.getElementById('ranked-result-title'),
    rankedResultSub: document.getElementById('ranked-result-sub'),
    rankedResultEmblem: document.getElementById('ranked-result-emblem'),
    resultsRpChange: document.getElementById('results-rp-change'),
    resultsTierBadge: document.getElementById('results-tier-badge'),
    resultsRubyChange: document.getElementById('results-ruby-change'),
    rankedCountdown: document.getElementById('ranked-countdown'),
    btnRankedHub: document.getElementById('btn-ranked-hub'),
  };

  const pauseOverlay = document.getElementById('game-pause-overlay');
  const pauseTime = document.getElementById('pause-time');
  const pauseKills = document.getElementById('pause-kills');
  const pauseGold = document.getElementById('pause-gold');
  const btnResume = document.getElementById('btn-resume-game');
  const btnQuit = document.getElementById('btn-quit-game');
  const hudPauseBtn = document.getElementById('hud-pause-btn');

  const overOverlay = document.getElementById('game-over-overlay');
  const overTime = document.getElementById('over-time');
  const overKills = document.getElementById('over-kills');
  const overLevel = document.getElementById('over-level');
  const overGold = document.getElementById('over-gold');
  const btnRestart = document.getElementById('btn-restart-game');
  const btnReturnHub = document.getElementById('btn-return-hub');

  engine = new GameEngine(canvas, hud, {
    onGameOver: (stats) => {
      overOverlay.classList.remove('hidden');
      overTime.textContent = formatTime(stats.survivalTime);
      overKills.textContent = stats.kills;
      overLevel.textContent = stats.level;
      overGold.textContent = `+${stats.gold} Gold`;

      // Record match session
      api.recordMatch({
        mode: stats.mode || 'solo',
        result: 'loss',
        score: (stats.kills || 0) * 10,
        kills: stats.kills || 0,
        survivalTime: stats.survivalTime || 0,
        skin: store.user?.equippedSkin || 'default',
        bossDefeated: false,
        rewardText: `+${stats.gold || 0} Gold`,
      }).then((res) => {
        if (res && res.user) store.setUser(res.user);
      }).catch(console.error);
    },
    onPauseStateChange: (isPaused, stats) => {
      if (isPaused) {
        pauseOverlay.classList.remove('hidden');
        pauseTime.textContent = formatTime(stats.survivalTime);
        pauseKills.textContent = stats.kills;
        pauseGold.textContent = stats.gold;
      } else {
        pauseOverlay.classList.add('hidden');
      }
    },
    onVictory: async (reward) => {
      const stats = engine.getStats();
      engine.stop();
      container.classList.add('hidden');
      if (hud.victoryOverlay) hud.victoryOverlay.classList.add('hidden');

      // Record co-op boss victory
      api.recordMatch({
        mode: 'coop',
        result: 'win',
        score: (stats.kills || 0) * 10 + 1000,
        kills: stats.kills || 0,
        survivalTime: stats.survivalTime || 0,
        skin: store.user?.equippedSkin || 'default',
        bossDefeated: true,
        rewardText: `+${reward?.diamonds || 15} Diamonds`,
      }).then((res) => {
        if (res && res.user) store.setUser(res.user);
      }).catch(console.error);

      try {
        const { user } = await api.me();
        store.setUser(user);
      } catch (e) {
        console.error('Failed to refresh user after victory:', e);
      }
      toast(`👑 VICTORY! Slayed the Lich King & earned +${reward?.diamonds || 15} Diamonds!`, 'success', 5000);
    },
    onRankedEnded: async (matchResult) => {
      const stats = engine.getStats();
      engine.stop();
      container.classList.add('hidden');
      if (hud.rankedResultsOverlay) hud.rankedResultsOverlay.classList.add('hidden');

      const myTeam = engine.myTeam;
      const isWinner = matchResult.winner !== 'tie' && matchResult.winner === myTeam;
      const isTie = matchResult.winner === 'tie';
      const result = isWinner ? 'win' : (isTie ? 'draw' : 'loss');
      const myScore = myTeam === 'red' ? matchResult.redScore : matchResult.blueScore;
      const rewardText = isWinner ? '+25 RP, +5 Rubies' : (isTie ? '+5 RP, +1 Ruby' : '-15 RP');

      // Record ranked match
      api.recordMatch({
        mode: 'ranked',
        result,
        score: myScore || 0,
        kills: stats.kills || 0,
        survivalTime: 180,
        skin: store.user?.equippedSkin || 'default',
        bossDefeated: false,
        rewardText,
      }).then((res) => {
        if (res && res.user) store.setUser(res.user);
      }).catch(console.error);

      try {
        const { user } = await api.me();
        store.setUser(user);
      } catch (e) {
        console.error('Failed to refresh user after ranked match:', e);
      }

      if (isWinner) {
        toast(`🏆 3v3 VICTORY! +25 RP & +5 Rubies added to your balance!`, 'success', 5000);
      } else if (isTie) {
        toast(`⚖️ 3v3 MATCH DRAW! +5 RP & +1 Ruby earned!`, 'info', 4000);
      } else {
        toast(`💀 3v3 DEFEAT: -15 RP. Train hard for the next battle!`, 'error', 4000);
      }
    },
  });

  initMultiplayer({
    onStartDungeon: ({ room, isHost, socket }) => {
      const skin = store.skinBySlug(store.user.equippedSkin);
      pauseOverlay.classList.add('hidden');
      overOverlay.classList.add('hidden');
      if (hud.victoryOverlay) hud.victoryOverlay.classList.add('hidden');
      if (hud.rankedResultsOverlay) hud.rankedResultsOverlay.classList.add('hidden');
      container.classList.remove('hidden');

      engine.start(skin, {
        mode: 'coop',
        isHost,
        socket,
        room,
      });

      toast(`🤝 Entered Co-op Dungeon (${room.code})! Slay 100 monsters to summon Boss!`, 'info', 3500);
    },
    onStartRankedMatch: ({ matchData, socket }) => {
      const skin = store.skinBySlug(store.user.equippedSkin);
      pauseOverlay.classList.add('hidden');
      overOverlay.classList.add('hidden');
      if (hud.victoryOverlay) hud.victoryOverlay.classList.add('hidden');
      if (hud.rankedResultsOverlay) hud.rankedResultsOverlay.classList.add('hidden');
      container.classList.remove('hidden');

      engine.start(skin, {
        mode: 'ranked',
        yourTeam: matchData.yourTeam,
        redTeam: matchData.redTeam,
        blueTeam: matchData.blueTeam,
        duration: matchData.duration,
        socket,
        room: { roomId: matchData.roomId },
      });

      const teamName = matchData.yourTeam === 'red' ? '🔴 TEAM RED' : '🔵 TEAM BLUE';
      toast(`🏆 3v3 RANKED MATCH START! You are assigned to ${teamName}!`, 'success', 4500);
    },
  });

  // Interactive Emoji Quick Bar buttons
  const emojiButtons = document.querySelectorAll('.emoji-quick-btn');
  emojiButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const emoji = btn.dataset.emoji;
      if (emoji && engine) {
        engine.sendEmoji(emoji);
      }
    });
  });

  const exitBattleAndSaveGold = async (goldAmount, returnButton) => {
    let restore = null;
    if (returnButton) restore = setBusy(returnButton, 'Saving...');
    const stats = engine.getStats();
    engine.stop();
    container.classList.add('hidden');
    pauseOverlay.classList.add('hidden');
    overOverlay.classList.add('hidden');

    if (stats.survivalTime > 5) {
      api.recordMatch({
        mode: stats.mode || 'solo',
        result: 'loss',
        score: (stats.kills || 0) * 10,
        kills: stats.kills || 0,
        survivalTime: stats.survivalTime || 0,
        skin: store.user?.equippedSkin || 'default',
        bossDefeated: false,
        rewardText: goldAmount > 0 ? `+${goldAmount} Gold` : 'Retreated',
      }).then((res) => {
        if (res && res.user) store.setUser(res.user);
      }).catch(console.error);
    }

    if (goldAmount > 0) {
      try {
        const data = await api.addGold(goldAmount);
        store.setUser(data.user);
        toast(`🏆 Battle Resolved: +${goldAmount} Gold banked to your account!`, 'success', 4000);
      } catch (err) {
        toast(err.message || 'Could not save gold', 'error');
      } finally {
        if (restore) restore();
      }
    } else {
      if (restore) restore();
      toast('Returned to Hub.', 'info', 2500);
    }
  };

  // ── Native 60 FPS HTML5 Canvas Engine Launch (Solo Survival) ──
  const pygameContainer = document.getElementById('pygame-container');
  const pygameFrame = document.getElementById('pygameFrame');
  const btnPygameReturn = document.getElementById('btn-pygame-return-hub');

  const launchNativeGame = (mode = 'solo') => {
    const skin = store.skinBySlug(store.user?.equippedSkin || 'default');
    const bridgeUser = {
      username: store.user?.username || 'Survivor',
      equippedSkin: store.user?.equippedSkin || 'default',
      gold: store.user?.gold || 0,
      diamonds: store.user?.diamonds || 0,
      rubies: store.user?.rubies || 0,
      adminBuffs: store.user?.adminBuffs || {},
    };
    try {
      localStorage.setItem('ls_bridge_user', JSON.stringify(bridgeUser));
    } catch (_) {}

    pauseOverlay.classList.add('hidden');
    overOverlay.classList.add('hidden');
    if (hud.victoryOverlay) hud.victoryOverlay.classList.add('hidden');
    if (hud.rankedResultsOverlay) hud.rankedResultsOverlay.classList.add('hidden');
    if (pygameContainer) {
      pygameContainer.classList.add('hidden');
      if (pygameFrame) pygameFrame.src = 'about:blank'; // Retired /pygame/index.html iframe in favor of native 60 FPS Canvas
    }
    container.classList.remove('hidden');

    engine.start(skin, { mode });
    toast(`⚔️ Tiến vào Chiến Trường Sinh Tồn với ${skin ? skin.name : 'Chiến Binh Độc Hành'}!`, 'success', 3200);
  };

  enterBtn.addEventListener('click', () => launchNativeGame('solo'));

  if (btnPygameReturn) {
    btnPygameReturn.addEventListener('click', () => {
      if (pygameContainer) pygameContainer.classList.add('hidden');
      if (pygameFrame) pygameFrame.src = 'about:blank';
      toast('Returned to Web Hub.', 'info', 2000);
    });
  }

  // Two-way Bridge: Listen for Real-Time Messages from Python Pygame iframe
  window.addEventListener('message', async (event) => {
    let msg = event.data;
    if (typeof msg === 'string') {
      try { msg = JSON.parse(msg); } catch (_) { return; }
    }
    if (!msg || typeof msg !== 'object') return;

    // Real-time Gold pickup from Python
    if (msg.type === 'LS_GOLD_UPDATE' && Number.isFinite(msg.goldDelta) && msg.goldDelta > 0) {
      try {
        const res = await api.addGold(msg.goldDelta);
        if (res && res.user) {
          store.setUser(res.user);
        }
      } catch (err) {
        console.warn('[Pygame Bridge] Gold update failed:', err);
      }
    }

    // Match End / Game Over from Python
    if (msg.type === 'LS_MATCH_END') {
      try {
        if (msg.goldEarned > 0) {
          const res = await api.addGold(msg.goldEarned);
          if (res && res.user) {
            store.setUser(res.user);
          }
        }
        await api.recordMatch({
          mode: 'solo',
          result: msg.result || 'defeat',
          kills: msg.kills || 0,
          timeSurvived: msg.timeSurvived || 0,
          goldEarned: msg.goldEarned || 0,
          rpChange: 0,
        });
        toast(`🏆 Pygame Session Saved: +${msg.goldEarned || 0} Gold & Match History recorded!`, 'success', 4000);
      } catch (err) {
        console.warn('[Pygame Bridge] Match record failed:', err);
      }
    }
  });

  hudPauseBtn.addEventListener('click', () => engine.togglePause());
  btnResume.addEventListener('click', () => engine.resume());

  btnQuit.addEventListener('click', () => {
    const stats = engine.getStats();
    exitBattleAndSaveGold(stats.gold, btnQuit);
  });

  btnReturnHub.addEventListener('click', () => {
    const stats = engine.getStats();
    exitBattleAndSaveGold(stats.gold, btnReturnHub);
  });

  btnRestart.addEventListener('click', () => {
    const stats = engine.getStats();
    if (stats.gold > 0) {
      api.addGold(stats.gold).then((data) => store.setUser(data.user)).catch(console.error);
      toast(`+${stats.gold} Gold banked!`, 'success');
    }
    overOverlay.classList.add('hidden');
    const skin = store.skinBySlug(store.user.equippedSkin);
    engine.start(skin, { mode: stats.mode || 'solo' });
  });
}

boot();


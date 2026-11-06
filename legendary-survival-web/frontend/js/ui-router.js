// Single Page Application (SPA) Tab Router for Legendary Survival Hub
import { loadProfile } from './profile.js';
import { loadLeaderboard } from './leaderboard.js';

let currentTab = 'home';
let tabButtons = [];
let tabViews = {};

export function getCurrentTab() {
  return currentTab;
}

export function switchTab(tabId) {
  if (!tabViews[tabId]) return;

  currentTab = tabId;

  // Update nav buttons
  tabButtons.forEach((btn) => {
    const isTarget = btn.dataset.tab === tabId;
    btn.classList.toggle('active', isTarget);
    btn.setAttribute('aria-selected', isTarget ? 'true' : 'false');
  });

  // Toggle tab view visibility
  Object.keys(tabViews).forEach((key) => {
    const view = tabViews[key];
    if (key === tabId) {
      view.classList.remove('hidden');
      view.classList.add('active');
    } else {
      view.classList.add('hidden');
      view.classList.remove('active');
    }
  });

  // Trigger tab data refreshes
  if (tabId === 'profile') {
    loadProfile().catch(console.error);
  } else if (tabId === 'leaderboard') {
    loadLeaderboard().catch(console.error);
  }

  // Scroll to top of main content
  const main = document.querySelector('.hub-main-content');
  if (main) main.scrollTop = 0;
}

export function initRouter() {
  tabButtons = Array.from(document.querySelectorAll('.nav-tab-btn[data-tab]'));

  const views = document.querySelectorAll('.tab-view');
  views.forEach((view) => {
    const id = view.id.replace(/^tab-/, '');
    tabViews[id] = view;
  });

  tabButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;
      if (target) switchTab(target);
    });
  });

  // Switch tab triggers anywhere on the page (e.g., [data-switch-tab="shop"])
  document.addEventListener('click', (e) => {
    const switchTarget = e.target.closest('[data-switch-tab]');
    if (switchTarget) {
      const tabId = switchTarget.dataset.switchTab;
      if (tabId) switchTab(tabId);
    }
  });

  // Default to home tab
  switchTab('home');
}


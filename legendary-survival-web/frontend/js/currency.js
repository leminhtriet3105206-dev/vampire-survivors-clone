// Currency HUD: Gold / Diamonds / Rubies with animated count changes.
import { store } from './store.js';
import { formatNumber } from './ui.js';

const CURRENCIES = ['gold', 'diamonds', 'rubies'];
const shown = { gold: null, diamonds: null, rubies: null };

function animateValue(node, from, to, duration = 600) {
  if (from === null || from === to) {
    node.textContent = formatNumber(to);
    return;
  }
  const start = performance.now();
  const pill = node.closest('.currency');
  pill?.classList.remove('gain', 'spend');
  void pill?.offsetWidth; // restart CSS animation
  pill?.classList.add(to > from ? 'gain' : 'spend');

  const step = (now) => {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    node.textContent = formatNumber(Math.round(from + (to - from) * eased));
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

export function initCurrencyBar() {
  const render = ({ user }) => {
    if (!user) return;
    for (const cur of CURRENCIES) {
      const node = document.querySelector(`[data-currency="${cur}"]`);
      if (!node) continue;
      const value = user.currencies?.[cur] ?? 0;
      animateValue(node, shown[cur], value);
      shown[cur] = value;
    }
  };
  store.subscribe(render);
  render(store);
}


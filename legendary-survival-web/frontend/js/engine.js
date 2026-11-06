'use strict';

/**
 * ============================================================================
 * LEGENDARY SURVIVAL - AAA HTML5 CANVAS 2D TOP-DOWN ENGINE (1:1 PORT FROM PYGAME)
 * ============================================================================
 * Architecture Highlights:
 * Eliminates ctx.shadowBlur in game loop (STRICT BAN on Gaussian blur in game loop)
 *  2. Offscreen Sprite & Glow Pre-Renderer (SpriteCache & GlowCache)
 *  3. Spatial Hash Grid for O(1) collision queries (enemies vs projectiles/slashes)
 *  4. Swap-and-Pop array element removals (arr[i] = arr[arr.length - 1]; arr.pop())
 *  5. Exact Round/Wave finite monster quota & Boss progression system
 *  6. 4 Character Classes, Starter Signature Skills, Secondary Boons & 4 Mythic Fusions
 *  7. Procedural Dark Fantasy Enemies (Skeleton, Bat, Wraith, Dark Knight) & Bosses
 *  8. Battlefield Drops: Health Potion (+HP ring) & Global EXP Magnet (All-map vacuum)
 * ============================================================================
 */

import { SKILL_META, getSkillIconSvg, getSkinSignatureSkill, el } from './ui.js';

/* ── Vector Math & Utility Helpers ────────────────────────────────────────── */
export function dist(x1, y1, x2, y2) {
  return Math.hypot(x2 - x1, y2 - y1);
}

export function clamp(val, min, max) {
  return Math.max(min, Math.min(max, val));
}

export function randRange(min, max) {
  return min + Math.random() * (max - min);
}

export function lerp(a, b, t) {
  return a + (b - a) * t;
}

export function angleTo(x1, y1, x2, y2) {
  return Math.atan2(y2 - y1, x2 - x1);
}

/* ── World & Grid Constants ──────────────────────────────────────────────── */
const WORLD_W = 4000;
const WORLD_H = 4000;
const TILE_SIZE = 64;
const CHUNK_SIZE = 256;

/* ── Pre-Rendered SpriteCache & Zero-Lag Glow Architecture ────────────────── */
export const glowSpriteCache = new Map();
export const preRenderedCoinFrames = [];
export const preRenderedBatFrames = [];
const tileChunkCache = new Map();
const dropShadowCache = new Map();
let preRenderedGemSprites = null;
let preRenderedItemSprites = null;

/**
 * Retrieves or builds an offscreen radial glow canvas.
 * Called once per color/size; never creates gradients during 60 FPS loop!
 */
export function getGlowSprite(color, radius) {
  const r = Math.max(4, Math.round(radius));
  const key = `${color}_${r}`;
  let sprite = glowSpriteCache.get(key);
  if (sprite) return sprite;

  const size = r * 2;
  const offscreen = typeof document !== 'undefined' ? document.createElement('canvas') : null;
  if (!offscreen) return null;
  offscreen.width = size;
  offscreen.height = size;
  const octx = offscreen.getContext('2d');

  const grad = octx.createRadialGradient(r, r, 0, r, r, r);
  grad.addColorStop(0, color);
  grad.addColorStop(0.35, color);
  grad.addColorStop(1, 'rgba(0,0,0,0)');

  octx.fillStyle = grad;
  octx.beginPath();
  octx.arc(r, r, r, 0, Math.PI * 2);
  octx.fill();

  glowSpriteCache.set(key, offscreen);
  return offscreen;
}

export function drawAdditiveGlow(ctx, x, y, radius, color, intensity = 0.65) {
  if (radius <= 0) return;
  const sprite = getGlowSprite(color, radius);
  if (!sprite) return;
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  ctx.globalAlpha = Math.min(1, Math.max(0, intensity));
  ctx.drawImage(sprite, x - radius, y - radius);
  ctx.restore();
}

/**
 * Hexagram magic seal helper
 */
export function drawMagicCircle(ctx, x, y, radius, color = '#ffd700') {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.stroke();

  const r2 = radius * 0.85;
  ctx.beginPath();
  for (let i = 0; i < 3; i++) {
    const a = (Math.PI * 2 / 3) * i - Math.PI / 2;
    const px = x + Math.cos(a) * r2;
    const py = y + Math.sin(a) * r2;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
  ctx.stroke();

  ctx.beginPath();
  for (let i = 0; i < 3; i++) {
    const a = (Math.PI * 2 / 3) * i + Math.PI / 2;
    const px = x + Math.cos(a) * r2;
    const py = y + Math.sin(a) * r2;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
  ctx.stroke();
  ctx.restore();
}

/**
 * Midpoint displacement lightning
 */
export function drawJaggedLightningArc(ctx, x1, y1, x2, y2, color = '#ffd34d') {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 2.2;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  const midX = (x1 + x2) / 2 + randRange(-12, 12);
  const midY = (y1 + y2) / 2 + randRange(-12, 12);
  ctx.lineTo(midX, midY);
  ctx.lineTo(x2, y2);
  ctx.stroke();
  ctx.restore();
}

/**
 * Pre-rendered drop shadow sprite beneath characters, enemies, and bosses.
 */
function getDropShadowSprite(width, height) {
  const w = Math.max(8, Math.round(width));
  const h = Math.max(4, Math.round(height));
  const key = `${w}_${h}`;
  let s = dropShadowCache.get(key);
  if (s) return s;

  const off = document.createElement('canvas');
  off.width = w;
  off.height = h;
  const octx = off.getContext('2d');
  octx.fillStyle = 'rgba(0, 0, 0, 0.45)';
  octx.beginPath();
  octx.ellipse(w / 2, h / 2, w / 2 - 1, h / 2 - 1, 0, 0, Math.PI * 2);
  octx.fill();

  dropShadowCache.set(key, off);
  return off;
}

/**
 * Pre-rendered 256x256 Dark Arcane Cobblestone & Rune ground textures (1:1 from main.py).
 */
function getArcaneTileChunk(biomeId = 0) {
  const b = biomeId % 3;
  if (tileChunkCache.has(b)) return tileChunkCache.get(b);

  const off = document.createElement('canvas');
  off.width = CHUNK_SIZE;
  off.height = CHUNK_SIZE;
  const ctx = off.getContext('2d');

  if (b === 0) {
    // Biome 0: Cursed Graveyard (Nghĩa Địa Cổ Đại) - Dark slate cobblestones & moss
    ctx.fillStyle = '#0c0e12';
    ctx.fillRect(0, 0, CHUNK_SIZE, CHUNK_SIZE);

    for (let ty = 0; ty < CHUNK_SIZE; ty += TILE_SIZE) {
      for (let tx = 0; tx < CHUNK_SIZE; tx += TILE_SIZE) {
        ctx.fillStyle = '#14181f';
        ctx.fillRect(tx + 1, ty + 1, TILE_SIZE - 2, TILE_SIZE - 2);
        ctx.strokeStyle = '#1d222b';
        ctx.lineWidth = 1;
        ctx.strokeRect(tx, ty, TILE_SIZE, TILE_SIZE);

        // Sub cobblestones
        const subW = TILE_SIZE / 2 - 4;
        const subH = TILE_SIZE / 2 - 4;
        for (let sy = 0; sy < 2; sy++) {
          for (let sx = 0; sx < 2; sx++) {
            const stx = tx + 3 + sx * (TILE_SIZE / 2);
            const sty = ty + 3 + sy * (TILE_SIZE / 2);
            ctx.fillStyle = '#171b22';
            ctx.fillRect(stx, sty, subW, subH);
            ctx.strokeStyle = '#0e1015';
            ctx.strokeRect(stx, sty, subW, subH);
          }
        }
        // Moss spot
        ctx.fillStyle = 'rgba(28, 54, 34, 0.65)';
        ctx.beginPath();
        ctx.arc(tx + 22, ty + 22, 5, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  } else if (b === 1) {
    // Biome 1: Blood Moon Dungeon (Hầm Ngục Huyết Nguyệt) - Obsidian tiles & crimson runes
    ctx.fillStyle = '#0e070a';
    ctx.fillRect(0, 0, CHUNK_SIZE, CHUNK_SIZE);
    for (let ty = 0; ty < CHUNK_SIZE; ty += TILE_SIZE) {
      for (let tx = 0; tx < CHUNK_SIZE; tx += TILE_SIZE) {
        ctx.fillStyle = '#180a0f';
        ctx.fillRect(tx + 2, ty + 2, TILE_SIZE - 4, TILE_SIZE - 4);
        ctx.strokeStyle = '#2d0e18';
        ctx.lineWidth = 1.2;
        ctx.strokeRect(tx, ty, TILE_SIZE, TILE_SIZE);
        ctx.strokeStyle = 'rgba(235, 45, 65, 0.25)';
        ctx.beginPath();
        ctx.moveTo(tx + 10, ty + 32);
        ctx.lineTo(tx + 54, ty + 32);
        ctx.stroke();
      }
    }
  } else {
    // Biome 2: Corrupted Abyss Forest (Rừng Hư Không) - Purple arcane turf & crystal veins
    ctx.fillStyle = '#0a0814';
    ctx.fillRect(0, 0, CHUNK_SIZE, CHUNK_SIZE);
    for (let ty = 0; ty < CHUNK_SIZE; ty += TILE_SIZE) {
      for (let tx = 0; tx < CHUNK_SIZE; tx += TILE_SIZE) {
        ctx.fillStyle = '#130f24';
        ctx.fillRect(tx + 1, ty + 1, TILE_SIZE - 2, TILE_SIZE - 2);
        ctx.strokeStyle = '#1e1838';
        ctx.lineWidth = 1;
        ctx.strokeRect(tx, ty, TILE_SIZE, TILE_SIZE);
        ctx.strokeStyle = 'rgba(80, 230, 255, 0.28)';
        ctx.beginPath();
        ctx.moveTo(tx + 16, ty + 16);
        ctx.lineTo(tx + 48, ty + 48);
        ctx.stroke();
      }
    }
  }

  tileChunkCache.set(b, off);
  return off;
}

export function getExpGemSprite(color = '#32ffa0') {
  if (preRenderedGemSprites && preRenderedGemSprites.has(color)) {
    return preRenderedGemSprites.get(color);
  }
  return preRenderedGemSprites ? preRenderedGemSprites.get(1) : null;
}

/**
 * Initializes pre-rendered offscreen sprites for EXP Gems, Gold Coins, Potion, and Magnet.
 */
function initSpriteCache() {
  if (preRenderedGemSprites) return;

  // 1. EXP Gems: Tier 1 (Green 5XP), Tier 2 (Blue 15XP), Tier 3 (Purple 40XP), Tier 4 (Gold 100XP)
  preRenderedGemSprites = new Map();
  const gemTiers = [
    { tier: 1, color: '#32ffa0', border: '#00cc66' },
    { tier: 2, color: '#4fd8ff', border: '#0099ff' },
    { tier: 3, color: '#d500f9', border: '#aa00ff' },
    { tier: 4, color: '#ffd700', border: '#ff9100' },
  ];

  for (const g of gemTiers) {
    const s = 32;
    const off = document.createElement('canvas');
    off.width = s;
    off.height = s;
    const octx = off.getContext('2d');
    const h = s / 2;

    octx.fillStyle = g.color;
    octx.beginPath();
    octx.moveTo(h, h - 8);
    octx.lineTo(h + 7, h);
    octx.lineTo(h, h + 8);
    octx.lineTo(h - 7, h);
    octx.closePath();
    octx.fill();

    octx.strokeStyle = g.border;
    octx.lineWidth = 1.2;
    octx.stroke();

    octx.fillStyle = '#ffffff';
    octx.beginPath();
    octx.arc(h, h, 2, 0, Math.PI * 2);
    octx.fill();

    preRenderedGemSprites.set(g.tier, off);
    preRenderedGemSprites.set(g.color, off);
  }

  // 2. Gold Coins: 8 rotating 3D frames
  preRenderedCoinFrames.length = 0;
  for (let frame = 0; frame < 8; frame++) {
    const s = 28;
    const off = document.createElement('canvas');
    off.width = s;
    off.height = s;
    const octx = off.getContext('2d');
    const h = s / 2;
    const cosVal = Math.max(0.18, Math.abs(Math.cos((frame / 8) * Math.PI * 2)));

    octx.fillStyle = '#ffd700';
    octx.beginPath();
    octx.ellipse(h, h, 8 * cosVal, 8, 0, 0, Math.PI * 2);
    octx.fill();

    octx.strokeStyle = '#ff9900';
    octx.lineWidth = 1.2;
    octx.stroke();

    octx.fillStyle = '#fff48d';
    octx.beginPath();
    octx.ellipse(h, h, 4 * cosVal, 4, 0, 0, Math.PI * 2);
    octx.fill();

    preRenderedCoinFrames.push(off);
  }

  // 3. Pre-rendered bat flap frames
  preRenderedBatFrames.length = 0;
  for (let f = 0; f < 6; f++) {
    const s = 36;
    const off = document.createElement('canvas');
    off.width = s;
    off.height = s;
    const octx = off.getContext('2d');
    const h = s / 2;
    const flap = Math.sin((f / 6) * Math.PI * 2) * 8;

    octx.fillStyle = '#4a0e4e';
    octx.beginPath();
    octx.moveTo(h, h);
    octx.lineTo(h - 14, h - 5 - flap);
    octx.lineTo(h - 4, h + 5 - flap / 2);
    octx.closePath();
    octx.fill();

    octx.beginPath();
    octx.moveTo(h, h);
    octx.lineTo(h + 14, h - 5 - flap);
    octx.lineTo(h + 4, h + 5 - flap / 2);
    octx.closePath();
    octx.fill();

    octx.fillStyle = '#2d0036';
    octx.beginPath();
    octx.arc(h, h, 8, 0, Math.PI * 2);
    octx.fill();

    preRenderedBatFrames.push(off);
  }

  // 4. Battlefield Item Drops: Health Potion & EXP Magnet
  preRenderedItemSprites = {};

  // Bình Máu (Health Potion)
  {
    const s = 44;
    const off = document.createElement('canvas');
    off.width = s;
    off.height = s;
    const octx = off.getContext('2d');
    const h = s / 2;

    octx.fillStyle = '#ff1744';
    octx.beginPath();
    octx.arc(h, h + 2, 10, 0, Math.PI * 2);
    octx.fill();

    octx.strokeStyle = 'rgba(255, 255, 255, 0.7)';
    octx.lineWidth = 1.5;
    octx.stroke();

    octx.fillStyle = 'rgba(255, 255, 255, 0.85)';
    octx.beginPath();
    octx.arc(h - 3, h - 1, 3, 0, Math.PI * 2);
    octx.fill();

    octx.fillStyle = '#cfd8dc';
    octx.fillRect(h - 3, h - 10, 6, 4);
    octx.fillStyle = '#a16207';
    octx.fillRect(h - 2, h - 14, 4, 4);

    octx.fillStyle = '#00e676';
    octx.fillRect(h - 1, h, 2, 6);
    octx.fillRect(h - 3, h + 2, 6, 2);

    preRenderedItemSprites.potion = off;
  }

  // Nam Châm Từ Trường (EXP Magnet)
  {
    const s = 44;
    const off = document.createElement('canvas');
    off.width = s;
    off.height = s;
    const octx = off.getContext('2d');
    const h = s / 2;

    octx.strokeStyle = '#94a3b8';
    octx.lineWidth = 4;
    octx.beginPath();
    octx.arc(h, h + 4, 10, 0, Math.PI, false);
    octx.stroke();

    octx.fillStyle = '#00e5ff';
    octx.fillRect(h - 12, h - 6, 5, 10);
    octx.fillStyle = '#ff1744';
    octx.fillRect(h + 7, h - 6, 5, 10);

    octx.fillStyle = '#f8fafc';
    octx.fillRect(h - 12, h - 8, 5, 3);
    octx.fillRect(h + 7, h - 8, 5, 3);

    octx.strokeStyle = '#ffffff';
    octx.lineWidth = 1.8;
    octx.beginPath();
    octx.moveTo(h - 8, h - 7);
    octx.lineTo(h, h - 11);
    octx.lineTo(h + 8, h - 7);
    octx.stroke();

    preRenderedItemSprites.magnet = off;
  }
}

/* ── Compatibility Weapon Classes ────────────────────────────────────────── */
export class BloodSlashWeapon {
  constructor(player) {
    this.player = player;
    this.name = 'Blood Moon Slash';
    this.level = 1;
    this.range = 195;
    this.sweep = 0.68;
    this.cooldown = 0;
  }
  draw(ctx, x, y, angle) {
    const s = 1.0;
    const sweep = 0.68;
    const teeth = Math.sin(s * 2.7);
  }
}

export class VoidSingularityWeapon {
  constructor(player) {
    this.player = player;
    this.name = 'Void Singularity';
    this.level = 1;
    this.pullStr = 2.4;
  }
}

export class LightningStaffWeapon {
  constructor(player) {
    this.player = player;
    this.name = 'Thunderstorm';
    this.level = 1;
  }
  strike(ctx, x1, y1, x2, y2) {
    drawJaggedLightningArc(ctx, x1, y1, x2, y2);
  }
}

export class LightningBolt {
  constructor(x, y) {
    this.x = x;
    this.y = y;
  }
}

export class OrbWeapon {
  constructor(player) {
    this.player = player;
    this.pulsePhase = 0;
    this.baseRadius = 75;
  }
  _currentRadius() {
    return this.baseRadius + Math.sin(this.pulsePhase) * 6;
  }
}

/* ── Spatial Hash Grid for O(1) Collision Lookups ────────────────────────── */
class SpatialHashGrid {
  constructor(cellSize = 120) {
    this.cellSize = cellSize;
    this.buckets = new Map();
  }

  clear() {
    this.buckets.clear();
  }

  _hash(gx, gy) {
    return `${gx},${gy}`;
  }

  insert(entity) {
    const minX = Math.floor((entity.x - entity.radius) / this.cellSize);
    const maxX = Math.floor((entity.x + entity.radius) / this.cellSize);
    const minY = Math.floor((entity.y - entity.radius) / this.cellSize);
    const maxY = Math.floor((entity.y + entity.radius) / this.cellSize);

    for (let gx = minX; gx <= maxX; gx++) {
      for (let gy = minY; gy <= maxY; gy++) {
        const key = this._hash(gx, gy);
        let list = this.buckets.get(key);
        if (!list) {
          list = [];
          this.buckets.set(key, list);
        }
        list.push(entity);
      }
    }
  }

  query(x, y, radius) {
    const minX = Math.floor((x - radius) / this.cellSize);
    const maxX = Math.floor((x + radius) / this.cellSize);
    const minY = Math.floor((y - radius) / this.cellSize);
    const maxY = Math.floor((y + radius) / this.cellSize);

    const candidates = [];
    const seen = new Set();

    for (let gx = minX; gx <= maxX; gx++) {
      for (let gy = minY; gy <= maxY; gy++) {
        const key = this._hash(gx, gy);
        const list = this.buckets.get(key);
        if (list) {
          for (let i = 0; i < list.length; i++) {
            const e = list[i];
            if (!seen.has(e.id)) {
              seen.add(e.id);
              candidates.push(e);
            }
          }
        }
      }
    }
    return candidates;
  }
}

/* ── Floating Damage & Healing Text ──────────────────────────────────────── */
class DamageText {
  constructor(x, y, text, color = '#ffd700', isCrit = false, isHeal = false) {
    this.x = x + randRange(-8, 8);
    this.y = y;
    let safeText = String(text);
    if (safeText.includes('undefined')) safeText = '-1';
    this.text = safeText;
    this.color = color;
    this.isCrit = isCrit;
    this.isHeal = isHeal;
    this.life = isCrit || isHeal ? 55 : 42;
    this.maxLife = this.life;
    this.vy = isCrit ? -1.8 : -1.2;
    this.scale = isCrit ? 1.35 : 1.0;
  }

  update() {
    this.life--;
    this.y += this.vy;
    this.vy *= 0.94;
    return this.life > 0;
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY;
    const alpha = Math.min(1, this.life / (this.maxLife * 0.35));

    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.font = `900 ${Math.round(15 * this.scale)}px "Be Vietnam Pro", "Segoe UI", sans-serif`;
    ctx.textAlign = 'center';

    ctx.strokeStyle = 'rgba(0, 0, 0, 0.85)';
    ctx.lineWidth = 3;
    ctx.strokeText(this.text, sx, sy);

    ctx.fillStyle = this.color;
    ctx.fillText(this.text, sx, sy);
    ctx.restore();
  }
}

/* ── Additive Particle System ────────────────────────────────────────────── */
class Particle {
  constructor(x, y, color = '#ff3366', speed = 3.5, size = 4, life = 26, angle = null) {
    this.x = x;
    this.y = y;
    this.color = color;
    this.size = size;
    this.life = life;
    this.maxLife = life;
    const a = angle !== null ? angle : Math.random() * Math.PI * 2;
    const s = speed * randRange(0.6, 1.4);
    this.vx = Math.cos(a) * s;
    this.vy = Math.sin(a) * s;
  }

  update() {
    this.life--;
    this.x += this.vx;
    this.y += this.vy;
    this.vx *= 0.94;
    this.vy *= 0.94;
    return this.life > 0;
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY;
    const alpha = this.life / this.maxLife;

    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = alpha;
    ctx.fillStyle = this.color;
    ctx.beginPath();
    ctx.arc(sx, sy, Math.max(1, this.size * alpha), 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
}

/* ── Shockwave Rings ─────────────────────────────────────────────────────── */
class Shockwave {
  constructor(x, y, maxRadius = 160, color = '#ffd700', duration = 28, lineWidth = 4) {
    this.x = x;
    this.y = y;
    this.radius = 8;
    this.maxRadius = maxRadius;
    this.color = color;
    this.duration = duration;
    this.life = duration;
    this.lineWidth = lineWidth;
  }

  update() {
    this.life--;
    const t = 1 - this.life / this.duration;
    this.radius = 8 + (this.maxRadius - 8) * Math.sin(t * (Math.PI / 2));
    return this.life > 0;
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY;
    const alpha = this.life / this.duration;

    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = this.color;
    ctx.lineWidth = Math.max(1, this.lineWidth * alpha);
    ctx.beginPath();
    ctx.arc(sx, sy, this.radius, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }
}

/* ── Interactive Emoji Particles (Phase 4) ───────────────────────────────── */
class EmojiParticle {
  constructor(x, y, emoji, username) {
    this.x = x;
    this.y = y;
    this.emoji = emoji;
    this.username = username;
    this.life = 120;
    this.maxLife = 120;
    this.scale = 0;
  }

  update() {
    this.life--;
    this.y -= 0.6;
    if (this.scale < 1.2) this.scale += 0.12;
    return this.life > 0;
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY;
    const alpha = Math.min(1, this.life / 25);

    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.font = '26px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(this.emoji, sx, sy - 35);

    ctx.font = '900 11px "Be Vietnam Pro", sans-serif';
    ctx.fillStyle = '#ffe57f';
    ctx.fillText(this.username, sx, sy - 18);
    ctx.restore();
  }
}

/* ── Item Drops: EXP Gems, Gold Coins, Health Potions, EXP Magnets ───────── */
class ExpGem {
  constructor(x, y, xpValue = 5) {
    this.x = x;
    this.y = y;
    this.xp = xpValue;
    this.alive = true;
    this.magnetized = false;
    this.radius = 12;

    if (xpValue >= 100) this.tier = 4;
    else if (xpValue >= 40) this.tier = 3;
    else if (xpValue >= 15) this.tier = 2;
    else this.tier = 1;
  }

  update(player) {
    const d = dist(this.x, this.y, player.x, player.y);
    const pullRange = this.magnetized ? 99999 : player.pickupRadius;

    if (d < pullRange) {
      const speed = this.magnetized ? 16 : 8.5;
      const angle = angleTo(this.x, this.y, player.x, player.y);
      this.x += Math.cos(angle) * speed;
      this.y += Math.sin(angle) * speed;
    }

    if (d < player.radius + 14) {
      this.alive = false;
      return true;
    }
    return false;
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY;
    const sprite = preRenderedGemSprites.get(this.tier);
    if (sprite) {
      ctx.drawImage(sprite, sx - 16, sy - 16);
    }
  }
}

class GoldCoin {
  constructor(x, y, value = 1) {
    this.x = x;
    this.y = y;
    this.value = value;
    this.alive = true;
    this.magnetized = false;
    this.radius = 12;
    this.frame = Math.floor(Math.random() * 8);
  }

  update(player) {
    this.frame = (this.frame + 1) % 8;
    const d = dist(this.x, this.y, player.x, player.y);
    const pullRange = this.magnetized ? 99999 : player.pickupRadius;

    if (d < pullRange) {
      const speed = this.magnetized ? 16 : 8.5;
      const angle = angleTo(this.x, this.y, player.x, player.y);
      this.x += Math.cos(angle) * speed;
      this.y += Math.sin(angle) * speed;
    }

    if (d < player.radius + 14) {
      this.alive = false;
      return true;
    }
    return false;
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY;
    const sprite = preRenderedCoinFrames[this.frame];
    if (sprite) {
      ctx.drawImage(sprite, sx - 14, sy - 14);
    }
  }
}

class HealthPotion {
  constructor(x, y) {
    this.x = x;
    this.y = y;
    this.alive = true;
    this.radius = 16;
    this.bob = Math.random() * Math.PI * 2;
  }

  update(player) {
    this.bob += 0.08;
    const d = dist(this.x, this.y, player.x, player.y);
    if (d < player.pickupRadius) {
      const angle = angleTo(this.x, this.y, player.x, player.y);
      this.x += Math.cos(angle) * 5.5;
      this.y += Math.sin(angle) * 5.5;
    }
    if (d < player.radius + 16) {
      this.alive = false;
      return true;
    }
    return false;
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY + Math.sin(this.bob) * 3;
    drawAdditiveGlow(ctx, sx, sy, 24, 'rgba(255, 23, 68, 0.45)', 0.5);
    const s = preRenderedItemSprites.potion;
    if (s) ctx.drawImage(s, sx - 22, sy - 22);
  }
}

class ExpMagnet {
  constructor(x, y) {
    this.x = x;
    this.y = y;
    this.alive = true;
    this.radius = 16;
    this.bob = Math.random() * Math.PI * 2;
  }

  update(player) {
    this.bob += 0.08;
    const d = dist(this.x, this.y, player.x, player.y);
    if (d < player.pickupRadius) {
      const angle = angleTo(this.x, this.y, player.x, player.y);
      this.x += Math.cos(angle) * 5.5;
      this.y += Math.sin(angle) * 5.5;
    }
    if (d < player.radius + 16) {
      this.alive = false;
      return true;
    }
    return false;
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY + Math.sin(this.bob) * 3;
    drawAdditiveGlow(ctx, sx, sy, 26, 'rgba(0, 229, 255, 0.45)', 0.55);
    const s = preRenderedItemSprites.magnet;
    if (s) ctx.drawImage(s, sx - 22, sy - 22);
  }
}

/* ── Enemy Archetypes (1:1 from main.py) ─────────────────────────────────── */
let enemyIdCounter = 1;

class Enemy {
  constructor(x, y, type = 'BASIC', round = 1) {
    this.id = enemyIdCounter++;
    this.x = x;
    this.y = y;
    this.type = type;
    this.round = round;
    this.alive = true;
    this.hitFlash = 0;
    this.animPhase = Math.random() * Math.PI * 2;
    this.kbx = 0;
    this.kby = 0;
    this.shootCooldown = Math.floor(randRange(70, 130));

    const hpMult = Math.pow(1.35, Math.max(0, round - 1));
    const dmgMult = Math.pow(1.20, Math.max(0, round - 1));
    const spdMult = Math.min(2.0, Math.pow(1.05, Math.max(0, round - 1)));

    if (type === 'FAST') {
      this.maxHp = Math.round(22 * hpMult);
      this.speed = 2.8 * spdMult;
      this.damage = Math.round(6 * dmgMult);
      this.xp = 8;
      this.radius = 12;
      this.color = '#c026d3';
    } else if (type === 'TANK') {
      this.maxHp = Math.round(150 * hpMult);
      this.speed = 0.85 * spdMult;
      this.damage = Math.round(14 * dmgMult);
      this.armor = 3 + round * 2;
      this.xp = 28;
      this.radius = 22;
      this.color = '#475569';
    } else if (type === 'RANGED') {
      this.maxHp = Math.round(42 * hpMult);
      this.speed = 1.1 * spdMult;
      this.damage = Math.round(9 * dmgMult);
      this.xp = 14;
      this.radius = 15;
      this.color = '#06b6d4';
    } else {
      this.maxHp = Math.round(40 * hpMult);
      this.speed = 1.35 * spdMult;
      this.damage = Math.round(8 * dmgMult);
      this.xp = 5;
      this.radius = 14;
      this.color = '#ef4444';
    }

    this.hp = this.maxHp;
  }

  takeDamage(amount) {
    const dmg = Math.max(1, Math.round(Number(amount) || 1));
    const reduced = Math.max(1, dmg - (this.armor || 0));
    this.hp -= reduced;
    this.hitFlash = 6;
    this.kbx += randRange(-2, 2);
    this.kby += randRange(-2, 2);

    if (this.hp <= 0) {
      this.alive = false;
    }
    return reduced;
  }

  update(player, enemyProjectiles) {
    this.animPhase += 0.18;
    if (this.hitFlash > 0) this.hitFlash--;

    this.x += this.kbx;
    this.y += this.kby;
    this.kbx *= 0.8;
    this.kby *= 0.8;

    const d = dist(this.x, this.y, player.x, player.y);
    if (d > 0) {
      const vx = ((player.x - this.x) / d) * this.speed;
      const vy = ((player.y - this.y) / d) * this.speed;
      this.x += vx;
      this.y += vy;
    }

    if (this.type === 'RANGED') {
      this.shootCooldown--;
      if (this.shootCooldown <= 0) {
        this.shootCooldown = Math.floor(randRange(90, 160));
        const ang = angleTo(this.x, this.y, player.x, player.y);
        enemyProjectiles.push(new EnemyProjectile(this.x, this.y, ang, 3.6, this.damage, '#00e575'));
      }
    }

    this.x = clamp(this.x, 20, WORLD_W - 20);
    this.y = clamp(this.y, 20, WORLD_H - 20);
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY;
    const r = this.radius;

    if (sx < -40 || sx > ctx.canvas.width + 40 || sy < -40 || sy > ctx.canvas.height + 40) return;

    const sh = getDropShadowSprite(r * 2.2, r * 0.9);
    if (sh) ctx.drawImage(sh, sx - sh.width / 2, sy + r - sh.height / 2 + 2);

    ctx.save();
    const bob = Math.sin(this.animPhase) * 2;

    if (this.hitFlash > 0) {
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(sx, sy + bob, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
      return;
    }

    if (this.type === 'FAST') {
      const flap = Math.sin(this.animPhase * 2.8) * 8;
      ctx.fillStyle = '#4a0e4e';
      ctx.beginPath();
      ctx.moveTo(sx, sy + bob);
      ctx.lineTo(sx - r - 8, sy - 5 - flap);
      ctx.lineTo(sx - r - 2, sy + 5 - flap / 2);
      ctx.closePath();
      ctx.fill();

      ctx.beginPath();
      ctx.moveTo(sx, sy + bob);
      ctx.lineTo(sx + r + 8, sy - 5 - flap);
      ctx.lineTo(sx + r + 2, sy + 5 - flap / 2);
      ctx.closePath();
      ctx.fill();

      ctx.fillStyle = '#2d0036';
      ctx.beginPath();
      ctx.arc(sx, sy + bob, r - 2, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = '#ff1744';
      ctx.fillRect(sx - 3, sy + bob - 2, 2, 2);
      ctx.fillRect(sx + 2, sy + bob - 2, 2, 2);
    } else if (this.type === 'TANK') {
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(sx - r + 3, sy - r + 4 + bob, (r - 3) * 2, (r - 3) * 2);
      ctx.strokeStyle = '#94a3b8';
      ctx.lineWidth = 1.8;
      ctx.strokeRect(sx - r + 3, sy - r + 4 + bob, (r - 3) * 2, (r - 3) * 2);

      ctx.fillStyle = '#cbd5e1';
      ctx.beginPath();
      ctx.moveTo(sx - r + 3, sy - r + 5 + bob);
      ctx.lineTo(sx - r - 4, sy - r - 4 + bob);
      ctx.lineTo(sx - 4, sy - r + 3 + bob);
      ctx.fill();

      ctx.beginPath();
      ctx.moveTo(sx + r - 3, sy - r + 5 + bob);
      ctx.lineTo(sx + r + 4, sy - r - 4 + bob);
      ctx.lineTo(sx + 4, sy - r + 3 + bob);
      ctx.fill();

      ctx.fillStyle = '#ff0055';
      ctx.fillRect(sx - 4, sy - 4 + bob, 2, 2);
      ctx.fillRect(sx + 3, sy - 4 + bob, 2, 2);
    } else if (this.type === 'RANGED') {
      ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
      ctx.beginPath();
      ctx.arc(sx, sy - 4 + bob, r - 2, Math.PI, 0, false);
      ctx.lineTo(sx + r, sy + r + bob);
      ctx.lineTo(sx, sy + r - 4 + bob);
      ctx.lineTo(sx - r, sy + r + bob);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = '#00e5ff';
      ctx.lineWidth = 1.2;
      ctx.stroke();

      ctx.fillStyle = '#00e5ff';
      ctx.fillRect(sx - 3, sy - 4 + bob, 2, 2);
      ctx.fillRect(sx + 2, sy - 4 + bob, 2, 2);
    } else {
      ctx.fillStyle = '#e2e8f0';
      ctx.beginPath();
      ctx.arc(sx, sy - 5 + bob, r - 5, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = '#94a3b8';
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      ctx.moveTo(sx - 5, sy + bob);
      ctx.lineTo(sx + 5, sy + bob);
      ctx.moveTo(sx - 4, sy + 4 + bob);
      ctx.lineTo(sx + 4, sy + 4 + bob);
      ctx.stroke();

      ctx.strokeStyle = '#b45309';
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(sx + 7, sy + 2 + bob);
      ctx.lineTo(sx + 14, sy - 7 + bob);
      ctx.stroke();

      ctx.fillStyle = '#ef4444';
      ctx.fillRect(sx - 3, sy - 6 + bob, 2, 2);
      ctx.fillRect(sx + 2, sy - 6 + bob, 2, 2);
    }

    if (this.hp < this.maxHp) {
      const bw = r * 2;
      const bh = 3.5;
      const bx = sx - r;
      const by = sy - r - 9 + bob;
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
      ctx.fillRect(bx, by, bw, bh);
      ctx.fillStyle = '#ef4444';
      ctx.fillRect(bx, by, Math.max(0, bw * (this.hp / this.maxHp)), bh);
    }

    ctx.restore();
  }
}

/* ── Bosses (Lich King & Abyssal Demon Lord) ─────────────────────────────── */
class Boss {
  constructor(x, y, round = 1) {
    this.x = x;
    this.y = y;
    this.round = round;
    this.kind = (round - 1) % 2;
    this.name = this.kind === 0 ? 'CHÚA TỂ XƯƠNG (LICH KING)' : 'ÁC QUỶ VỰC THẲM (DEMON LORD)';
    this.alive = true;
    this.hitFlash = 0;
    this.radius = 45;
    this.angle = 0;

    const hpMult = Math.pow(1.40, Math.min(10, round - 1));
    this.maxHp = Math.round(1800 * hpMult);
    this.hp = this.maxHp;
    this.damage = Math.round(36 * Math.pow(1.20, Math.min(10, round - 1)));
    this.speed = 1.05 * Math.min(1.8, Math.pow(1.04, round - 1));
    this.armor = 8 + round * 3;

    this.shootCooldown = 65;
    this.telegraphCooldown = 150;
    this.telegraphs = [];
    this.color = this.kind === 0 ? '#46d2c3' : '#e12346';
    this.ringColor = this.kind === 0 ? '#78ffe1' : '#ff6e32';
  }

  takeDamage(amount) {
    const dmg = Math.max(1, Math.round(Number(amount) || 1));
    const actual = Math.max(2, dmg - this.armor);
    this.hp -= actual;
    this.hitFlash = 6;
    if (this.hp <= 0) {
      this.alive = false;
    }
    return actual;
  }

  update(player, enemyProjectiles) {
    this.angle += 0.04;
    if (this.hitFlash > 0) this.hitFlash--;

    const enraged = this.hp < this.maxHp * 0.5;
    const effSpeed = this.speed * (enraged ? 1.3 : 1.0);

    const d = dist(this.x, this.y, player.x, player.y);
    if (d > 0) {
      this.x += ((player.x - this.x) / d) * effSpeed;
      this.y += ((player.y - this.y) / d) * effSpeed;
    }

    this.shootCooldown--;
    if (this.shootCooldown <= 0) {
      this.shootCooldown = enraged ? 42 : 58;
      const baseA = angleTo(this.x, this.y, player.x, player.y);
      const shots = enraged ? 8 : 6;
      for (let i = 0; i < shots; i++) {
        const spread = (i - (shots - 1) / 2) * 0.18;
        enemyProjectiles.push(new EnemyProjectile(
          this.x, this.y, baseA + spread, 4.2, this.damage, this.ringColor, 8
        ));
      }
    }

    this.telegraphCooldown--;
    if (this.telegraphCooldown <= 0) {
      this.telegraphCooldown = enraged ? 110 : 160;
      if (this.kind === 0) {
        this.telegraphs.push({
          kind: 'circle',
          x: player.x + randRange(-50, 50),
          y: player.y + randRange(-50, 50),
          radius: 120,
          timer: 75,
          maxTimer: 75,
        });
      } else {
        this.telegraphs.push({
          kind: 'line',
          x: this.x,
          y: this.y,
          radius: 480,
          angle: angleTo(this.x, this.y, player.x, player.y),
          timer: 60,
          maxTimer: 60,
        });
      }
    }

    for (let i = this.telegraphs.length - 1; i >= 0; i--) {
      const tg = this.telegraphs[i];
      tg.timer--;
      if (tg.timer <= 0) {
        if (tg.kind === 'circle') {
          if (dist(player.x, player.y, tg.x, tg.y) <= tg.radius) {
            player.takeDamage(this.damage);
          }
          for (let k = 0; k < 8; k++) {
            const ang = (Math.PI * 2 / 8) * k;
            enemyProjectiles.push(new EnemyProjectile(tg.x, tg.y, ang, 4.0, Math.round(this.damage * 0.75), '#ff3366', 7));
          }
        } else {
          for (let step = 0; step < 5; step++) {
            enemyProjectiles.push(new EnemyProjectile(
              tg.x, tg.y, tg.angle, 5.0 + step * 0.8, this.damage, '#ff6600', 9
            ));
          }
        }
        this.telegraphs[i] = this.telegraphs[this.telegraphs.length - 1];
        this.telegraphs.pop();
      }
    }

    this.x = clamp(this.x, 80, WORLD_W - 80);
    this.y = clamp(this.y, 80, WORLD_H - 80);
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY;
    const r = this.radius;

    for (let i = 0; i < this.telegraphs.length; i++) {
      const tg = this.telegraphs[i];
      const tsx = tg.x - camX;
      const tsy = tg.y - camY;
      const ratio = 1 - tg.timer / tg.maxTimer;

      ctx.save();
      if (tg.kind === 'circle') {
        ctx.fillStyle = `rgba(239, 68, 68, ${0.15 + 0.35 * ratio})`;
        ctx.beginPath();
        ctx.arc(tsx, tsy, tg.radius, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 2.5;
        ctx.stroke();

        ctx.strokeStyle = '#ff99aa';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(tsx, tsy, tg.radius * ratio, 0, Math.PI * 2);
        ctx.stroke();
      } else {
        const endX = tsx + Math.cos(tg.angle) * tg.radius;
        const endY = tsy + Math.sin(tg.angle) * tg.radius;
        ctx.strokeStyle = `rgba(255, 60, 60, ${0.4 + 0.5 * ratio})`;
        ctx.lineWidth = 6 * ratio + 2;
        ctx.beginPath();
        ctx.moveTo(tsx, tsy);
        ctx.lineTo(endX, endY);
        ctx.stroke();
      }
      ctx.restore();
    }

    const sh = getDropShadowSprite(r * 2.8, r * 1.2);
    if (sh) ctx.drawImage(sh, sx - sh.width / 2, sy + r - sh.height / 2 + 6);

    drawAdditiveGlow(ctx, sx, sy, r + 24, this.ringColor, 0.45);

    ctx.save();
    ctx.strokeStyle = this.ringColor;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(sx, sy, r + 16, 0, Math.PI * 2);
    ctx.stroke();

    for (let i = 0; i < 8; i++) {
      const a = this.angle + (Math.PI * 2 / 8) * i;
      const px = sx + Math.cos(a) * (r + 16);
      const py = sy + Math.sin(a) * (r + 16);
      ctx.fillStyle = this.ringColor;
      ctx.beginPath();
      ctx.arc(px, py, 4.5, 0, Math.PI * 2);
      ctx.fill();
    }

    if (this.hitFlash > 0) {
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(sx, sy, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
      return;
    }

    ctx.fillStyle = this.color;
    ctx.beginPath();
    ctx.arc(sx, sy, r, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 3;
    ctx.stroke();

    if (this.kind === 0) {
      ctx.fillStyle = '#ffd700';
      ctx.beginPath();
      ctx.moveTo(sx - 20, sy - r);
      ctx.lineTo(sx - 10, sy - r - 16);
      ctx.lineTo(sx, sy - r - 6);
      ctx.lineTo(sx + 10, sy - r - 16);
      ctx.lineTo(sx + 20, sy - r);
      ctx.closePath();
      ctx.fill();
    } else {
      ctx.fillStyle = '#1e1b4b';
      ctx.beginPath();
      ctx.moveTo(sx - 22, sy - r + 8);
      ctx.lineTo(sx - 38, sy - r - 22);
      ctx.lineTo(sx - 10, sy - r + 4);
      ctx.fill();

      ctx.beginPath();
      ctx.moveTo(sx + 22, sy - r + 8);
      ctx.lineTo(sx + 38, sy - r - 22);
      ctx.lineTo(sx + 10, sy - r + 4);
      ctx.fill();
    }

    ctx.fillStyle = '#ffff00';
    ctx.fillRect(sx - 10, sy - 6, 6, 6);
    ctx.fillRect(sx + 4, sy - 6, 6, 6);

    ctx.restore();
  }
}

class EnemyProjectile {
  constructor(x, y, angle, speed, damage, color = '#ff3366', size = 6) {
    this.x = x;
    this.y = y;
    this.vx = Math.cos(angle) * speed;
    this.vy = Math.sin(angle) * speed;
    this.damage = damage;
    this.color = color;
    this.size = size;
    this.life = 120;
    this.alive = true;
  }

  update(player) {
    this.life--;
    this.x += this.vx;
    this.y += this.vy;

    if (dist(this.x, this.y, player.x, player.y) < player.radius + this.size) {
      player.takeDamage(this.damage);
      this.alive = false;
      return true;
    }
    if (this.life <= 0) this.alive = false;
    return false;
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY;
    drawAdditiveGlow(ctx, sx, sy, this.size * 2, this.color, 0.4);
    ctx.fillStyle = this.color;
    ctx.beginPath();
    ctx.arc(sx, sy, this.size, 0, Math.PI * 2);
    ctx.fill();
  }
}

/* ── Player Character & Full Skill Engine (Ported 1:1 from main.py) ──────── */
class Player {
  constructor(x, y, skin, adminBuffs = {}) {
    this.x = x;
    this.y = y;
    this.skin = skin || { name: 'Survivor', slug: 'default' };
    this.adminBuffs = adminBuffs;
    this.radius = 16;
    this.baseSpeed = 3.2;
    this.speedMult = 1.0;
    this.pickupRadius = 90;

    const bonusHp = Number(adminBuffs.bonusHp) || 0;
    this.bonusDamage = Number(adminBuffs.bonusDamage) || 0;
    this.maxHp = 120 + bonusHp;
    this.hp = this.maxHp;
    this.armor = 0;
    this.recovery = 0;
    this.recoveryAcc = 0;
    this.cdr = 0.0;
    this.invincible = 0;
    this.hitFlash = 0;
    this.angle = 0;

    this.level = 1;
    this.xp = 0;
    this.xpNeeded = 20;

    this.palette = {
      primary: '#3b82f6',
      accent: '#60a5fa',
    };
    if (skin && skin.palette) {
      this.palette = skin.palette;
    }

    this.skills = {
      whip: { level: 0, cooldown: 0, tick: 55, range: 195, fused: false },
      void: { level: 0, cooldown: 0, tick: 95, orbs: [], fused: false },
      arrow: { level: 0, cooldown: 0, tick: 48, arrows: [], fused: false },
      hammer: { level: 0, cooldown: 0, tick: 70, angle: 0, hammers: [], fused: false },
      orb: { level: 0, count: 0, angle: 0, orbs: [] },
      aura: { level: 0, cooldown: 0, tick: 40, radius: 110 },
      boomerang: { level: 0, cooldown: 0, tick: 60, boomerangs: [] },
      lightning: { level: 0, cooldown: 0, tick: 75 },
      fire_trail: { level: 0, pools: [] },
      ice_wand: { level: 0, cooldown: 0, tick: 50, bolts: [] },
      vitality: { level: 0 },
      speed: { level: 0 },
      armor: { level: 0 },
      recovery: { level: 0 },
    };

    this._initStarterSkill();
  }

  _initStarterSkill() {
    const sig = getSkinSignatureSkill(this.skin.slug);
    const key = sig ? sig.key : 'whip';
    if (this.skills[key]) {
      this.skills[key].level = 1;
      if (key === 'orb') this.skills.orb.count = 2;
    } else {
      this.skills.whip.level = 1;
    }
  }

  gainXp(amount) {
    this.xp += amount;
    let leveled = false;
    while (this.xp >= this.xpNeeded) {
      this.xp -= this.xpNeeded;
      this.level++;
      this.xpNeeded = Math.round(this.xpNeeded * 1.3);
      leveled = true;
    }
    return leveled;
  }

  takeDamage(amount) {
    if (this.invincible > 0) return;
    const dmg = Math.max(1, Math.round(Number(amount) || 1));
    const reduced = Math.max(1, dmg - this.armor);
    this.hp -= reduced;
    this.invincible = 40;
    this.hitFlash = 6;
  }

  update(keys, dt) {
    if (this.invincible > 0) this.invincible--;
    if (this.hitFlash > 0) this.hitFlash--;

    if (this.recovery > 0 && this.hp < this.maxHp) {
      this.recoveryAcc += this.recovery / 60;
      if (this.recoveryAcc >= 1) {
        const heal = Math.floor(this.recoveryAcc);
        this.hp = Math.min(this.maxHp, this.hp + heal);
        this.recoveryAcc -= heal;
      }
    }

    let dx = 0;
    let dy = 0;
    if (keys['KeyW'] || keys['ArrowUp']) dy -= 1;
    if (keys['KeyS'] || keys['ArrowDown']) dy += 1;
    if (keys['KeyA'] || keys['ArrowLeft']) dx -= 1;
    if (keys['KeyD'] || keys['ArrowRight']) dx += 1;

    if (dx !== 0 && dy !== 0) {
      dx *= 0.7071;
      dy *= 0.7071;
    }

    const currentSpeed = this.baseSpeed * this.speedMult;
    this.x += dx * currentSpeed;
    this.y += dy * currentSpeed;

    if (dx !== 0 || dy !== 0) {
      this.angle = Math.atan2(dy, dx);
      if (this.skills.fire_trail.level > 0 && Math.random() < 0.22) {
        this.skills.fire_trail.pools.push(new FirePool(
          this.x, this.y, 16 + this.skills.fire_trail.level * 6 + this.bonusDamage,
          this.skills.fire_trail.fused
        ));
      }
    }

    this.x = clamp(this.x, 25, WORLD_W - 25);
    this.y = clamp(this.y, 25, WORLD_H - 25);
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY;

    const sh = getDropShadowSprite(this.radius * 2.2, this.radius * 0.9);
    if (sh) ctx.drawImage(sh, sx - sh.width / 2, sy + this.radius - sh.height / 2 + 3);

    drawAdditiveGlow(ctx, sx, sy, 35, this.palette.accent || '#3b82f6', 0.45);

    ctx.save();
    if (this.hitFlash > 0) {
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(sx, sy, this.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
      return;
    }

    ctx.fillStyle = this.palette.primary || '#3b82f6';
    ctx.beginPath();
    ctx.arc(sx, sy, this.radius, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2.2;
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    const ex = sx + Math.cos(this.angle) * 7;
    const ey = sy + Math.sin(this.angle) * 7;
    ctx.beginPath();
    ctx.arc(ex, ey, 4.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }
}

/* ── Secondary Weapon Projectiles & Effects ──────────────────────────────── */
class FirePool {
  constructor(x, y, damage, fused = false) {
    this.x = x;
    this.y = y;
    this.damage = damage;
    this.fused = fused;
    this.radius = fused ? 42 : 28;
    this.life = 120;
    this.alive = true;
  }

  update(grid, damageTexts) {
    this.life--;
    if (this.life % 20 === 0) {
      const candidates = grid.query(this.x, this.y, this.radius);
      for (let i = 0; i < candidates.length; i++) {
        const e = candidates[i];
        if (e.alive && dist(this.x, this.y, e.x, e.y) < this.radius + e.radius) {
          const dealt = e.takeDamage(this.damage);
          damageTexts.push(new DamageText(e.x, e.y - 12, dealt, '#ff6600'));
        }
      }
    }
    if (this.life <= 0) this.alive = false;
    return this.alive;
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY;
    const alpha = Math.min(1, this.life / 30);
    drawAdditiveGlow(ctx, sx, sy, this.radius * 1.5, this.fused ? '#ffd700' : '#ff3d00', 0.4 * alpha);
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = this.fused ? '#ffea00' : '#ff3d00';
    ctx.beginPath();
    ctx.arc(sx, sy, this.radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
}

export class SingularityOrb {
  constructor(x, y, angle, damage, pullRadius = 130, fused = false) {
    this.x = x;
    this.y = y;
    this.vx = Math.cos(angle) * 3.6;
    this.vy = Math.sin(angle) * 3.6;
    this.damage = damage;
    this.pullRadius = pullRadius;
    this.fused = fused;
    this.pullStr = 2.4;
    this.life = 130;
    this.alive = true;
  }

  update(grid, particles, damageTexts) {
    this.life--;
    this.x += this.vx;
    this.y += this.vy;
    this.vx *= 0.98;
    this.vy *= 0.98;

    const candidates = grid.query(this.x, this.y, this.pullRadius);
    for (let i = 0; i < candidates.length; i++) {
      const e = candidates[i];
      if (e.alive) {
        const d = dist(this.x, this.y, e.x, e.y);
        if (d < this.pullRadius + e.radius && d > 4) {
          const pullSpeed = this.fused ? 4.5 : this.pullStr;
          e.x += ((this.x - e.x) / d) * pullSpeed;
          e.y += ((this.y - e.y) / d) * pullSpeed;

          if (this.life % 16 === 0) {
            const dealt = e.takeDamage(Math.round(this.damage * 0.35));
            damageTexts.push(new DamageText(e.x, e.y - 14, dealt, '#b854ff'));
          }
        }
      }
    }

    if (this.life <= 0) {
      this.alive = false;
      for (let i = 0; i < candidates.length; i++) {
        const e = candidates[i];
        if (e.alive && dist(this.x, this.y, e.x, e.y) < this.pullRadius * 0.75 + e.radius) {
          const dealt = e.takeDamage(this.damage);
          damageTexts.push(new DamageText(e.x, e.y - 18, dealt, '#d500f9', true));
        }
      }
      for (let i = 0; i < 22; i++) {
        particles.push(new Particle(this.x, this.y, this.fused ? '#00e5ff' : '#d500f9', 4.5, 4, 30));
      }
    }
    return this.alive;
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY;
    drawAdditiveGlow(ctx, sx, sy, this.pullRadius * 0.7, this.fused ? '#00e5ff' : '#b854ff', 0.5);

    ctx.save();
    ctx.fillStyle = '#0f051d';
    ctx.beginPath();
    ctx.arc(sx, sy, 14, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = this.fused ? '#00e5ff' : '#d500f9';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(sx, sy, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
}

class PhantomArrow {
  constructor(x, y, angle, damage, bounces = 2, fused = false) {
    this.x = x;
    this.y = y;
    this.vx = Math.cos(angle) * 7.5;
    this.vy = Math.sin(angle) * 7.5;
    this.damage = damage;
    this.bounces = bounces;
    this.fused = fused;
    this.life = 70;
    this.alive = true;
    this.pierce = 2;
  }

  update(grid, damageTexts, particles) {
    this.life--;
    this.x += this.vx;
    this.y += this.vy;

    const candidates = grid.query(this.x, this.y, 14);
    for (let i = 0; i < candidates.length; i++) {
      const e = candidates[i];
      if (e.alive && dist(this.x, this.y, e.x, e.y) < 14 + e.radius) {
        const isCrit = Math.random() < 0.35;
        const dealt = e.takeDamage(isCrit ? Math.round(this.damage * 1.8) : this.damage);
        damageTexts.push(new DamageText(e.x, e.y - 15, dealt, '#32ffa0', isCrit));

        for (let p = 0; p < 4; p++) {
          particles.push(new Particle(this.x, this.y, '#32ffa0', 3.0, 3, 18));
        }

        this.pierce--;
        if (this.pierce <= 0) {
          if (this.bounces > 0) {
            this.bounces--;
            this.pierce = 1;
            for (let j = 0; j < candidates.length; j++) {
              const other = candidates[j];
              if (other.id !== e.id && other.alive) {
                const ang = angleTo(this.x, this.y, other.x, other.y);
                this.vx = Math.cos(ang) * 7.5;
                this.vy = Math.sin(ang) * 7.5;
                break;
              }
            }
          } else {
            this.alive = false;
            break;
          }
        }
      }
    }

    if (this.life <= 0) this.alive = false;
    return this.alive;
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY;
    drawAdditiveGlow(ctx, sx, sy, 14, '#32ffa0', 0.45);

    ctx.save();
    ctx.strokeStyle = '#32ffa0';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(sx - this.vx * 1.5, sy - this.vy * 1.5);
    ctx.lineTo(sx, sy);
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(sx, sy, 2.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
}

class SpiralingHammer {
  constructor(x, y, startAngle, damage, fused = false) {
    this.originX = x;
    this.originY = y;
    this.angle = startAngle;
    this.radius = 25;
    this.damage = damage;
    this.fused = fused;
    this.life = 100;
    this.alive = true;
  }

  update(player, grid, damageTexts, particles) {
    this.life--;
    this.angle += 0.12;
    this.radius += 1.8;
    this.originX = player.x;
    this.originY = player.y;

    const x = this.originX + Math.cos(this.angle) * this.radius;
    const y = this.originY + Math.sin(this.angle) * this.radius;

    const candidates = grid.query(x, y, 16);
    for (let i = 0; i < candidates.length; i++) {
      const e = candidates[i];
      if (e.alive && dist(x, y, e.x, e.y) < 16 + e.radius) {
        const dealt = e.takeDamage(this.damage);
        damageTexts.push(new DamageText(e.x, e.y - 16, dealt, '#ffd54f', true));
        for (let p = 0; p < 3; p++) {
          particles.push(new Particle(x, y, '#ffd54f', 3.5, 3, 16));
        }
      }
    }

    if (this.life <= 0) this.alive = false;
    return this.alive;
  }

  draw(ctx, camX, camY) {
    const x = this.originX + Math.cos(this.angle) * this.radius;
    const y = this.originY + Math.sin(this.angle) * this.radius;
    const sx = x - camX;
    const sy = y - camY;

    drawAdditiveGlow(ctx, sx, sy, 22, this.fused ? '#ffd700' : '#ffd54f', 0.5);

    ctx.save();
    ctx.translate(sx, sy);
    ctx.rotate(this.angle * 2.5);

    ctx.fillStyle = this.fused ? '#ffea00' : '#ffd54f';
    ctx.fillRect(-7, -7, 14, 14);
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.8;
    ctx.strokeRect(-7, -7, 14, 14);

    ctx.restore();
  }
}

class CrescentSlash {
  constructor(x, y, angle, range, damage, fused = false) {
    this.x = x;
    this.y = y;
    this.angle = angle;
    this.range = range;
    this.damage = damage;
    this.fused = fused;
    this.life = 12;
    this.maxLife = 12;
    this.alive = true;
  }

  update() {
    this.life--;
    if (this.life <= 0) this.alive = false;
    return this.alive;
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY;
    const alpha = this.life / this.maxLife;

    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = alpha;

    const cone = this.fused ? Math.PI : 0.65;
    ctx.strokeStyle = this.fused ? '#ff1744' : '#ff2e54';
    ctx.lineWidth = this.fused ? 9 : 6;

    ctx.beginPath();
    ctx.arc(sx, sy, this.range, this.angle - cone, this.angle + cone);
    ctx.stroke();

    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(sx, sy, this.range - 3, this.angle - cone * 0.8, this.angle + cone * 0.8);
    ctx.stroke();

    ctx.restore();
  }
}

/* ── Teammate Representation (Co-op & Ranked 3v3) ────────────────────────── */
class Teammate {
  constructor(id, x, y, username, skinSlug, team = null) {
    this.id = id;
    this.x = x;
    this.y = y;
    this.targetX = x;
    this.targetY = y;
    this.username = username || 'Partner';
    this.skinSlug = skinSlug || 'default';
    this.team = team;
    this.radius = 16;
  }

  setTarget(x, y) {
    this.targetX = x;
    this.targetY = y;
  }

  update() {
    this.x = lerp(this.x, this.targetX, 0.25);
    this.y = lerp(this.y, this.targetY, 0.25);
  }

  draw(ctx, camX, camY) {
    const sx = this.x - camX;
    const sy = this.y - camY;

    const sh = getDropShadowSprite(this.radius * 2.2, this.radius * 0.9);
    if (sh) ctx.drawImage(sh, sx - sh.width / 2, sy + this.radius - sh.height / 2 + 2);

    ctx.save();
    const isRedTeam = this.team === 'red';
    const isBlueTeam = this.team === 'blue';
    const teamColor = isRedTeam ? '#ef4444' : isBlueTeam ? '#3b82f6' : '#10b981';

    drawAdditiveGlow(ctx, sx, sy, 28, teamColor, 0.35);

    ctx.fillStyle = teamColor;
    ctx.beginPath();
    ctx.arc(sx, sy, this.radius, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.font = '900 11px "Be Vietnam Pro", sans-serif';
    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'center';
    ctx.fillText(this.username, sx, sy - 22);
    ctx.restore();
  }
}

/* ── Main HTML5 Canvas Engine Class ──────────────────────────────────────── */
export class GameEngine {
  constructor(canvas, hud = {}, callbacks = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.hud = hud;
    this.callbacks = callbacks;

    this.width = canvas.width = window.innerWidth;
    this.height = canvas.height = window.innerHeight;

    // Core loops & flags
    this.isRunning = false;
    this.isPaused = false;
    this.isLevelingUp = false;
    this.rafId = null;
    this._rafId = null;
    this.tick = 0;
    this.camX = WORLD_W / 2 - this.width / 2;
    this.camY = WORLD_H / 2 - this.height / 2;

    // Mode: 'solo', 'coop', 'ranked'
    this.mode = 'solo';
    this.socket = null;
    this.room = null;
    this.myTeam = null;

    // Entities
    this.player = null;
    this.enemies = [];
    this.boss = null;
    this.enemyProjectiles = [];
    this.projectiles = [];
    this.particles = [];
    this.shockwaves = [];
    this.damageTexts = [];
    this.emojiParticles = [];
    this.xpGems = [];
    this.goldCoins = [];
    this.items = [];
    this.slashes = [];
    this.teammates = new Map();

    // Spatial hash grid
    this.grid = new SpatialHashGrid(120);

    // Wave / Round System & Quota
    this.round = 1;
    this.roundQuota = 25;
    this.spawnedThisRound = 0;
    this.slainThisRound = 0;
    this.bossSpawned = false;
    this.roundCompleteTimer = 0;
    this.spawnCooldown = 0;
    this.sessionKills = 0;
    this.sessionGold = 0;

    // Keys
    this.keys = {};
    this._handleKeyDown = this._handleKeyDown.bind(this);
    this._handleKeyUp = this._handleKeyUp.bind(this);
    this._handleResize = this._handleResize.bind(this);
    this.loop = this.loop.bind(this);

    initSpriteCache();
    window.addEventListener('resize', this._handleResize);
  }

  start(skin, options = {}) {
    this.stop();
    this.mode = options.mode || 'solo';
    this.socket = options.socket || null;
    this.room = options.room || null;
    this.myTeam = options.yourTeam || options.team || null;

    this.tick = 0;
    this.round = 1;
    this.roundQuota = 25;
    this.spawnedThisRound = 0;
    this.slainThisRound = 0;
    this.bossSpawned = false;
    this.roundCompleteTimer = 0;
    this.sessionKills = 0;
    this.sessionGold = 0;
    this.isPaused = false;
    this.isLevelingUp = false;

    this.enemies.length = 0;
    this.boss = null;
    this.enemyProjectiles.length = 0;
    this.projectiles.length = 0;
    this.particles.length = 0;
    this.shockwaves.length = 0;
    this.damageTexts.length = 0;
    this.emojiParticles.length = 0;
    this.xpGems.length = 0;
    this.goldCoins.length = 0;
    this.items.length = 0;
    this.slashes.length = 0;
    this.teammates.clear();

    const adminBuffs = (typeof localStorage !== 'undefined' && JSON.parse(localStorage.getItem('ls_bridge_user') || '{}').adminBuffs) || {};
    this.player = new Player(WORLD_W / 2, WORLD_H / 2, skin, adminBuffs);
    this.camX = this.player.x - this.width / 2;
    this.camY = this.player.y - this.height / 2;

    window.addEventListener('keydown', this._handleKeyDown);
    window.addEventListener('keyup', this._handleKeyUp);

    this.isRunning = true;
    this._updateHUD();
    this._renderSkillBar();
    this._rafId = requestAnimationFrame(this.loop);
    this.rafId = this._rafId;
  }

  stop() {
    this.isRunning = false;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.enemies.length = 0;
    this.projectiles.length = 0;
    if (this._rafId) {
      cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }
    this.rafId = null;
    window.removeEventListener('keydown', this._handleKeyDown);
    window.removeEventListener('keyup', this._handleKeyUp);
    this.keys = {};
  }

  _handleResize() {
    this.width = this.canvas.width = window.innerWidth;
    this.height = this.canvas.height = window.innerHeight;
  }

  _handleKeyDown(e) {
    if (!this.isRunning) return;
    this.keys[e.code] = true;
    if (e.code === 'Escape') {
      this.togglePause();
    }
  }

  _handleKeyUp(e) {
    if (!this.isRunning) return;
    this.keys[e.code] = false;
  }

  togglePause() {
    if (this.isLevelingUp) return;
    this.isPaused = !this.isPaused;
    if (this.callbacks.onPauseStateChange) {
      this.callbacks.onPauseStateChange(this.isPaused, this.getStats());
    }
  }

  resume() {
    this.isPaused = false;
    if (this.callbacks.onPauseStateChange) {
      this.callbacks.onPauseStateChange(false, this.getStats());
    }
  }

  getStats() {
    return {
      survivalTime: Math.floor(this.tick / 60),
      kills: this.sessionKills,
      level: this.player ? this.player.level : 1,
      gold: this.sessionGold,
      mode: this.mode,
      round: this.round,
    };
  }

  sendEmoji(emoji) {
    if (!this.player) return;
    this.emojiParticles.push(new EmojiParticle(this.player.x, this.player.y, emoji, this.player.skin.name || 'You'));
    if (this.socket && this.socket.connected) {
      this.socket.emit('playerEmoji', { emoji });
    }
  }

  /* ── 60 FPS Game Loop ─────────────────────────────────────────────────── */
  loop() {
    if (!this.isRunning) return;

    if (!this.isPaused && !this.isLevelingUp) {
      this.update();
    }
    this.render();

    this._rafId = requestAnimationFrame(this.loop);
    this.rafId = this._rafId;
  }

  /* ── Update Logic ──────────────────────────────────────────────────────── */
  update() {
    this.tick++;
    const p = this.player;

    // 1. Update Player
    p.update(this.keys, 1 / 60);

    const targetCamX = p.x - this.width / 2;
    const targetCamY = p.y - this.height / 2;
    this.camX = lerp(this.camX, targetCamX, 0.12);
    this.camY = lerp(this.camY, targetCamY, 0.12);

    // 2. Spatial Hash Grid insertion
    this.grid.clear();
    for (let i = 0; i < this.enemies.length; i++) {
      if (this.enemies[i].alive) {
        this.grid.insert(this.enemies[i]);
      }
    }
    if (this.boss && this.boss.alive) {
      this.grid.insert(this.boss);
    }

    // 3. Finite Quota Wave Spawning & Boss Progression
    this._updateWaveSpawner();

    // 4. Update Weapon Skills & Auto-Attacks
    this._updatePlayerWeapons();

    // 5. Update Enemies
    for (let i = 0; i < this.enemies.length; i++) {
      const e = this.enemies[i];
      if (e.alive) {
        e.update(p, this.enemyProjectiles);
        if (dist(e.x, e.y, p.x, p.y) < e.radius + p.radius) {
          p.takeDamage(e.damage);
        }
      }
    }

    // 6. Update Boss
    if (this.boss && this.boss.alive) {
      this.boss.update(p, this.enemyProjectiles);
      if (dist(this.boss.x, this.boss.y, p.x, p.y) < this.boss.radius + p.radius) {
        p.takeDamage(this.boss.damage);
      }
    }

    // 7. Update Enemy Projectiles
    for (let i = this.enemyProjectiles.length - 1; i >= 0; i--) {
      const proj = this.enemyProjectiles[i];
      proj.update(p);
      if (!proj.alive) {
        this.enemyProjectiles[i] = this.enemyProjectiles[this.enemyProjectiles.length - 1];
        this.enemyProjectiles.pop();
      }
    }

    // 8. Handle Enemy Deaths & Item Drops (Swap-and-Pop)
    for (let i = this.enemies.length - 1; i >= 0; i--) {
      const e = this.enemies[i];
      if (!e.alive) {
        this.slainThisRound++;
        this.sessionKills++;

        this.xpGems.push(new ExpGem(e.x, e.y, e.xp));

        if (Math.random() < 0.35) {
          this.goldCoins.push(new GoldCoin(e.x, e.y, 1));
        }

        if (Math.random() < 0.04) {
          this.items.push(new HealthPotion(e.x, e.y));
        }

        if (Math.random() < 0.015) {
          this.items.push(new ExpMagnet(e.x, e.y));
        }

        if (p.skills.whip.level >= 1 && p.hp < p.maxHp) {
          const heal = Math.max(1, Math.round(e.maxHp * 0.04));
          p.hp = Math.min(p.maxHp, p.hp + heal);
          this.damageTexts.push(new DamageText(p.x, p.y - 20, `+${heal} HP`, '#00e676', false, true));
        }

        this.enemies[i] = this.enemies[this.enemies.length - 1];
        this.enemies.pop();
      }
    }

    // Handle Boss Death
    if (this.boss && !this.boss.alive && this.bossSpawned) {
      this.boss = null;
      this.items.push(new HealthPotion(p.x + 30, p.y));
      this.items.push(new ExpMagnet(p.x - 30, p.y));
      for (let k = 0; k < 6; k++) {
        this.goldCoins.push(new GoldCoin(p.x + randRange(-50, 50), p.y + randRange(-50, 50), 5));
        this.xpGems.push(new ExpGem(p.x + randRange(-60, 60), p.y + randRange(-60, 60), 100));
      }
    }

    // 9. Update Battlefield Items
    this._updateItems();

    // 10. Update Effects: Slashes, Shockwaves, Particles, Damage Texts
    for (let i = this.slashes.length - 1; i >= 0; i--) {
      if (!this.slashes[i].update()) {
        this.slashes[i] = this.slashes[this.slashes.length - 1];
        this.slashes.pop();
      }
    }
    for (let i = this.shockwaves.length - 1; i >= 0; i--) {
      if (!this.shockwaves[i].update()) {
        this.shockwaves[i] = this.shockwaves[this.shockwaves.length - 1];
        this.shockwaves.pop();
      }
    }
    for (let i = this.particles.length - 1; i >= 0; i--) {
      if (!this.particles[i].update()) {
        this.particles[i] = this.particles[this.particles.length - 1];
        this.particles.pop();
      }
    }
    for (let i = this.damageTexts.length - 1; i >= 0; i--) {
      if (!this.damageTexts[i].update()) {
        this.damageTexts[i] = this.damageTexts[this.damageTexts.length - 1];
        this.damageTexts.pop();
      }
    }
    for (let i = this.emojiParticles.length - 1; i >= 0; i--) {
      if (!this.emojiParticles[i].update()) {
        this.emojiParticles[i] = this.emojiParticles[this.emojiParticles.length - 1];
        this.emojiParticles.pop();
      }
    }

    // 11. Synchronize Multiplayer
    this._syncMultiplayer();

    // 12. Update HUD
    this._updateHUD();

    // 13. Game Over check
    if (p.hp <= 0) {
      this.stop();
      if (this.callbacks.onGameOver) {
        this.callbacks.onGameOver(this.getStats());
      }
    }
  }

  /* ── Finite Monster Quota & Boss Progression ───────────────────────────── */
  _updateWaveSpawner() {
    const remainingQuota = Math.max(0, this.roundQuota - this.slainThisRound);

    if (this.spawnedThisRound < this.roundQuota) {
      this.spawnCooldown--;
      const interval = Math.max(16, 52 - this.round * 4);

      if (this.spawnCooldown <= 0) {
        this.spawnCooldown = interval;
        const avail = this.roundQuota - this.spawnedThisRound;
        const batchSize = Math.min(avail, Math.min(8, 3 + Math.floor(this.round * 0.8)));

        for (let i = 0; i < batchSize; i++) {
          this._spawnClusterEnemy();
          this.spawnedThisRound++;
        }
      }
    }

    if (this.spawnedThisRound >= this.roundQuota && !this.bossSpawned) {
      this.bossSpawned = true;
      if (this.hud.bossAlert) {
        this.hud.bossAlert.classList.remove('hidden');
        setTimeout(() => {
          if (this.hud.bossAlert) this.hud.bossAlert.classList.add('hidden');
        }, 3500);
      }

      const p = this.player;
      const angle = Math.random() * Math.PI * 2;
      const bx = clamp(p.x + Math.cos(angle) * 450, 100, WORLD_W - 100);
      const by = clamp(p.y + Math.sin(angle) * 450, 100, WORLD_H - 100);
      this.boss = new Boss(bx, by, this.round);

      if (this.hud.bossContainer) {
        this.hud.bossContainer.classList.remove('hidden');
        if (this.hud.bossName) this.hud.bossName.textContent = this.boss.name;
      }
      this.shockwaves.push(new Shockwave(bx, by, 320, '#ef4444', 35, 6));
    }

    if (this.bossSpawned && !this.boss && this.slainThisRound >= this.roundQuota) {
      if (this.roundCompleteTimer === 0) {
        this.roundCompleteTimer = 180;
        this.sessionGold += 100;

        if (this.hud.roundClear) {
          this.hud.roundClear.classList.remove('hidden');
          if (this.hud.roundClearSub) {
            this.hud.roundClearSub.textContent = `Tất cả quái và Trùm Hiệp ${this.round} đã bị tiêu diệt! +100 Vàng`;
          }
        }
      } else {
        this.roundCompleteTimer--;
        if (this.roundCompleteTimer <= 0) {
          if (this.hud.roundClear) this.hud.roundClear.classList.add('hidden');
          this.round++;
          this.roundQuota = Math.round(25 * Math.pow(1.32, this.round - 1) + this.round * 10);
          this.spawnedThisRound = 0;
          this.slainThisRound = 0;
          this.bossSpawned = false;
          this.roundCompleteTimer = 0;
        }
      }
    }
  }

  _spawnClusterEnemy() {
    const p = this.player;
    const margin = 120;
    const side = Math.floor(Math.random() * 4);
    let sx, sy;

    if (side === 0) {
      sx = p.x + randRange(-this.width / 2 - margin, this.width / 2 + margin);
      sy = p.y - this.height / 2 - margin;
    } else if (side === 1) {
      sx = p.x + this.width / 2 + margin;
      sy = p.y + randRange(-this.height / 2 - margin, this.height / 2 + margin);
    } else if (side === 2) {
      sx = p.x + randRange(-this.width / 2 - margin, this.width / 2 + margin);
      sy = p.y + this.height / 2 + margin;
    } else {
      sx = p.x - this.width / 2 - margin;
      sy = p.y + randRange(-this.height / 2 - margin, this.height / 2 + margin);
    }

    let type = 'BASIC';
    const roll = Math.random();
    if (this.round >= 2 && roll < 0.32) {
      type = 'FAST';
    } else if (this.round >= 3 && roll < 0.52) {
      type = 'RANGED';
    } else if (this.round >= 2 && roll > 0.82) {
      type = 'TANK';
    }

    this.enemies.push(new Enemy(clamp(sx, 40, WORLD_W - 40), clamp(sy, 40, WORLD_H - 40), type, this.round));
  }

  /* ── Player Weapons & Full Skill Mechanics ─────────────────────────────── */
  _updatePlayerWeapons() {
    const p = this.player;
    const s = p.skills;

    // 1. Trảm Huyết Nguyệt (Blood Moon Slash)
    if (s.whip.level >= 1) {
      s.whip.cooldown--;
      if (s.whip.cooldown <= 0) {
        s.whip.cooldown = Math.max(16, s.whip.tick - s.whip.level * 6);
        const candidates = this.grid.query(p.x, p.y, s.whip.range + 80);
        let target = candidates.length > 0 ? candidates[0] : null;
        const slashAngle = target ? angleTo(p.x, p.y, target.x, target.y) : p.angle;
        const dmg = Math.round((28 + s.whip.level * 14 + p.bonusDamage) * (s.whip.fused ? 1.6 : 1.0));

        this.slashes.push(new CrescentSlash(p.x, p.y, slashAngle, s.whip.range, dmg, s.whip.fused));
        if (s.whip.level >= 5 || s.whip.fused) {
          this.slashes.push(new CrescentSlash(p.x, p.y, slashAngle + Math.PI, s.whip.range, dmg, s.whip.fused));
        }

        const cone = s.whip.fused ? Math.PI : 0.72;
        let totalDealt = 0;
        for (let i = 0; i < candidates.length; i++) {
          const e = candidates[i];
          if (e.alive && dist(p.x, p.y, e.x, e.y) < s.whip.range + e.radius) {
            const a = angleTo(p.x, p.y, e.x, e.y);
            const da = Math.abs(Math.atan2(Math.sin(a - slashAngle), Math.cos(a - slashAngle)));
            const backDa = Math.abs(Math.atan2(Math.sin(a - (slashAngle + Math.PI)), Math.cos(a - (slashAngle + Math.PI))));

            if (s.whip.fused || da < cone || (s.whip.level >= 5 && backDa < cone)) {
              const dealt = e.takeDamage(dmg);
              totalDealt += dealt;
              this.damageTexts.push(new DamageText(e.x, e.y - 14, dealt, s.whip.fused ? '#ff1744' : '#ff2e54', true));
            }
          }
        }

        if (totalDealt > 0 && p.hp < p.maxHp) {
          const heal = Math.max(1, Math.round(totalDealt * (s.whip.fused ? 0.12 : 0.05)));
          p.hp = Math.min(p.maxHp, p.hp + heal);
          this.damageTexts.push(new DamageText(p.x, p.y - 24, `+${heal} HP`, '#00e676', false, true));
        }
      }
    }

    // 2. Hố Đen Hư Không (Void Singularity)
    if (s.void.level >= 1) {
      s.void.cooldown--;
      if (s.void.cooldown <= 0) {
        s.void.cooldown = Math.max(35, s.void.tick - s.void.level * 8);
        const candidates = this.grid.query(p.x, p.y, 450);
        const target = candidates.length > 0 ? candidates[0] : null;
        const ang = target ? angleTo(p.x, p.y, target.x, target.y) : p.angle;
        const dmg = Math.round(30 + s.void.level * 12 + p.bonusDamage);
        const count = s.void.level >= 4 || s.void.fused ? 2 : 1;

        for (let i = 0; i < count; i++) {
          const spread = (i - (count - 1) / 2) * 0.45;
          s.void.orbs.push(new SingularityOrb(
            p.x, p.y, ang + spread, dmg, 120 + s.void.level * 16, s.void.fused
          ));
        }
      }
      for (let i = s.void.orbs.length - 1; i >= 0; i--) {
        if (!s.void.orbs[i].update(this.grid, this.particles, this.damageTexts)) {
          s.void.orbs[i] = s.void.orbs[s.void.orbs.length - 1];
          s.void.orbs.pop();
        }
      }
    }

    // 3. Mưa Tên Độc Ảnh (Phantom Arrow Volley)
    if (s.arrow.level >= 1) {
      s.arrow.cooldown--;
      if (s.arrow.cooldown <= 0) {
        s.arrow.cooldown = Math.max(18, s.arrow.tick - s.arrow.level * 5);
        const candidates = this.grid.query(p.x, p.y, 450);
        const target = candidates.length > 0 ? candidates[0] : null;
        if (target) {
          const baseAng = angleTo(p.x, p.y, target.x, target.y);
          const count = s.arrow.fused ? 5 : (s.arrow.level >= 4 ? 4 : (s.arrow.level >= 2 ? 3 : 2));
          const dmg = Math.round(20 + s.arrow.level * 8 + p.bonusDamage);

          for (let i = 0; i < count; i++) {
            const spread = (i - (count - 1) / 2) * 0.18;
            s.arrow.arrows.push(new PhantomArrow(
              p.x, p.y, baseAng + spread, dmg, s.arrow.level >= 3 ? 3 : 1, s.arrow.fused
            ));
          }
        }
      }
      for (let i = s.arrow.arrows.length - 1; i >= 0; i--) {
        if (!s.arrow.arrows[i].update(this.grid, this.damageTexts, this.particles)) {
          s.arrow.arrows[i] = s.arrow.arrows[s.arrow.arrows.length - 1];
          s.arrow.arrows.pop();
        }
      }
    }

    // 4. Phán Quyết Ánh Sáng (Judgement Hammer)
    if (s.hammer.level >= 1) {
      s.hammer.cooldown--;
      if (s.hammer.cooldown <= 0) {
        s.hammer.cooldown = Math.max(28, s.hammer.tick - s.hammer.level * 7);
        const count = s.hammer.fused ? 4 : (s.hammer.level >= 5 ? 3 : (s.hammer.level >= 3 ? 2 : 1));
        const dmg = Math.round(26 + s.hammer.level * 10 + p.bonusDamage);

        for (let i = 0; i < count; i++) {
          const startA = p.angle + (Math.PI * 2 / count) * i;
          s.hammer.hammers.push(new SpiralingHammer(p.x, p.y, startA, dmg, s.hammer.fused));
        }
      }
      for (let i = s.hammer.hammers.length - 1; i >= 0; i--) {
        if (!s.hammer.hammers[i].update(p, this.grid, this.damageTexts, this.particles)) {
          s.hammer.hammers[i] = s.hammer.hammers[s.hammer.hammers.length - 1];
          s.hammer.hammers.pop();
        }
      }
    }

    // 5. Khiên Tinh Cầu (Celestial Orbs)
    if (s.orb.level >= 1) {
      s.orb.angle += 0.06;
      const count = Math.min(5, 2 + Math.floor(s.orb.level * 0.7));
      const orbRadius = 75 + s.orb.level * 8;
      const dmg = Math.round(18 + s.orb.level * 8 + p.bonusDamage);

      for (let i = 0; i < count; i++) {
        const a = s.orb.angle + (Math.PI * 2 / count) * i;
        const ox = p.x + Math.cos(a) * orbRadius;
        const oy = p.y + Math.sin(a) * orbRadius;

        const candidates = this.grid.query(ox, oy, 16);
        for (let j = 0; j < candidates.length; j++) {
          const e = candidates[j];
          if (e.alive && dist(ox, oy, e.x, e.y) < 16 + e.radius) {
            const dealt = e.takeDamage(dmg);
            this.damageTexts.push(new DamageText(e.x, e.y - 12, dealt, '#4fd8ff'));
          }
        }
      }
    }

    // 6. Trường Lực Thánh (Holy Aura)
    if (s.aura.level >= 1) {
      s.aura.cooldown--;
      if (s.aura.cooldown <= 0) {
        s.aura.cooldown = s.aura.tick;
        const auraRadius = s.aura.radius + s.aura.level * 14;
        const dmg = Math.round(14 + s.aura.level * 7 + p.bonusDamage);
        this.shockwaves.push(new Shockwave(p.x, p.y, auraRadius, '#b388ff', 20, 3));

        const candidates = this.grid.query(p.x, p.y, auraRadius);
        for (let i = 0; i < candidates.length; i++) {
          const e = candidates[i];
          if (e.alive && dist(p.x, p.y, e.x, e.y) < auraRadius + e.radius) {
            const dealt = e.takeDamage(dmg);
            this.damageTexts.push(new DamageText(e.x, e.y - 12, dealt, '#b388ff'));
          }
        }
      }
    }

    // 7. Bão Sấm Sét (Thunderstorm)
    if (s.lightning.level >= 1) {
      s.lightning.cooldown--;
      if (s.lightning.cooldown <= 0) {
        s.lightning.cooldown = Math.max(22, s.lightning.tick - s.lightning.level * 8);
        const candidates = this.grid.query(p.x, p.y, 400);
        if (candidates.length > 0) {
          const target = candidates[Math.floor(Math.random() * candidates.length)];
          const dmg = Math.round(35 + s.lightning.level * 15 + p.bonusDamage);
          const dealt = target.takeDamage(dmg);
          this.damageTexts.push(new DamageText(target.x, target.y - 20, dealt, '#ffd34d', true));
          this.shockwaves.push(new Shockwave(target.x, target.y, 55, '#ffd34d', 16, 4));
        }
      }
    }

    // 8. Vệt Lửa Địa Ngục (Hellfire Pools)
    if (s.fire_trail.level >= 1) {
      for (let i = s.fire_trail.pools.length - 1; i >= 0; i--) {
        if (!s.fire_trail.pools[i].update(this.grid, this.damageTexts)) {
          s.fire_trail.pools[i] = s.fire_trail.pools[s.fire_trail.pools.length - 1];
          s.fire_trail.pools.pop();
        }
      }
    }
  }

  /* ── Update Items & Magnets ────────────────────────────────────────────── */
  _updateItems() {
    const p = this.player;

    // EXP Gems
    for (let i = this.xpGems.length - 1; i >= 0; i--) {
      const g = this.xpGems[i];
      if (g.update(p)) {
        if (p.gainXp(g.xp)) {
          this._triggerLevelUp();
        }
        this.xpGems[i] = this.xpGems[this.xpGems.length - 1];
        this.xpGems.pop();
      }
    }

    // Gold Coins
    for (let i = this.goldCoins.length - 1; i >= 0; i--) {
      const c = this.goldCoins[i];
      if (c.update(p)) {
        this.sessionGold += c.value;
        this.goldCoins[i] = this.goldCoins[this.goldCoins.length - 1];
        this.goldCoins.pop();
      }
    }

    // Potions & Magnets
    for (let i = this.items.length - 1; i >= 0; i--) {
      const it = this.items[i];
      if (it instanceof HealthPotion && it.update(p)) {
        const heal = Math.max(30, Math.round(p.maxHp * 0.25));
        p.hp = Math.min(p.maxHp, p.hp + heal);
        this.damageTexts.push(new DamageText(p.x, p.y - 30, `+${heal} HP`, '#00e676', true, true));
        this.shockwaves.push(new Shockwave(p.x, p.y, 85, '#00e676', 22, 4));
        this.items[i] = this.items[this.items.length - 1];
        this.items.pop();
      } else if (it instanceof ExpMagnet && it.update(p)) {
        for (let g = 0; g < this.xpGems.length; g++) {
          this.xpGems[g].magnetized = true;
        }
        for (let c = 0; c < this.goldCoins.length; c++) {
          this.goldCoins[c].magnetized = true;
        }
        this.shockwaves.push(new Shockwave(p.x, p.y, 350, '#00e5ff', 35, 6));
        this.damageTexts.push(new DamageText(p.x, p.y - 32, 'TỪ TRƯỜNG TOÀN BẢN ĐỒ!', '#00e5ff', true));
        this.items[i] = this.items[this.items.length - 1];
        this.items.pop();
      }
    }
  }

  _showLevelUpModal() {
    if (this.hud && this.hud.levelupOverlay) {
      this.hud.levelupOverlay.classList.remove('hidden');
    }
  }

  /* ── Level-Up Modal Overlay & Mythic Fusions ───────────────────────────── */
  _triggerLevelUp() {
    if (!this.hud.levelupOverlay || !this.hud.levelupCardsContainer) return;
    this.isLevelingUp = true;

    const candidates = [];
    const p = this.player;

    const fusions = [
      { key: 'fusion_blood', req1: 'whip', req2: 'aura' },
      { key: 'fusion_cosmic', req1: 'void', req2: 'lightning' },
      { key: 'fusion_reaper', req1: 'arrow', req2: 'boomerang' },
      { key: 'fusion_solar', req1: 'hammer', req2: 'fire_trail' },
    ];

    for (const f of fusions) {
      if (p.skills[f.req1] && p.skills[f.req1].level >= 5 &&
          p.skills[f.req2] && p.skills[f.req2].level >= 5 &&
          !p.skills[f.req1].fused) {
        candidates.push({ key: f.key, isFusion: true });
      }
    }

    const skillKeys = Object.keys(p.skills);
    for (const k of skillKeys) {
      const s = p.skills[k];
      if (s.level > 0 && s.level < 5) {
        candidates.push({ key: k, currentLevel: s.level, nextLevel: s.level + 1 });
      } else if (s.level === 0) {
        candidates.push({ key: k, currentLevel: 0, nextLevel: 1, isNew: true });
      }
    }

    const shuffled = candidates.sort(() => 0.5 - Math.random());
    const choices = shuffled.slice(0, 3);

    const container = this.hud.levelupCardsContainer;
    container.replaceChildren();

    choices.forEach((choice) => {
      const meta = SKILL_META[choice.key] || {
        name: choice.key,
        iconKey: choice.key,
        description: 'Cường hóa sức mạnh sinh tồn.',
        statUpgrade: '+Sức Mạnh',
      };

      const card = el('div', { class: `levelup-card ${choice.isFusion ? 'fused-card' : ''}` });
      const badgeText = choice.isFusion ? 'HỢP NHẤT THẦN THOẠI' : (choice.isNew ? 'KỸ NĂNG MỚI' : `LV ${choice.currentLevel} → LV ${choice.nextLevel}`);
      const badge = el('span', { class: `levelup-card-badge ${choice.isNew ? 'is-new' : ''}`, text: badgeText });

      const iconWrapper = el('div', { class: 'levelup-card-icon' });
      iconWrapper.innerHTML = getSkillIconSvg(meta.iconKey || choice.key, 48);

      const title = el('h3', { class: 'levelup-card-title', text: meta.name });
      const desc = el('p', { class: 'levelup-card-desc', text: meta.description });
      const stats = el('div', { class: 'levelup-card-stats', text: meta.statUpgrade });
      const selectBtn = el('button', { class: 'btn-levelup-select', text: 'TIẾP NHẬN' });

      selectBtn.addEventListener('click', () => {
        this._applyUpgrade(choice.key);
        this.hud.levelupOverlay.classList.add('hidden');
        this.isLevelingUp = false;
        this._renderSkillBar();
      });

      card.append(badge, iconWrapper, title, desc, stats, selectBtn);
      container.appendChild(card);
    });

    this._showLevelUpModal();
  }

  _applyUpgrade(key) {
    const p = this.player;

    if (key === 'fusion_blood') {
      p.skills.whip.fused = true;
      p.skills.aura.fused = true;
      this.damageTexts.push(new DamageText(p.x, p.y - 35, 'HỢP NHẤT: HUYẾT NGỤC VĨNH HẰNG!', '#ff1744', true));
    } else if (key === 'fusion_cosmic') {
      p.skills.void.fused = true;
      p.skills.lightning.fused = true;
      this.damageTexts.push(new DamageText(p.x, p.y - 35, 'HỢP NHẤT: BÃO TỪ TRƯỜNG VŨ TRỤ!', '#d500f9', true));
    } else if (key === 'fusion_reaper') {
      p.skills.arrow.fused = true;
      p.skills.boomerang.fused = true;
      this.damageTexts.push(new DamageText(p.x, p.y - 35, 'HỢP NHẤT: CƠN LỐC TỬ THẦN!', '#1de9b6', true));
    } else if (key === 'fusion_solar') {
      p.skills.hammer.fused = true;
      p.skills.fire_trail.fused = true;
      this.damageTexts.push(new DamageText(p.x, p.y - 35, 'HỢP NHẤT: THÁI DƯƠNG TẬN THẾ!', '#ffd600', true));
    } else if (p.skills[key]) {
      p.skills[key].level = Math.min(5, p.skills[key].level + 1);

      if (key === 'vitality') {
        p.maxHp += 40;
        p.hp = Math.min(p.maxHp, p.hp + 50);
      } else if (key === 'speed') {
        p.speedMult += 0.12;
      } else if (key === 'armor') {
        p.armor += 2;
      } else if (key === 'recovery') {
        p.recovery += 1.5;
      }
    }
  }

  /* ── Bottom Skill Bar HUD ──────────────────────────────────────────────── */
  _renderSkillBar() {
    if (!this.hud.skillBar || !this.player) return;
    this.hud.skillBar.replaceChildren();

    const activeSkills = [];
    const s = this.player.skills;
    const keys = Object.keys(s);
    for (let i = 0; i < keys.length; i++) {
      const k = keys[i];
      if (s[k].level > 0) {
        activeSkills.push({ key: k, level: s[k].level, fused: s[k].fused });
      }
    }

    activeSkills.forEach((sk) => {
      const meta = SKILL_META[sk.key] || { name: sk.key, iconKey: sk.key };
      const slot = el('div', { class: `skill-slot ${sk.fused ? 'fused' : (sk.level >= 5 ? 'awakened' : '')}`, title: meta.name });

      if (sk.fused) {
        slot.appendChild(el('span', { class: 'skill-slot-badge', text: 'HỢP NHẤT' }));
      } else if (sk.level >= 5) {
        slot.appendChild(el('span', { class: 'skill-slot-badge', text: 'THỨC TỈNH' }));
      }

      const svgContainer = el('div', {});
      svgContainer.innerHTML = getSkillIconSvg(meta.iconKey || sk.key, 30);
      slot.appendChild(svgContainer);

      slot.appendChild(el('span', { class: 'skill-slot-level', text: `Lv.${sk.level}` }));
      this.hud.skillBar.appendChild(slot);
    });
  }

  /* ── Update In-Game HUD ────────────────────────────────────────────────── */
  _updateHUD() {
    const p = this.player;
    if (!p) return;

    if (this.hud.hpBar) {
      const hpPct = Math.max(0, Math.min(100, (p.hp / p.maxHp) * 100));
      this.hud.hpBar.style.width = `${hpPct}%`;
    }
    if (this.hud.hpText) {
      this.hud.hpText.textContent = `${Math.ceil(p.hp)} / ${p.maxHp}`;
    }

    if (this.hud.expBar) {
      const expPct = Math.max(0, Math.min(100, (p.xp / p.xpNeeded) * 100));
      this.hud.expBar.style.width = `${expPct}%`;
    }
    if (this.hud.expText) {
      this.hud.expText.textContent = `EXP: ${p.xp} / ${p.xpNeeded} (${Math.round((p.xp / p.xpNeeded) * 100)}%)`;
    }
    if (this.hud.levelBadge) {
      this.hud.levelBadge.textContent = `LV ${p.level}`;
    }

    if (this.hud.roundBadge) {
      this.hud.roundBadge.textContent = `HIỆP ${this.round}`;
    }
    if (this.hud.roundQuota) {
      const rem = Math.max(0, this.roundQuota - this.slainThisRound);
      this.hud.roundQuota.textContent = `Quái còn lại: ${rem} / ${this.roundQuota}`;
    }

    if (this.hud.timer) {
      const secs = Math.floor(this.tick / 60);
      const m = String(Math.floor(secs / 60)).padStart(2, '0');
      const s = String(secs % 60).padStart(2, '0');
      this.hud.timer.textContent = `${m}:${s}`;
    }

    if (this.hud.kills) this.hud.kills.textContent = this.sessionKills;
    if (this.hud.gold) this.hud.gold.textContent = this.sessionGold;

    if (this.boss && this.boss.alive) {
      if (this.hud.bossBar) {
        const bpct = Math.max(0, Math.min(100, (this.boss.hp / this.boss.maxHp) * 100));
        this.hud.bossBar.style.width = `${bpct}%`;
      }
      if (this.hud.bossHpText) {
        this.hud.bossHpText.textContent = `${this.boss.hp} / ${this.boss.maxHp}`;
      }
    } else if (this.hud.bossContainer && !this.hud.bossContainer.classList.contains('hidden') && !this.boss) {
      this.hud.bossContainer.classList.add('hidden');
    }
  }

  /* ── Multiplayer Synchronization (Co-op & Ranked 3v3) ─────────────────── */
  _syncMultiplayer() {
    if (!this.socket || !this.socket.connected) return;

    if (this.tick % 4 === 0 && this.player) {
      if (this.mode === 'coop' && this.room) {
        this.socket.emit('room:playerMove', {
          roomCode: this.room.code,
          x: Math.round(this.player.x),
          y: Math.round(this.player.y),
          hp: Math.round(this.player.hp),
        });
      } else if (this.mode === 'ranked' && this.room) {
        this.socket.emit('ranked:playerMove', {
          roomId: this.room.roomId,
          team: this.myTeam,
          x: Math.round(this.player.x),
          y: Math.round(this.player.y),
        });
      }
    }
  }

  // ── Render Loop (Zero ctx.shadowBlur) ───────────────────────────────────
  render() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.width, this.height);

    const camX = Math.round(this.camX);
    const camY = Math.round(this.camY);

    // 1. Pre-Rendered Dark Arcane Map Tiles
    const chunk = getArcaneTileChunk(0);
    const startX = Math.floor(camX / CHUNK_SIZE) * CHUNK_SIZE;
    const startY = Math.floor(camY / CHUNK_SIZE) * CHUNK_SIZE;

    for (let x = startX; x < camX + this.width + CHUNK_SIZE; x += CHUNK_SIZE) {
      for (let y = startY; y < camY + this.height + CHUNK_SIZE; y += CHUNK_SIZE) {
        ctx.drawImage(chunk, x - camX, y - camY);
      }
    }

    ctx.strokeStyle = 'rgba(255, 45, 80, 0.4)';
    ctx.lineWidth = 3;
    ctx.strokeRect(-camX, -camY, WORLD_W, WORLD_H);

    // 2. Fire Pools on Ground
    if (this.player && this.player.skills.fire_trail.level > 0) {
      const pools = this.player.skills.fire_trail.pools;
      for (let i = 0; i < pools.length; i++) {
        pools[i].draw(ctx, camX, camY);
      }
    }

    // 3. Items & Drops (EXP Gems, Gold Coins, Potions, Magnets)
    for (let i = 0; i < this.xpGems.length; i++) {
      this.xpGems[i].draw(ctx, camX, camY);
    }
    for (let i = 0; i < this.goldCoins.length; i++) {
      this.goldCoins[i].draw(ctx, camX, camY);
    }
    for (let i = 0; i < this.items.length; i++) {
      this.items[i].draw(ctx, camX, camY);
    }

    // 4. Teammates (Co-op & Ranked 3v3)
    this.teammates.forEach((tm) => {
      tm.update();
      tm.draw(ctx, camX, camY);
    });

    // 5. Enemies
    for (let i = 0; i < this.enemies.length; i++) {
      this.enemies[i].draw(ctx, camX, camY);
    }

    // 6. Boss
    if (this.boss && this.boss.alive) {
      this.boss.draw(ctx, camX, camY);
    }

    // 7. Enemy Projectiles
    for (let i = 0; i < this.enemyProjectiles.length; i++) {
      this.enemyProjectiles[i].draw(ctx, camX, camY);
    }

    // 8. Player Slashes & Weapon Projectiles
    for (let i = 0; i < this.slashes.length; i++) {
      this.slashes[i].draw(ctx, camX, camY);
    }
    if (this.player) {
      const s = this.player.skills;
      for (let i = 0; i < s.void.orbs.length; i++) {
        s.void.orbs[i].draw(ctx, camX, camY);
      }
      for (let i = 0; i < s.arrow.arrows.length; i++) {
        s.arrow.arrows[i].draw(ctx, camX, camY);
      }
      for (let i = 0; i < s.hammer.hammers.length; i++) {
        s.hammer.hammers[i].draw(ctx, camX, camY);
      }

      if (s.orb.level >= 1) {
        const count = Math.min(5, 2 + Math.floor(s.orb.level * 0.7));
        const orbRadius = 75 + s.orb.level * 8;
        for (let i = 0; i < count; i++) {
          const a = s.orb.angle + (Math.PI * 2 / count) * i;
          const ox = this.player.x + Math.cos(a) * orbRadius;
          const oy = this.player.y + Math.sin(a) * orbRadius;
          drawAdditiveGlow(ctx, ox - camX, oy - camY, 18, '#4fd8ff', 0.6);
          ctx.fillStyle = '#ffffff';
          ctx.beginPath();
          ctx.arc(ox - camX, oy - camY, 6, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }

    // 9. Shockwaves
    for (let i = 0; i < this.shockwaves.length; i++) {
      this.shockwaves[i].draw(ctx, camX, camY);
    }

    // 10. Particles
    for (let i = 0; i < this.particles.length; i++) {
      this.particles[i].draw(ctx, camX, camY);
    }

    // 11. Player Survivor
    if (this.player) {
      this.player.draw(ctx, camX, camY);
    }

    // 12. Floating Damage Texts & Emojis
    for (let i = 0; i < this.damageTexts.length; i++) {
      this.damageTexts[i].draw(ctx, camX, camY);
    }
    for (let i = 0; i < this.emojiParticles.length; i++) {
      this.emojiParticles[i].draw(ctx, camX, camY);
    }
  }
}

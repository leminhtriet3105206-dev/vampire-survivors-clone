# ⚔️ Legendary Survival — Web Hub & Multiplayer Ecosystem

A full-stack, modular web application and multiplayer hub for **Legendary Survival**, featuring secure user authentication, multi-tier in-game currency management, an anime-inspired character skin shop, and real-time world chat.

---

## 🏗️ Tech Stack

- **Backend:**
  - **Node.js** (v18+) & **Express.js** (REST API & static asset delivery)
  - **MongoDB** & **Mongoose** (ODM, schemas, unique indexes, atomic transactions)
  - **Socket.io** (Bidirectional real-time WebSocket communication for World Chat)
  - **JWT (JSON Web Tokens)** & **bcryptjs** (Stateless authentication & salted hashing)
  - **Helmet** & **express-rate-limit** (Security headers, CSP, brute-force protection)
- **Frontend:**
  - **HTML5** (Semantic structure, accessibility, dialog/modal overlays)
  - **CSS3** (Responsive design, dark fantasy/arcane glassmorphism, procedural anime avatars, glowing currency animations)
  - **Vanilla JavaScript (ES Modules)** (State management, API client, Socket.io client, zero heavy UI frameworks)

---

## 📁 Project Folder Structure

```text
legendary-survival-web/
├── backend/
│   ├── .env.example                  # Environment variables template
│   ├── .env                          # Local environment configuration
│   ├── package.json                  # Dependencies & scripts
│   ├── scripts/
│   │   └── check-syntax.js           # Automated syntax verification across codebase
│   └── src/
│       ├── app.js                    # Express app configuration, middleware & static routing
│       ├── server.js                 # HTTP server bootstrap, Socket.io attachment, graceful shutdown
│       ├── config/
│       │   ├── db.js                 # Mongoose connection management & event listeners
│       │   └── env.js                # Validated environment configuration loader
│       ├── controllers/
│       │   ├── authController.js     # User registration, login & profile lookup
│       │   ├── chatController.js     # Chat history pagination & REST fallback
│       │   ├── shopController.js     # Skin catalogue & atomic purchase logic
│       │   └── userController.js     # Skin equipping & daily reward claims
│       ├── middleware/
│       │   ├── auth.js               # JWT Bearer token authentication guard
│       │   ├── errorHandler.js       # Centralized error handler & JSON formatting
│       │   ├── rateLimiters.js       # Auth brute-force & general API rate limiters
│       │   └── validate.js           # Request payload sanitization & field validators
│       ├── models/
│       │   ├── ChatMessage.js        # Global chat message schema with auto-TTL
│       │   ├── Skin.js               # Anime skin definition & pricing schema
│       │   └── User.js               # User accounts, password hashes & currency balances
│       ├── routes/
│       │   ├── authRoutes.js         # /api/auth endpoints
│       │   ├── chatRoutes.js         # /api/chat endpoints
│       │   ├── index.js              # Aggregated API router & /api/health
│       │   ├── shopRoutes.js         # /api/shop endpoints
│       │   └── userRoutes.js         # /api/users endpoints
│       ├── seed/
│       │   ├── runSeed.js            # Standalone seed executor (`npm run seed`)
│       │   ├── seedSkins.js          # Upsert logic for anime skin catalogue
│       │   └── skins.data.js         # 9 anime-inspired skin definitions
│       ├── sockets/
│       │   ├── chatSocket.js         # Socket.io auth handshake, rate limiting & message broadcasting
│       │   └── roomSocket.js         # Room management, party code generation, co-op sync relays & boss rewards
│       └── utils/
│           ├── AppError.js           # Custom operational error class
│           ├── asyncHandler.js       # Async controller exception wrapper
│           └── jwt.js                # Token signing & verification helpers
├── frontend/
│   ├── index.html                    # Authentication portal (Login & Register)
│   ├── game.html                     # Game hub (Currencies, Profile, Anime Skin Shop, World Chat, Co-op Modals & Canvas)
│   ├── assets/
│   │   └── favicon.svg               # Vector brand emblem
│   ├── css/
│   │   ├── auth.css                  # Auth card, tabs, input states & layout
│   │   ├── base.css                  # CSS variables, typography, buttons, procedural avatars, toasts
│   │   └── game.css                  # Hub layout, skin shop, chat, canvas HUD, co-op lobby & boss bars
│   └── js/
│       ├── api.js                    # Fetch wrapper, error translation & session persistence
│       ├── auth.js                   # Auth form handling, input validation & redirects
│       ├── chat.js                   # Socket.io client, live chat feed, auto-scroll & typing counter
│       ├── currency.js               # Real-time animated currency count updates
│       ├── engine.js                 # 2D Canvas Action Survival Engine (Solo & Co-op Multiplayer, Lich King Boss)
│       ├── game.js                   # Hub bootstrap, battle orchestration & daily reward claims
│       ├── multiplayer.js            # Real-Time Co-op Dungeon room lobby, ready state & party synchronization
│       ├── shop.js                   # Skin catalogue rendering, currency/rarity filters, purchase dialogs
│       ├── store.js                  # Lightweight reactive observable client store
│       └── ui.js                     # DOM builder, notifications (toasts), procedural avatars
└── README.md                         # This documentation file
```

---

## 🎮 Core Features

### 1. User Authentication System
- **Registration & Login:** Clean tabbed UI with live field validation (username format, email regex, password strength).
- **Security:**
  - Passwords hashed with **bcryptjs** (configurable salt rounds, default 12).
  - Passwords marked `select: false` in Mongoose so they are never leaked in queries.
  - Case-insensitive username lookup with `usernameLower` unique index to prevent duplicate identities.
  - JWT tokens issued upon login/registration, validated via `requireAuth` middleware.
  - Rate limiting on `/api/auth/*` protects against brute-force credential stuffing.

### 2. In-Game Currency System
- **Three Currencies:**
  - 🪙 **Gold:** Earned through gameplay and daily claims; used for starter and standard skins.
  - 💎 **Diamonds:** Premium currency for Epic and Legendary anime skins.
  - 🔻 **Rubies:** Ultra-rare prestige currency for Legendary and Mythic transformations.
- **Visual Feedback:**
  - Custom CSS vector icons (no image asset dependencies).
  - Smooth animated number counters that tick up when rewards are claimed and pulse red/green upon spend/gain.
- **Daily Rewards:**
  - Players can claim a daily bounty (+500 Gold, +10 Diamonds, +2 Rubies) once every 24 hours.
  - Enforced atomically in MongoDB to eliminate double-claim race conditions.

### 3. Anime Skin Shop
- **Rich Catalogue:** 9 distinct anime-inspired character outfits:
  1. *Wandering Survivor* (Common - Free Starter)
  2. *Shadow Shinobi* (Rare - 800 Gold) — Inspired by ninja anime
  3. *Crimson Flame Slayer* (Rare - 1,200 Gold) — Inspired by demon hunter anime
  4. *Wall Scout Regiment* (Epic - 2,500 Gold) — Inspired by titan scout anime
  5. *Golden Saiyan Warrior* (Epic - 40 Diamonds) — Inspired by martial arts anime
  6. *Thunder Assassin Hunter* (Epic - 55 Diamonds) — Inspired by lightning hunter anime
  7. *Black Soul Reaper* (Legendary - 90 Diamonds) — Inspired by spirit swordsman anime
  8. *Infinity Sorcerer* (Legendary - 12 Rubies) — Inspired by cursed energy anime
  9. *Sun God Pirate King* (Mythic - 25 Rubies) — Inspired by pirate adventure anime
- **Procedural CSS Avatars:** Every skin renders with custom animated cape, aura, hair silhouette, glowing eyes, and character emblems directly in CSS.
- **Race-Safe Purchases:**
  - Purchases use conditional atomic queries (`findOneAndUpdate` checking `balance >= price` and `$ne: ownedSkins`).
  - Balances can never drop below zero even under rapid concurrent requests.
- **Wardrobe & Equip:** Players can equip any unlocked skin at any time; equipped skin updates in the player profile and displays next to their messages in World Chat.

### 4. Real-Time World Chat
- **WebSocket Powered:** Uses **Socket.io** with handshake authentication using the player's JWT token.
- **Live Features:**
  - Automatic chat history loaded upon connecting (last 50 messages).
  - Real-time online user count broadcasting.
  - Messages display the sender's username, timestamp, and their currently equipped anime skin avatar.
  - Anti-spam rate limiting (minimum 800ms between messages, maximum 300 characters).
  - Control character sanitization and safe DOM insertion (`textContent` only) preventing XSS attacks.

### 5. 2D Action Survival Engine (Phase 2 Gameplay)
- **HTML5 Canvas & 60 FPS Loop:** High-performance top-down action engine built in Vanilla JS using `requestAnimationFrame` with delta-time smoothing.
- **Camera Tracking:** The player remains centered on-screen while an infinite dark arcane grid with scrolling coordinate runes and drifting dust particles moves relative to the player.
- **Fluid Controls:** 8-directional movement mapped to WASD and Arrow Keys with vector normalization.
- **Auto-Aim Combat:** Automatically targets and fires glowing energy projectiles toward the nearest enemy in range. Projectile counts scale into multi-shot spreads as the player levels up.
- **Anime Skin Visual Integration:** The player's canvas model, cape colors, aura glow, and projectile effects dynamically adapt to the currently equipped Anime Skin.
- **Procedural Enemy Waves:** Bats, skeletons, and armored golems spawn just outside the camera viewport, pathfinding towards the player with flocking/separation physics.
- **Loot & Leveling:** Slain enemies drop EXP gems and Gold coins with magnetic attraction physics. Leveling up heals the player, expands weapon damage, increases fire rate, and upgrades projectile count.
- **Match Resolution & Bank Sync:** When defeated, the game over modal displays survival time, kills, and gold collected, saving the earned gold to MongoDB via `POST /api/users/me/add-gold` and smoothly returning to the Hub with live currency animations.

### 6. Phase 3: Real-Time Co-op Dungeon (Multiplayer)
- **Room-Based Party Management:**
  - Create a private party room with an auto-generated 5-character room code (e.g., `X7B9Q`).
  - Friends join via the room code from the Hub modal.
  - Room Lobby shows 4 player slots with their equipped anime avatars, Host badge, and Ready check toggles.
  - The Host's "START DUNGEON" button unlocks only when all party members are marked Ready.
- **Real-Time Canvas Synchronization:**
  - Position, velocity, facing angle, and health are synchronized across clients at 20Hz.
  - Teammates render on the canvas using their equipped anime skin colors, emblem, and floating username pill + health bar above their heads.
  - Attack projectile visuals are mirrored so you see your teammates firing magic and energy beams in real time.
- **Shared Objective & Lich King Boss:**
  - Shared quest objective: *"Slay Monsters: 0 / 100"*. Every kill by any player increments the shared counter.
  - Reaching 100 kills summons the giant **Lich King Boss** (`maxHp: 4500`, radius: 42, dark violet pulsating aura, spiked Lich Crown, and frost nova projectile bursts).
  - Prominent Lich King Health Bar appears at the top of the screen.
- **Host-Authoritative Enemy Simulation:**
  - The Host's client authoritatively calculates enemy physics and broadcasts snapshots to non-host clients (~20Hz), eliminating desyncs.
  - Non-hosts forward hit events to the Host (`room:enemyHit`) while rendering instant responsive damage numbers and spark VFX locally.
- **Victory & Premium Diamond Reward:**
  - When the Lich King is vanquished, the server atomically awards **+15 Diamonds** in MongoDB to all room participants.
  - A celebratory Victory Modal overlay appears with an animated crown, granting 15 Diamonds and counting down 5s before safely returning players to the Web Hub with their updated balance!

### 7. Phase 4: 3v3 Ranked Matchmaking (PvE Score Race) & Ranked Rewards
- **3v3 Matchmaking Queue:**
  - Click **"🏆 RANKED 3v3"** from the Web Hub to enter the Matchmaking Queue with an animated radar scanning effect.
  - When 6 players join (or upon clicking *"⚡ Fill AI Competitors & Start"* for instant solo testing), the server matches them into **Team Red** (3 players) and **Team Blue** (3 players) and seamlessly transitions everyone into the battlefield.
- **Live PvE Score Race Rules (180 Seconds):**
  - Match duration is exactly 3 minutes (180s).
  - Teams cannot hit each other directly; they race to accumulate points against relentless monster hordes.
  - **Scoring:**
    - Normal Enemy Kill: **+10 Points**
    - Elite Enemy Kill (`BRUTE`): **+100 Points**
    - Boss Kill: **+1,000 Points**
  - **Live Scoreboard:** Prominent HUD bar displaying `[RED: 4500] - 02:45 - [BLUE: 4200]` synchronized at 10Hz/1s intervals.
- **ELO Progression & Ruby Rewards:**
  - Match resolution evaluated at 0:00:
    - **Victory:** **+25 RP** & **+5 Rubies** 🔻
    - **Defeat:** **-15 RP** (minimum 0) & **0 Rubies**
    - **Draw / Tie:** **+5 RP** & **+1 Ruby** 🔻
  - **Rank Tiers in MongoDB:**
    - `< 100 RP`: 🥉 **Bronze**
    - `100 - 299 RP`: 🥈 **Silver**
    - `300 - 599 RP`: 🥇 **Gold**
    - `600+ RP`: 💎 **Diamond**
  - Rank Badge displays in the player Profile, top bar, and alongside chat messages.
- **Ruby Shop & Prestige Avatar Frames:**
  - Activated "Rubies" shop tab with Mythic skins and exclusive animated Avatar Frames:
    - *Sun God Pirate King* (Mythic Skin - 25 Rubies)
    - *Infinity Sorcerer* (Legendary Skin - 12 Rubies)
    - *Glowing Diamond Frame* (15 Rubies) — Crystalline pulsing cyan border.
    - *Challenger Fire Frame* (30 Rubies) — Radiant animated flame border with embers.
  - Players can equip frames via `PATCH /api/users/me/equipped-frame` and show them off across the Hub, World Chat, and Battle HUD.
- **In-Game Interactive Emojis:**
  - Keys `1`, `2`, `3`, `4`, `5` (or clicking the bottom HUD quick bar) trigger instant taunts:
    - `1`: 😡 (Rage)
    - `2`: 😭 (Tears)
    - `3`: 💀 (Skull)
    - `4`: ❤️ (Love)
    - `5`: 🤡 (Clown)
  - Floating speech bubbles with team-colored borders float upward over the player's head for 2 seconds, visible to both allies and opponents in real time!

---

## 🚀 Getting Started

### Prerequisites
- **Node.js** (v18.0.0 or higher recommended)
- **MongoDB** (A local MongoDB instance running on `localhost:27017` OR a free cloud cluster on [MongoDB Atlas](https://www.mongodb.com/atlas))

---

### Step 1: Install Backend Dependencies

Open your terminal, navigate to the `backend` folder, and install packages:

```bash
cd legendary-survival-web/backend
npm install
```

---

### Step 2: Configure Environment Variables

Create your `.env` file in `legendary-survival-web/backend/`:

```bash
# On Windows PowerShell:
Copy-Item .env.example .env

# On Linux/macOS:
cp .env.example .env
```

Review the values in `.env`:

```ini
NODE_ENV=development
PORT=3000

# Local MongoDB:
MONGODB_URI=mongodb://127.0.0.1:27017/legendary_survival

# OR MongoDB Atlas (replace with your credentials):
# MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.mongodb.net/legendary_survival?retryWrites=true&w=majority

# Strong random secret for JWT signing
JWT_SECRET=your_super_secret_random_key_here

JWT_EXPIRES_IN=7d
BCRYPT_ROUNDS=12

# Starting balance for new accounts
STARTING_GOLD=1500
STARTING_DIAMONDS=60
STARTING_RUBIES=10
```

---

### Step 3: Start MongoDB

- **If using local MongoDB:** Ensure the MongoDB service is running:
  ```powershell
  # Windows service:
  net start MongoDB
  # Or run mongod directly:
  mongod --dbpath <path-to-data-dir>
  ```
- **If using MongoDB Atlas:** Paste your connection string into `MONGODB_URI` in `.env`.

---

### Step 4: Run the Application

From `legendary-survival-web/backend/`:

```bash
# Start in production mode:
npm start

# OR start in development mode with auto-reload:
npm run dev
```

When started, the server automatically connects to MongoDB, seeds the anime skin catalogue, and serves both the REST API and the frontend at:

👉 **`http://localhost:3000`**

Open `http://localhost:3000` in your web browser:
1. Register a new account (comes pre-loaded with starting Gold, Diamonds, and Rubies).
2. Browse the **Anime Skin Shop**, purchase outfits, and click **Equip**.
3. Claim your **Daily Reward** from the top bar.
4. Send messages in **World Chat** (open multiple browser windows to see real-time updates).

---

## 📡 API Reference

### Authentication (`/api/auth`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/auth/register` | Create account `{ username, email, password, confirmPassword }` | No |
| `POST` | `/api/auth/login` | Login `{ identifier, password }` (username or email) | No |
| `GET` | `/api/auth/me` | Fetch authenticated user profile & balances | Yes (Bearer) |

### Skin Shop (`/api/shop`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/shop/skins` | List all active anime skins & prices | No |
| `POST` | `/api/shop/skins/:slug/purchase` | Purchase skin with appropriate currency | Yes (Bearer) |

### User Actions (`/api/users`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `PATCH` | `/api/users/me/equipped-skin` | Equip an owned skin `{ slug }` | Yes (Bearer) |
| `PATCH` | `/api/users/me/equipped-frame` | Equip an owned avatar frame `{ slug }` | Yes (Bearer) |
| `POST` | `/api/users/me/daily-reward` | Claim 24h currency bonus | Yes (Bearer) |
| `POST` | `/api/users/me/add-gold` | Bank gold collected from a survival match `{ gold }` | Yes (Bearer) |
| `POST` | `/api/users/me/add-diamonds` | Bank diamonds earned from Co-op Boss `{ diamonds }` | Yes (Bearer) |

### Admin & GM Actions (`/api/admin`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/admin/users` | List all registered users (role, currencies, buffs) | Admin (Bearer) |
| `POST` | `/api/admin/give-currency` | Adjust user currency `{ targetUsername, currencyType, amount }` | Admin (Bearer) |
| `POST` | `/api/admin/set-stats` | Set player power buffs `{ targetUsername, bonusHp, bonusDamage }` | Admin (Bearer) |

### Chat (`/api/chat`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/chat/messages?limit=50` | REST fallback to fetch recent chat messages | Yes (Bearer) |

---

## 🔌 Socket.io Events

- **Handshake:** Connect with `{ auth: { token: "<JWT>" } }`.
- **World Chat & GM Commands:**
  - `chat:send`: Normal player messages broadcast to all survivors.
  - **GM Chat Commands (Admin Only):** Intercepted on `/`. Command `/give [username] [currency] [amount]` (e.g., `/give Player1 gold 5000`) atomically modifies target currency in MongoDB, sends private `chat:systemMessage` confirmation to the GM, and emits `admin:currencyReceived` to update the recipient's balance in real time.
- **Co-op Dungeon (Phase 3):**
  - `room:create`, `room:join`, `room:ready`, `room:start`, `room:leave`
  - Relays: `room:playerMove`, `room:playerAttack`, `room:enemiesUpdate`, `room:enemyHit`, `room:bossDefeated`, `room:victory`
- **Ranked 3v3 Matchmaking (Phase 4):**
  - `ranked:joinQueue` / `ranked:leaveQueue`: Join or exit the 6-player queue.
  - `ranked:fillQueueBots`: Instantly fills remaining slots with AI contenders for solo testing.
  - `ranked:queueStatus`: Broadcasts current queue size (`{ queueSize, target: 6 }`).
  - `ranked:matchFound`: Broadcasts match start with assigned team and full rosters.
  - `ranked:scoreUpdate`: Emitted on enemy kills (+10 normal, +100 elite, +1000 boss).
  - `ranked:scoreSync`: Broadcasts live aggregated Red and Blue scores and timer at 10Hz/1s.
  - `ranked:emoji`: Emitted on keys 1-5 taunt input (`['😡', '😭', '💀', '❤️', '🤡']`).
  - `ranked:emojiBroadcast`: Broadcasts floating emoji event to all match participants.
  - `ranked:playerMove` & `ranked:playerAttack`: Synchronizes 6-player positions and projectiles.
  - `ranked:matchEnded`: Emitted at 0:00, resolving winner, updating RP (+25 / -15) and Rubies (+5 / 0), and showing the victory/defeat results overlay.

### 6. AAA Dark Fantasy "Arcane Obsidian & Gold" UI & Ported Skills
- **Arcane Obsidian & Gold Theme:**
  - Replaces standard dashboard colors with deep obsidian/charcoal gradients (`#07080b` to `#161b24`), metallic gold beveled borders (`linear-gradient(135deg, #fce881, #cba135, #6e5016, #ffd34d)`), and sharp clipped corners (`clip-path: polygon(...)`).
  - Panels, headers, and cards feature chiseled typography, gold drop shadows, and subtle radial ambient glows.
- **48x48 Metallic Frame SVG Skill Icons:**
  - Replaces text-only skill descriptions with crisp, performant vector SVGs inside 48x48 glowing metallic gold frames.
  - Implemented across the Anime Skin Shop (highlighting each character's Signature Weapon), the Survivor Profile panel, and the In-Game Ascension Level-Up modal.
- **Survivor Ascension Level-Up Modal Overlay:**
  - Pauses the canvas battlefield on level-up and displays a dark fantasy overlay with **3 vertical reward cards**.
  - Each card displays a 48x48 glowing skill icon, stylized gold title, current vs next level badge (`Lv. X ➔ Lv. Y` or `✨ NEW WEAPON`), stat upgrades, and golden hover-glow interaction that resumes the game on selection.
- **Authentic Canvas Skill Mechanics & High-Performance Additive Blending:**
  - **Blood Moon Slash (`WhipWeapon`):** Multi-layered jagged crescent energy arcs (`math.sin(frac * math.pi)` + energy teeth) with blood particle spray and lifesteal heals (+HP green floating text).
  - **Void Singularity (`VoidSingularityWeapon` / `SingularityOrb`):** Gravitational vortex drawing enemies toward an event horizon, rotating hexagram runes, and an implosion Cosmic Nova shockwave.
  - **Thunderstorm (`LightningStaffWeapon` / `LightningBolt`):** Procedural midpoint displacement jagged lightning bolts striking from the sky with electric chain jumps and electromagnetic ground shockwaves.
  - **Celestial Orbs (`OrbWeapon`):** Orbiting magic shields with breathing radius oscillation (`radius * (0.72 + 0.38 * sin(pulsePhase))`), connecting energy beams, knockback, and hexagram magic seals.
  - **Additive Blending (`globalCompositeOperation = 'lighter'`):** Applied to all skill VFX, projectiles, and shockwaves for dazzling neon arcade pop at consistent 60 FPS.

---

## 🛡️ Verification & Code Quality

Run the built-in syntax checker and smoke test suite to verify all backend and frontend files:

```bash
cd legendary-survival-web/backend
npm run check
npm test
```


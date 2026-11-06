// Small DOM helpers: element builder, toasts, confirm modal, skin avatar renderer, and SVG skill icons.

export const CURRENCY_META = {
  gold: { label: 'Gold', className: 'cur-gold' },
  diamonds: { label: 'Diamonds', className: 'cur-diamond' },
  rubies: { label: 'Rubies', className: 'cur-ruby' },
};

export const RARITY_LABEL = {
  common: 'Common',
  rare: 'Rare',
  epic: 'Epic',
  legendary: 'Legendary',
  mythic: 'Mythic',
};

export const RANK_META = {
  Bronze: { icon: '🥉', label: 'Bronze', className: 'rank-bronze' },
  Silver: { icon: '🥈', label: 'Silver', className: 'rank-silver' },
  Gold: { icon: '🥇', label: 'Gold', className: 'rank-gold' },
  Diamond: { icon: '💎', label: 'Diamond', className: 'rank-diamond' },
};

/* ── Vector SVG Skill Icons (48x48 AAA Dark Fantasy Style) ── */
export const SKILL_SVGS = {
  whip: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="whip-grad" x1="6" y1="42" x2="42" y2="6" gradientUnits="userSpaceOnUse">
        <stop stop-color="#ff1a40"/>
        <stop offset="0.5" stop-color="#ff6078"/>
        <stop offset="1" stop-color="#ffe4b5"/>
      </linearGradient>
      <radialGradient id="whip-glow" cx="24" cy="24" r="20" gradientUnits="userSpaceOnUse">
        <stop stop-color="#ff2e54" stop-opacity="0.6"/>
        <stop offset="1" stop-color="#ff2e54" stop-opacity="0"/>
      </radialGradient>
    </defs>
    <circle cx="24" cy="24" r="18" fill="url(#whip-glow)"/>
    <path d="M10 38C12 28 20 14 38 8C33 16 28 22 26 28C24 33 22 36 10 38Z" fill="url(#whip-grad)"/>
    <path d="M16 35C22 26 28 17 41 7C36 18 31 25 24 31C20 34 18 35 16 35Z" fill="#ffffff" fill-opacity="0.75"/>
    <path d="M7 41L13 35M12 43L17 38" stroke="#ff8095" stroke-width="2" stroke-linecap="round"/>
    <path d="M28 16L32 14M22 22L25 20M18 29L20 27" stroke="#ffc0cb" stroke-width="1.8" stroke-linecap="round"/>
    <circle cx="39" cy="9" r="2.5" fill="#fff"/>
  </svg>`,

  void: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="void-grad" x1="8" y1="8" x2="40" y2="40" gradientUnits="userSpaceOnUse">
        <stop stop-color="#b854ff"/>
        <stop offset="0.5" stop-color="#55e2ff"/>
        <stop offset="1" stop-color="#8033ff"/>
      </linearGradient>
      <radialGradient id="void-center" cx="24" cy="24" r="8" gradientUnits="userSpaceOnUse">
        <stop stop-color="#090514"/>
        <stop offset="0.75" stop-color="#150a2b"/>
        <stop offset="1" stop-color="#9340ff"/>
      </radialGradient>
    </defs>
    <circle cx="24" cy="24" r="20" stroke="#7928ca" stroke-width="1.2" stroke-dasharray="3 3"/>
    <path d="M24 10C31 10 37 15 37 22C37 28 32 32 26 31C21 30 19 26 20 22C21 19 24 19 24 21" stroke="url(#void-grad)" stroke-width="2.6" stroke-linecap="round"/>
    <path d="M24 38C17 38 11 33 11 26C11 20 16 16 22 17C27 18 29 22 28 26C27 29 24 29 24 27" stroke="url(#void-grad)" stroke-width="2.6" stroke-linecap="round"/>
    <circle cx="24" cy="24" r="8.5" fill="url(#void-center)" stroke="#55e2ff" stroke-width="1.5"/>
    <circle cx="24" cy="24" r="3" fill="#ffffff" fill-opacity="0.9"/>
    <circle cx="12" cy="14" r="1.5" fill="#55e2ff"/>
    <circle cx="36" cy="34" r="1.5" fill="#ff79c6"/>
    <circle cx="37" cy="15" r="1.2" fill="#fff"/>
  </svg>`,

  lightning: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="light-grad" x1="14" y1="4" x2="34" y2="44" gradientUnits="userSpaceOnUse">
        <stop stop-color="#fff8cc"/>
        <stop offset="0.3" stop-color="#ffe153"/>
        <stop offset="0.7" stop-color="#4fd8ff"/>
        <stop offset="1" stop-color="#1a8cff"/>
      </linearGradient>
    </defs>
    <path d="M28 4L12 24H24L18 44L36 20H24L28 4Z" fill="url(#light-grad)"/>
    <path d="M26 8L15 23H24L20 38L32 21H24L26 8Z" fill="#ffffff" fill-opacity="0.85"/>
    <path d="M12 18L7 21M34 28L41 26M14 36L8 39M32 10L37 7" stroke="#6be5ff" stroke-width="1.8" stroke-linecap="round"/>
  </svg>`,

  orb: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="orb-grad" x1="10" y1="10" x2="38" y2="38" gradientUnits="userSpaceOnUse">
        <stop stop-color="#6df5ff"/>
        <stop offset="0.5" stop-color="#9a5eff"/>
        <stop offset="1" stop-color="#ff7ee5"/>
      </linearGradient>
    </defs>
    <circle cx="24" cy="24" r="14" stroke="#4fd8ff" stroke-width="1.2" stroke-opacity="0.5"/>
    <polygon points="24,12 34,29 14,29" stroke="#9a5eff" stroke-width="1.4" fill="none"/>
    <polygon points="24,36 14,19 34,19" stroke="#9a5eff" stroke-width="1.4" fill="none"/>
    <circle cx="24" cy="24" r="3.5" fill="#ffffff"/>
    <g transform="rotate(25 24 24)">
      <circle cx="24" cy="7" r="5" fill="#4fd8ff" stroke="#fff" stroke-width="1.5"/>
      <circle cx="9" cy="33" r="5" fill="#9a5eff" stroke="#fff" stroke-width="1.5"/>
      <circle cx="39" cy="33" r="5" fill="#ff7ee5" stroke="#fff" stroke-width="1.5"/>
    </g>
    <ellipse cx="24" cy="24" rx="19" ry="19" stroke="#ffd34d" stroke-width="1" stroke-dasharray="2 4" stroke-opacity="0.6"/>
  </svg>`,

  might: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="might-grad" x1="10" y1="38" x2="38" y2="10" gradientUnits="userSpaceOnUse">
        <stop stop-color="#ffb830"/>
        <stop offset="0.6" stop-color="#fff0a0"/>
        <stop offset="1" stop-color="#ff4757"/>
      </linearGradient>
    </defs>
    <path d="M37 7L41 11L22 30L18 26L37 7Z" fill="url(#might-grad)"/>
    <path d="M35 9L39 13L24 28L20 24L35 9Z" fill="#fff" fill-opacity="0.8"/>
    <path d="M14 26L26 38L22 41L11 29L14 26Z" fill="#966f1e" stroke="#ffe27a" stroke-width="1.2"/>
    <path d="M14 36L8 42" stroke="#5a3810" stroke-width="3" stroke-linecap="round"/>
    <circle cx="7" cy="43" r="2.5" fill="#ffd34d" stroke="#fff" stroke-width="1"/>
    <line x1="28" y1="13" x2="33" y2="18" stroke="#ff4757" stroke-width="2"/>
  </svg>`,

  vitality: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="shield-grad" x1="12" y1="6" x2="36" y2="42" gradientUnits="userSpaceOnUse">
        <stop stop-color="#3ddc97"/>
        <stop offset="0.5" stop-color="#149360"/>
        <stop offset="1" stop-color="#0a4d32"/>
      </linearGradient>
    </defs>
    <path d="M24 6L38 12V24C38 33 24 42 24 42C24 42 10 33 10 24V12L24 6Z" fill="url(#shield-grad)" stroke="#a3f7bf" stroke-width="2"/>
    <path d="M24 14V34M16 22H32" stroke="#ffe27a" stroke-width="3.5" stroke-linecap="round"/>
    <circle cx="24" cy="22" r="3.5" fill="#ffffff"/>
    <path d="M15 15L24 10L33 15" stroke="#ffffff" stroke-width="1.5" stroke-linecap="round" fill="none" opacity="0.6"/>
  </svg>`,

  speed: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="boot-grad" x1="8" y1="12" x2="40" y2="38" gradientUnits="userSpaceOnUse">
        <stop stop-color="#ffe66d"/>
        <stop offset="0.6" stop-color="#ff9f1c"/>
        <stop offset="1" stop-color="#e71d36"/>
      </linearGradient>
    </defs>
    <path d="M14 14L22 10L26 24L38 27C41 28 42 32 39 34L32 38H18L14 30V14Z" fill="url(#boot-grad)" stroke="#fff" stroke-width="1.2"/>
    <path d="M14 16C8 12 6 22 12 26C8 28 10 34 16 33" stroke="#ffe27a" stroke-width="2.2" stroke-linecap="round" fill="none"/>
    <path d="M9 13C16 11 20 18 20 22" stroke="#ffffff" stroke-width="1.8" stroke-linecap="round"/>
    <path d="M4 36H12M8 40H16M6 32H10" stroke="#4fd8ff" stroke-width="1.6" stroke-linecap="round"/>
  </svg>`,

  magnet: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="mag-blue" x1="10" y1="10" x2="20" y2="38" gradientUnits="userSpaceOnUse">
        <stop stop-color="#4fd8ff"/>
        <stop offset="1" stop-color="#0066cc"/>
      </linearGradient>
      <linearGradient id="mag-red" x1="28" y1="10" x2="38" y2="38" gradientUnits="userSpaceOnUse">
        <stop stop-color="#ff4d6d"/>
        <stop offset="1" stop-color="#a00028"/>
      </linearGradient>
    </defs>
    <path d="M12 18V28C12 34.6 17.4 40 24 40C30.6 40 36 34.6 36 28V18H28V28C28 30.2 26.2 32 24 32C21.8 32 20 30.2 20 28V18H12Z" fill="#24213d" stroke="#5f588d" stroke-width="1.5"/>
    <rect x="12" y="8" width="8" height="12" rx="1.5" fill="url(#mag-blue)"/>
    <text x="14" y="17" font-size="8" font-weight="900" fill="#fff" font-family="sans-serif">N</text>
    <rect x="28" y="8" width="8" height="12" rx="1.5" fill="url(#mag-red)"/>
    <text x="30" y="17" font-size="8" font-weight="900" fill="#fff" font-family="sans-serif">S</text>
    <path d="M16 6C20 4 28 4 32 6M13 3C20 0 28 0 35 3" stroke="#ffe153" stroke-width="1.4" stroke-linecap="round" stroke-dasharray="2 3"/>
  </svg>`,

  arrow: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="arrow-grad" x1="6" y1="42" x2="42" y2="6" gradientUnits="userSpaceOnUse">
        <stop stop-color="#32ffa0"/>
        <stop offset="0.6" stop-color="#00e575"/>
        <stop offset="1" stop-color="#ffffff"/>
      </linearGradient>
    </defs>
    <path d="M42 6L28 12L36 20L42 6Z" fill="url(#arrow-grad)"/>
    <path d="M32 16L14 34" stroke="#32ffa0" stroke-width="3" stroke-linecap="round"/>
    <path d="M8 40L14 34M10 42L16 36M6 38L12 32" stroke="#00b359" stroke-width="2" stroke-linecap="round"/>
    <circle cx="36" cy="12" r="2" fill="#fff"/>
  </svg>`,

  hammer: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="ham-grad" x1="8" y1="8" x2="40" y2="40" gradientUnits="userSpaceOnUse">
        <stop stop-color="#fff59d"/>
        <stop offset="0.4" stop-color="#ffd54f"/>
        <stop offset="1" stop-color="#ff8f00"/>
      </linearGradient>
    </defs>
    <rect x="18" y="8" width="22" height="14" rx="3" transform="rotate(45 29 15)" fill="url(#ham-grad)" stroke="#fff" stroke-width="1.5"/>
    <line x1="20" y1="24" x2="8" y2="36" stroke="#cbb482" stroke-width="4.5" stroke-linecap="round"/>
    <circle cx="6" cy="38" r="2.5" fill="#ffd54f"/>
    <path d="M26 12L34 20M32 10L36 14" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/>
  </svg>`,

  aura: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="18" stroke="#b388ff" stroke-width="2" stroke-dasharray="4 2"/>
    <circle cx="24" cy="24" r="11" fill="#7c4dff" fill-opacity="0.35" stroke="#ea80fc" stroke-width="1.8"/>
    <circle cx="24" cy="24" r="4" fill="#ffffff"/>
    <path d="M24 6V10M24 38V42M6 24H10M38 24H42" stroke="#ea80fc" stroke-width="2.5" stroke-linecap="round"/>
  </svg>`,

  boomerang: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M8 20C12 8 28 6 38 10C34 16 26 22 18 26L8 20Z" fill="#00e5ff" stroke="#fff" stroke-width="1.5"/>
    <path d="M18 26C22 34 28 42 40 38C36 30 30 24 24 18L18 26Z" fill="#7c4dff" stroke="#fff" stroke-width="1.5"/>
    <circle cx="21" cy="22" r="3" fill="#ffe57f"/>
  </svg>`,

  fire_trail: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M24 4C28 14 38 20 38 30C38 38 32 44 24 44C16 44 10 38 10 30C10 22 18 16 24 4Z" fill="#ff3d00"/>
    <path d="M24 16C27 22 32 26 32 32C32 36 28 40 24 40C20 40 16 36 16 32C16 27 21 24 24 16Z" fill="#ffea00"/>
    <circle cx="24" cy="34" r="3.5" fill="#ffffff"/>
  </svg>`,

  ice_wand: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <line x1="12" y1="36" x2="32" y2="16" stroke="#90caf9" stroke-width="3.5" stroke-linecap="round"/>
    <polygon points="36,8 42,14 36,20 30,14" fill="#00e5ff" stroke="#fff" stroke-width="1.5"/>
    <circle cx="36" cy="14" r="2.5" fill="#fff"/>
  </svg>`,

  armor: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M24 6L38 12V24C38 34 24 42 24 42C24 42 10 34 10 24V12L24 6Z" fill="#455a64" stroke="#cfd8dc" stroke-width="2"/>
    <path d="M24 12V36M16 22H32" stroke="#b0bec5" stroke-width="2"/>
    <circle cx="24" cy="22" r="3" fill="#eceff1"/>
  </svg>`,

  recovery: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M24 38L12 26C8 22 8 16 12 12C16 8 22 8 24 14C26 8 32 8 36 12C40 16 40 22 36 26L24 38Z" fill="#00e676" stroke="#b9f6ca" stroke-width="2"/>
    <path d="M24 18V28M19 23H29" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>
  </svg>`,

  fusion_blood: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="18" fill="#500010" stroke="#ff1744" stroke-width="2.5"/>
    <path d="M12 36C16 20 28 10 36 12C32 24 24 32 12 36Z" fill="#ff5252"/>
    <circle cx="24" cy="24" r="6" fill="#ffebee"/>
  </svg>`,

  fusion_cosmic: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="19" stroke="#00e5ff" stroke-width="2" stroke-dasharray="3 3"/>
    <circle cx="24" cy="24" r="9" fill="#12002b" stroke="#d500f9" stroke-width="2"/>
    <path d="M10 24L20 28L28 20L38 24" stroke="#ffff00" stroke-width="2" stroke-linecap="round"/>
  </svg>`,

  fusion_reaper: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="18" stroke="#00e676" stroke-width="2"/>
    <path d="M14 12C26 10 36 20 34 34C24 30 18 20 14 12Z" fill="#1de9b6"/>
    <path d="M34 12C22 10 12 20 14 34C24 30 30 20 34 12Z" fill="#69f0ae" fill-opacity="0.8"/>
  </svg>`,

  fusion_solar: `<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="12" fill="#ff6d00" stroke="#ffd600" stroke-width="3"/>
    <path d="M24 2V8M24 40V46M2 24H8M40 24H46M8 8L13 13M35 35L40 40M8 40L13 35M35 13L40 8" stroke="#ffab00" stroke-width="2.5" stroke-linecap="round"/>
  </svg>`,
};

export const SKILL_META = {
  whip: {
    key: 'whip',
    name: 'Trảm Huyết Nguyệt',
    category: 'Vũ Khí',
    iconKey: 'whip',
    description: 'Chém lưỡi liềm huyết nguyệt đỏ thẫm hình cánh cung, gây sát thương diện rộng và hồi máu theo % sát thương gây ra.',
    statUpgrade: '+35% Cự Ly, +16 Sát Thương, +5% Hút Máu',
    color: '#ff2e54',
  },
  void: {
    key: 'void',
    name: 'Hố Đen Hư Không',
    category: 'Vũ Khí',
    iconKey: 'void',
    description: 'Triệu hồi hố đen trọng lực hút bầy quái về tâm điểm, thiêu đốt liên tục rồi phát nổ hủy diệt.',
    statUpgrade: '+25% Bán Kính Hút, +22 Sát Thương, Nổ Hư Không',
    color: '#b854ff',
  },
  arrow: {
    key: 'arrow',
    name: 'Mưa Tên Độc Ảnh',
    category: 'Vũ Khí',
    iconKey: 'arrow',
    description: 'Bắn loạt tên ngọc bích ma ảo xuyên thấu và nảy bật giữa các quái vật, gây độc lan rộng.',
    statUpgrade: '+1 Mũi Tên, +1 Lần Bật, +15 Sát Thương Chí Mạng',
    color: '#32ffa0',
  },
  hammer: {
    key: 'hammer',
    name: 'Phán Quyết Ánh Sáng',
    category: 'Vũ Khí',
    iconKey: 'hammer',
    description: 'Triệu hồi búa thần hoàng kim xoay tròn mở rộng theo quỹ đạo xoắn ốc quanh người chơi, nghiền nát quân đoàn quái.',
    statUpgrade: '+1 Búa Hoàng Kim, +20 Sát Thương, Giật Sét Thánh',
    color: '#ffd54f',
  },
  orb: {
    key: 'orb',
    name: 'Khiên Tinh Cầu',
    category: 'Vũ Khí',
    iconKey: 'orb',
    description: 'Xoay các tinh cầu ma pháp bảo hộ quanh người chơi, chém tan bầy quái áp sát.',
    statUpgrade: '+1 Quả Cầu, +14 Sát Thương, +20 Bán Kính',
    color: '#4fd8ff',
  },
  aura: {
    key: 'aura',
    name: 'Trường Lực Thánh',
    category: 'Vũ Khí',
    iconKey: 'aura',
    description: 'Tạo vùng hào quang thần thánh xung quanh liên tục thiêu đốt toàn bộ kẻ địch bước vào.',
    statUpgrade: '+30 Bán Kính, +15 Sát Thương Mỗi Giây',
    color: '#b388ff',
  },
  boomerang: {
    key: 'boomerang',
    name: 'Lưỡi Hái Tử Thần',
    category: 'Vũ Khí',
    iconKey: 'boomerang',
    description: 'Phóng lưỡi hái tử thần bay lượn xuyên qua hàng ngũ kẻ địch rồi quay trở lại tay.',
    statUpgrade: '+1 Lưỡi Hái, +22 Sát Thương, +15% Tốc Độ Bay',
    color: '#00e5ff',
  },
  lightning: {
    key: 'lightning',
    name: 'Bão Sấm Sét',
    category: 'Vũ Khí',
    iconKey: 'lightning',
    description: 'Giáng sấm sét thiên giới từ trên trời xuống kẻ thù, giật sét lan truyền sang các mục tiêu lân cận.',
    statUpgrade: '+1 Mục Tiêu Sấm, +2 Tia Lan, +24 Sát Thương',
    color: '#ffd34d',
  },
  fire_trail: {
    key: 'fire_trail',
    name: 'Vệt Lửa Địa Ngục',
    category: 'Vũ Khí',
    iconKey: 'fire_trail',
    description: 'Để lại vệt dung nham địa ngục cháy rực theo bước chân người chơi, thiêu rụi lũ quái truy đuổi.',
    statUpgrade: '+30% Thời Gian Tồn Tại Vệt Lửa, +18 Sát Thương',
    color: '#ff3d00',
  },
  ice_wand: {
    key: 'ice_wand',
    name: 'Băng Trượng Tinh Vân',
    category: 'Vũ Khí',
    iconKey: 'ice_wand',
    description: 'Phóng tia băng hà tinh vân đóng băng và làm chậm tốc độ di chuyển của kẻ địch gần nhất.',
    statUpgrade: '+1 Tia Băng, +1.5s Đóng Băng, +15 Sát Thương',
    color: '#90caf9',
  },
  vitality: {
    key: 'vitality',
    name: 'Sinh Lực Tối Đa',
    category: 'Bổ Trợ',
    iconKey: 'vitality',
    description: 'Tăng lượng Máu tối đa và hồi phục ngay một phần sinh lực bị tổn thương.',
    statUpgrade: '+40 Máu Tối Đa, Hồi Ngay 50 Máu',
    color: '#3ddc97',
  },
  speed: {
    key: 'speed',
    name: 'Tốc Độ Di Chuyển',
    category: 'Bổ Trợ',
    iconKey: 'speed',
    description: 'Gia tăng tốc độ chạy giúp linh hoạt né tránh các đợt bao vây của bầy quái.',
    statUpgrade: '+12% Tốc Độ Chạy, +5% Tỉ Lệ Né',
    color: '#ffe153',
  },
  armor: {
    key: 'armor',
    name: 'Giáp Phòng Thủ',
    category: 'Bổ Trợ',
    iconKey: 'armor',
    description: 'Rèn luyện giáp trụ cứng cáp, giảm trực tiếp sát thương nhận vào từ mọi nguồn.',
    statUpgrade: '+2 Giáp Giảm Sát Thương Trực Tiếp',
    color: '#cfd8dc',
  },
  recovery: {
    key: 'recovery',
    name: 'Hồi Phục Sinh Lực',
    category: 'Bổ Trợ',
    iconKey: 'recovery',
    description: 'Tự động phục hồi một lượng máu nhất định theo mỗi giây chiến đấu.',
    statUpgrade: '+1.5 HP Tự Động Phục Hồi / Giây',
    color: '#00e676',
  },
  fusion_blood: {
    key: 'fusion_blood',
    name: 'Huyết Ngục Vĩnh Hằng',
    category: 'Hợp Nhất Thần Thoại',
    iconKey: 'fusion_blood',
    recipeHint: 'Trảm Huyết Nguyệt + Trường Lực Thánh',
    description: 'Hợp nhất tối thượng: Nhát chém huyết nguyệt 4 hướng 360 độ kết hợp trường lực máu tỏa ra hút cạn sinh lực kẻ thù!',
    statUpgrade: 'Thức Tỉnh Thần Thoại: 4 Nhát Chém 360°, Hút Máu 15%, Vực Máu Bất Diệt',
    color: '#ff1744',
  },
  fusion_cosmic: {
    key: 'fusion_cosmic',
    name: 'Bão Từ Trường Vũ Trụ',
    category: 'Hợp Nhất Thần Thoại',
    iconKey: 'fusion_cosmic',
    recipeHint: 'Hố Đen Hư Không + Bão Sấm Sét',
    description: 'Hợp nhất tối thượng: Hố đen vũ trụ hút sạch quái toàn màn hình kết hợp mưa sấm sét giáng liên tục!',
    statUpgrade: 'Thức Tỉnh Thần Thoại: Siêu Hố Đen Hút Toàn Map, Mưa Sấm Thiên Giới',
    color: '#d500f9',
  },
  fusion_reaper: {
    key: 'fusion_reaper',
    name: 'Cơn Lốc Tử Thần',
    category: 'Hợp Nhất Thần Thoại',
    iconKey: 'fusion_reaper',
    recipeHint: 'Mưa Tên Độc Ảnh + Lưỡi Hái Tử Thần',
    description: 'Hợp nhất tối thượng: Mưa tên xé gió kết hợp lưỡi hái tử thần cuồng nộ càn quét mọi phương vị!',
    statUpgrade: 'Thức Tỉnh Thần Thoại: Loạt Tên Độc Tự Nảy + Lưỡi Hái Bão Táp',
    color: '#1de9b6',
  },
  fusion_solar: {
    key: 'fusion_solar',
    name: 'Thái Dương Tận Thế',
    category: 'Hợp Nhất Thần Thoại',
    iconKey: 'fusion_solar',
    recipeHint: 'Phán Quyết Ánh Sáng + Vệt Lửa Địa Ngục',
    description: 'Hợp nhất tối thượng: 4 Búa Thái Dương khổng lồ xoay quanh thiêu đốt toàn bộ mặt đất thành biển lửa mặt trời!',
    statUpgrade: 'Thức Tỉnh Thần Thoại: 4 Búa Mặt Trời, Biển Lửa Thái Dương Thiêu Rụi',
    color: '#ffd600',
  },
};

/** Resolves signature skill metadata for each anime skin */
export function getSkinSignatureSkill(skinSlug) {
  const map = {
    default: SKILL_META.hammer,
    'shadow-shinobi': SKILL_META.arrow,
    'flame-slayer': SKILL_META.whip,
    'titan-scout': SKILL_META.whip,
    'saiyan-warrior': SKILL_META.void,
    'straw-pirate': SKILL_META.hammer,
    'sorcerer-gojo': SKILL_META.void,
    'alchemy-hero': SKILL_META.void,
    'solo-shadow': SKILL_META.whip,
    'chainsaw-devil': SKILL_META.whip,
    'cyber-ronin': SKILL_META.whip,
  };
  return map[skinSlug] || SKILL_META.whip;
}

/** Returns raw SVG string for a skill icon */
export function getSkillIconSvg(iconKey, size = 48) {
  const svg = SKILL_SVGS[iconKey] || SKILL_SVGS.whip;
  return svg.replace('<svg ', `<svg width="${size}" height="${size}" `);
}

/** Returns a DOM node representing a 48x48 glowing metallic framed skill icon */
export function renderSkillIconBadge(iconKey, size = 48, label = '') {
  const frame = el('div', {
    class: 'skill-icon-frame',
    title: label || (SKILL_META[iconKey] ? SKILL_META[iconKey].name : iconKey),
    'aria-label': label || iconKey,
  });
  frame.innerHTML = getSkillIconSvg(iconKey, size);
  return frame;
}

export function rankBadge(tier = 'Bronze', rp = null) {
  const meta = RANK_META[tier] || RANK_META.Bronze;
  const textStr = rp !== null ? `${meta.icon} ${meta.label} (${rp} RP)` : `${meta.icon} ${meta.label}`;
  return el('span', { class: `rank-badge ${meta.className}`, title: `${meta.label} Tier` }, [
    el('span', { class: 'rank-icon', text: meta.icon }),
    el('span', { class: 'rank-text', text: rp !== null ? `${meta.label} (${rp} RP)` : meta.label }),
  ]);
}

/** el('div', { class: 'x', text: 'hi', onclick }, [children]) - never uses innerHTML. */
export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export const formatNumber = (n) => new Intl.NumberFormat('en-US').format(Number(n) || 0);

export function currencyIcon(currency, size = '') {
  const meta = CURRENCY_META[currency] || CURRENCY_META.gold;
  return el('span', { class: `cur-icon ${meta.className} ${size}`.trim(), 'aria-hidden': 'true' });
}

/* ── Toasts ─────────────────────────────────────────────── */
export function toast(message, type = 'info', timeout = 3200) {
  let host = document.getElementById('toast-host');
  if (!host) {
    host = el('div', { id: 'toast-host', 'aria-live': 'polite' });
    document.body.append(host);
  }
  const node = el('div', { class: `toast toast-${type}`, role: 'status', text: message });
  host.append(node);
  requestAnimationFrame(() => node.classList.add('show'));
  setTimeout(() => {
    node.classList.remove('show');
    setTimeout(() => node.remove(), 300);
  }, timeout);
}

/* ── Confirm modal (Promise<boolean>) ───────────────────── */
export function confirmDialog({ title, body, confirmText = 'Confirm', cancelText = 'Cancel' }) {
  return new Promise((resolve) => {
    const close = (result) => {
      overlay.classList.remove('show');
      document.removeEventListener('keydown', onKey);
      setTimeout(() => overlay.remove(), 200);
      resolve(result);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') close(false);
    };
    const confirmBtn = el('button', { class: 'btn btn-primary', type: 'button', text: confirmText, onclick: () => close(true) });
    const overlay = el('div', { class: 'modal-overlay', role: 'dialog', 'aria-modal': 'true' }, [
      el('div', { class: 'modal' }, [
        el('h3', { class: 'modal-title', text: title }),
        el('div', { class: 'modal-body' }, body instanceof Node ? body : el('p', { text: body })),
        el('div', { class: 'modal-actions' }, [
          el('button', { class: 'btn btn-ghost', type: 'button', text: cancelText, onclick: () => close(false) }),
          confirmBtn,
        ]),
      ]),
    ]);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) close(false);
    });
    document.addEventListener('keydown', onKey);
    document.body.append(overlay);
    requestAnimationFrame(() => overlay.classList.add('show'));
    confirmBtn.focus();
  });
}

/* ── Procedural CSS skin avatar ─────────────────────────── */
const FALLBACK_COLORS = { primary: '#7f8cff', secondary: '#2c3170', accent: '#d9defc' };

export function skinAvatar(skin, size = 'md', frameSlug = 'default') {
  const colors = (skin && skin.colors) || FALLBACK_COLORS;
  const frameClass = frameSlug && frameSlug !== 'default' ? ` has-frame frame-${frameSlug.replace(/^frame-/, '')}` : '';
  const node = el('div', { class: `avatar avatar-${size} rarity-${(skin && skin.rarity) || 'common'}${frameClass}`, 'aria-hidden': 'true' }, [
    el('div', { class: 'av-frame' }),
    el('div', { class: 'av-aura' }),
    el('div', { class: 'av-cape' }),
    el('div', { class: 'av-body' }, el('span', { class: 'av-emblem', text: (skin && skin.emblem) || 'S' })),
    el('div', { class: 'av-head' }, [
      el('div', { class: 'av-hair' }),
      el('div', { class: 'av-eye av-eye-l' }),
      el('div', { class: 'av-eye av-eye-r' }),
    ]),
    el('div', { class: 'av-shadow' }),
  ]);
  node.style.setProperty('--p', colors.primary);
  node.style.setProperty('--s', colors.secondary);
  node.style.setProperty('--a', colors.accent);
  return node;
}

/** Puts a button into a loading state; returns a restore function. */
export function setBusy(button, busyText = 'Please wait...') {
  const original = button.textContent;
  button.disabled = true;
  button.classList.add('is-busy');
  button.textContent = busyText;
  return () => {
    button.disabled = false;
    button.classList.remove('is-busy');
    button.textContent = original;
  };
}


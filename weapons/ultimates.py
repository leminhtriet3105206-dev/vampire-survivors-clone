"""Ultimate skill activations and screen-clearing effects for characters and anime skins."""
import math
import random
from typing import Any, List, Optional, Tuple
import pygame

from core.config import C_WHITE, SCREEN_H, SCREEN_W
from core.i18n import T
from gfx.vfx import ShockwaveRing, draw_additive_glow, draw_jagged_lightning_arc
from pooling.damage_number_pool import DamageNumberPool, PooledDamageNumber
from pooling.particle_pool import ParticlePool, PooledParticle
from spatial.math_utils import clamp, dist, dist_to_segment, lerp, norm

# Aliases for compatibility
Particle = PooledParticle
DamageNumber = PooledDamageNumber

class ActiveUltimate:
    """
    Quản lý hoạt ảnh, hiệu ứng VFX đa lớp và sát thương huỷ diệt của Kỹ Năng Tối Thượng (Ultimate Skill)
    cho 6 Lớp Nhân Vật:
      1. Huyết Kiếm Sĩ: Trảm Huyết Nguyệt Liên Hoàn (10 nhát chém quét màn hình + hồi 50% HP)
      2. Pháp Sư Tinh Vân: Thiên Thạch Hư Không (Thiên thạch giáng thế + hố đen hút toàn bộ quái + nổ Nova)
      3. Thợ Săn Bóng Đêm: Tiễn Ảnh Bóng Đêm (Ngưng đọng thời gian 75% trong 4s + mưa 100+ tiễn độc)
      4. Thánh Kỵ Sĩ: Thánh Quang Bảo Hộ (5s Bất Tử + 12 cột sáng thánh quang thanh tẩy)
      5. Tử Linh Pháp Sư: Thủy Triều Tử Linh (45 đầu lâu linh hồn quét toàn bản đồ, hút sinh lực)
      6. Long Chiến Binh: Hơi Thở Thánh Long (Quét tia lửa rồng 360 độ thiêu rụi mọi kẻ thù)
    """
    def __init__(self, char_id: str, player, wave: int):
        self.char_id = char_id
        self.player = player
        self.wave = wave
        self.alive = True
        self.tick = 0
        self.life = 0
        self.max_life = 0
        self.impacted = False

        self.skin_id = getattr(player, "skin_id", "default")
        if self.skin_id == "saiyan":
            # Siêu Kamehameha & Quả Cầu Genki (Genki Dama)
            self.max_life = 125
            self.life = 125
            self.kame_angle = player.angle
            self.genki_r = 15.0
            self.genki_pos = [player.x, player.y - 75]
            self.exploded = False
            return
        elif self.skin_id == "naruto":
            # Bijuu Dama & Phong Độn: Rasenshuriken
            self.max_life = 120
            self.life = 120
            self.shuriken_angle = 0.0
            self.shuriken_pos = [player.x, player.y]
            self.shuriken_vel = [math.cos(player.angle) * 7.5, math.sin(player.angle) * 7.5]
            self.bijuu_exploded = False
            return
        elif self.skin_id == "gojo":
            # Hư Thức: Tử (Hollow Purple)
            self.max_life = 120
            self.life = 120
            self.blue_pos = [player.x - 70, player.y - 30]
            self.red_pos = [player.x + 70, player.y - 30]
            self.hollow_pos = [player.x, player.y]
            self.hollow_vel = [math.cos(player.angle) * 11.0, math.sin(player.angle) * 11.0]
            self.space_cracks = []
            return
        elif self.skin_id == "luffy":
            # Gear 5 Nika: Bajrang Gun (Cực Đại Viên Long Thương)
            self.max_life = 125
            self.life = 125
            self.target_pos = [player.x + math.cos(player.angle) * 120, player.y + math.sin(player.angle) * 120]
            self.fist_pos = [self.target_pos[0], player.y - 520]
            self.slammed = False
            self.haki_sparks = []
            return

        if char_id == "warrior":
            # 10 kiếm khí khổng lồ quét ngang dọc
            self.max_life = 65
            self.life = 65
            heal_amt = int(player.max_hp * 0.5)
            player.hp = min(player.max_hp, player.hp + heal_amt)
            player.heal_aura_timer = 50
            self.slashes = []
            for i in range(10):
                ang = random.uniform(0, math.tau)
                cx = player.x + random.uniform(-140, 140)
                cy = player.y + random.uniform(-100, 100)
                self.slashes.append({
                    "delay": i * 5,
                    "x1": cx - math.cos(ang) * 520,
                    "y1": cy - math.sin(ang) * 520,
                    "x2": cx + math.cos(ang) * 520,
                    "y2": cy + math.sin(ang) * 520,
                    "angle": ang,
                    "hit": False,
                    "anim": 0,
                })
        elif char_id == "mage":
            # Thiên Thạch Hư Không
            self.max_life = 95
            self.life = 95
            self.target_x = player.x
            self.target_y = player.y
            self.start_x = player.x - 240
            self.start_y = player.y - 520
            self.cur_x = self.start_x
            self.cur_y = self.start_y
            self.singularity_timer = 0
        elif char_id == "rogue":
            # Ngưng đọng thời gian 4s (240 ticks) + Tiễn Ảnh Bóng Đêm
            self.max_life = 240
            self.life = 240
            self.arrows = []
        elif char_id == "paladin":
            # 5s Bất Tử + 12 Cột Sáng Thánh Quang
            self.max_life = 300
            self.life = 300
            player.invincible = 300
            self.pillars = []
            for i in range(12):
                self.pillars.append({
                    "delay": i * 20,
                    "x": player.x + random.uniform(-420, 420),
                    "y": player.y + random.uniform(-300, 300),
                    "active": False,
                    "anim": 0,
                    "hit": False,
                })
        elif char_id == "necromancer":
            # Thủy Triều Tử Linh: 45 đầu lâu xoắn ốc
            self.max_life = 130
            self.life = 130
            self.skulls = []
            for i in range(45):
                ang = (math.tau / 45) * i
                spd = random.uniform(5.5, 9.5)
                self.skulls.append({
                    "x": player.x,
                    "y": player.y,
                    "vx": math.cos(ang) * spd,
                    "vy": math.sin(ang) * spd,
                    "ang": ang,
                    "life": 120,
                    "pierce": 12,
                    "hit_set": set(),
                })
        else:  # dragon_lancer
            # Hơi Thở Thánh Long: Quét lửa 360 độ quanh thân
            self.max_life = 105
            self.life = 105
            self.beam_angle = player.angle
            self.range_r = 380

    def update(self, enemies, bosses, particles, damage_numbers, shockwaves, sfx, player):
        self.tick += 1
        self.life -= 1
        if self.life <= 0:
            self.alive = False
            return

        all_e = [e for e in enemies + bosses if e.alive]
        p = player
        w = self.wave

        if self.skin_id == "saiyan":
            elapsed = self.max_life - self.life
            if elapsed < 40:
                self.genki_r = min(80.0, self.genki_r + 1.6)
                self.genki_pos[0] = p.x
                self.genki_pos[1] = p.y - 75
                for _ in range(3):
                    ang = random.uniform(0, math.tau)
                    r_p = random.uniform(80, 140)
                    particles.append(Particle(self.genki_pos[0] + math.cos(ang) * r_p,
                                              self.genki_pos[1] + math.sin(ang) * r_p,
                                              (80, 220, 255), speed=3.5, life=18))
            elif elapsed < 85:
                if elapsed == 40 and sfx:
                    sfx.play_beam()
                beam_dir = p.angle
                beam_len = 800
                p_start = (p.x, p.y)
                p_end = (p.x + math.cos(beam_dir) * beam_len, p.y + math.sin(beam_dir) * beam_len)
                dmg_tick = int((85 + w * 12) * p.damage_mult)
                for e in all_e:
                    if dist_to_segment((e.x, e.y), p_start, p_end) < 65 + e.radius:
                        e.take_damage(dmg_tick)
                        e.x += math.cos(beam_dir) * 4.0
                        e.y += math.sin(beam_dir) * 4.0
                        damage_numbers.append(DamageNumber(e.x, e.y, dmg_tick, (60, 220, 255), is_crit=(elapsed % 4 == 0)))
                        particles.append(Particle(e.x, e.y, (255, 225, 80), speed=4.0, life=14))
                shockwaves.append(ShockwaveRing(p.x, p.y, (80, 210, 255), max_radius=80, duration=10, width=3))
            else:
                if not self.exploded:
                    self.exploded = True
                    if sfx: sfx.play_thunder()
                    shockwaves.append(ShockwaveRing(self.genki_pos[0], self.genki_pos[1], (80, 230, 255), max_radius=380, duration=35, width=12))
                    shockwaves.append(ShockwaveRing(self.genki_pos[0], self.genki_pos[1], (255, 230, 90), max_radius=260, duration=25, width=8))
                    blast_dmg = int((800 + w * 65) * p.damage_mult)
                    for e in all_e:
                        if dist((self.genki_pos[0], self.genki_pos[1]), (e.x, e.y)) < 380:
                            e.take_damage(blast_dmg)
                            damage_numbers.append(DamageNumber(e.x, e.y, blast_dmg, (255, 230, 90), is_crit=True))
                            for _ in range(5):
                                particles.append(Particle(e.x, e.y, (60, 220, 255), speed=5.5, life=30))
            return

        elif self.skin_id == "naruto":
            elapsed = self.max_life - self.life
            self.shuriken_angle += 0.35
            if elapsed < 75:
                self.shuriken_pos[0] += self.shuriken_vel[0]
                self.shuriken_pos[1] += self.shuriken_vel[1]
                for _ in range(3):
                    particles.append(Particle(self.shuriken_pos[0], self.shuriken_pos[1], (255, 140, 40), speed=3.0, life=18))
                slash_dmg = int((65 + w * 8) * p.damage_mult)
                for e in all_e:
                    if dist((self.shuriken_pos[0], self.shuriken_pos[1]), (e.x, e.y)) < 110 + e.radius:
                        e.take_damage(slash_dmg)
                        damage_numbers.append(DamageNumber(e.x, e.y, slash_dmg, (255, 150, 50)))
            else:
                if not self.bijuu_exploded:
                    self.bijuu_exploded = True
                    if sfx: sfx.play_thunder()
                    shockwaves.append(ShockwaveRing(self.shuriken_pos[0], self.shuriken_pos[1], (255, 40, 60), max_radius=360, duration=35, width=11))
                    shockwaves.append(ShockwaveRing(self.shuriken_pos[0], self.shuriken_pos[1], (255, 140, 30), max_radius=240, duration=25, width=7))
                    nuke_dmg = int((750 + w * 60) * p.damage_mult)
                    for e in all_e:
                        if dist((self.shuriken_pos[0], self.shuriken_pos[1]), (e.x, e.y)) < 360:
                            e.take_damage(nuke_dmg)
                            damage_numbers.append(DamageNumber(e.x, e.y, nuke_dmg, (255, 60, 60), is_crit=True))
                            for _ in range(6):
                                particles.append(Particle(e.x, e.y, (255, 50, 50), speed=5.5, life=32))
            return

        elif self.skin_id == "gojo":
            elapsed = self.max_life - self.life
            if elapsed < 45:
                pull_dmg = int((40 + w * 5) * p.damage_mult)
                for e in all_e:
                    if dist((self.blue_pos[0], self.blue_pos[1]), (e.x, e.y)) < 220:
                        e.x += (self.blue_pos[0] - e.x) * 0.12
                        e.y += (self.blue_pos[1] - e.y) * 0.12
                        if elapsed % 8 == 0:
                            e.take_damage(pull_dmg)
                            damage_numbers.append(DamageNumber(e.x, e.y, pull_dmg, (40, 160, 255)))
                for e in all_e:
                    if dist((self.red_pos[0], self.red_pos[1]), (e.x, e.y)) < 220:
                        e.x -= (self.red_pos[0] - e.x) * 0.08
                        e.y -= (self.red_pos[1] - e.y) * 0.08
            elif elapsed < 65:
                mid_x = (self.blue_pos[0] + self.red_pos[0]) / 2
                mid_y = (self.blue_pos[1] + self.red_pos[1]) / 2
                self.hollow_pos = [mid_x, mid_y]
                if elapsed == 64 and sfx:
                    sfx.play_beam()
            else:
                self.hollow_pos[0] += self.hollow_vel[0]
                self.hollow_pos[1] += self.hollow_vel[1]
                if elapsed % 4 == 0:
                    ang = math.atan2(self.hollow_vel[1], self.hollow_vel[0])
                    p1 = (self.hollow_pos[0] + random.uniform(-25, 25), self.hollow_pos[1] + random.uniform(-25, 25))
                    p2 = (p1[0] - math.cos(ang) * random.uniform(40, 80), p1[1] - math.sin(ang) * random.uniform(40, 80))
                    self.space_cracks.append((p1, p2, 25))
                void_dmg = int((130 + w * 15) * p.damage_mult)
                for e in all_e:
                    if dist((self.hollow_pos[0], self.hollow_pos[1]), (e.x, e.y)) < 130 + e.radius:
                        e.take_damage(void_dmg)
                        damage_numbers.append(DamageNumber(e.x, e.y, void_dmg, (200, 70, 255), is_crit=True))
                        for _ in range(2):
                            particles.append(Particle(e.x, e.y, (190, 60, 255), speed=4.5, life=22))
            return

        elif self.skin_id == "luffy":
            elapsed = self.max_life - self.life
            if elapsed < 55:
                t = elapsed / 55.0
                self.fist_pos[1] = lerp(p.y - 520, self.target_pos[1], t)
                if elapsed % 3 == 0:
                    ang = random.uniform(0, math.tau)
                    r_h = random.uniform(110, 180)
                    p1 = (self.fist_pos[0], self.fist_pos[1])
                    p2 = (self.fist_pos[0] + math.cos(ang) * r_h, self.fist_pos[1] + math.sin(ang) * r_h)
                    self.haki_sparks.append((p1, p2, 12))
            else:
                if not self.slammed:
                    self.slammed = True
                    if sfx: sfx.play_thunder()
                    shockwaves.append(ShockwaveRing(self.target_pos[0], self.target_pos[1], (255, 30, 60), max_radius=390, duration=40, width=14))
                    shockwaves.append(ShockwaveRing(self.target_pos[0], self.target_pos[1], (255, 220, 60), max_radius=280, duration=30, width=9))
                    slam_dmg = int((900 + w * 75) * p.damage_mult)
                    for e in all_e:
                        if dist((self.target_pos[0], self.target_pos[1]), (e.x, e.y)) < 390:
                            e.take_damage(slam_dmg)
                            damage_numbers.append(DamageNumber(e.x, e.y, slam_dmg, (255, 40, 70), is_crit=True))
                            for _ in range(7):
                                particles.append(Particle(e.x, e.y, (255, 20, 50), speed=6.0, life=35))
            return

        if self.char_id == "warrior":
            elapsed = self.max_life - self.life
            for sl in self.slashes:
                if elapsed >= sl["delay"] and not sl["hit"]:
                    sl["hit"] = True
                    sl["anim"] = 12
                    p1 = (sl["x1"], sl["y1"])
                    p2 = (sl["x2"], sl["y2"])
                    dmg = int((440 + w * 35) * p.damage_mult)
                    for e in all_e:
                        if dist_to_segment((e.x, e.y), p1, p2) < e.radius + 45:
                            e.take_damage(dmg)
                            damage_numbers.append(DamageNumber(e.x, e.y, dmg, (255, 60, 75), is_crit=True))
                            for _ in range(3):
                                particles.append(Particle(e.x, e.y, (255, 30, 60), speed=4.2, angle=sl["angle"], spread=0.6))
                    mid_x = (sl["x1"] + sl["x2"]) / 2
                    mid_y = (sl["y1"] + sl["y2"]) / 2
                    shockwaves.append(ShockwaveRing(mid_x, mid_y, (255, 50, 70), max_radius=110, duration=15, width=4))
                elif sl.get("anim", 0) > 0:
                    sl["anim"] -= 1

        elif self.char_id == "mage":
            elapsed = self.max_life - self.life
            if elapsed <= 24:
                t = elapsed / 24.0
                self.cur_x = lerp(self.start_x, self.target_x, t)
                self.cur_y = lerp(self.start_y, self.target_y, t)
                for _ in range(4):
                    particles.append(Particle(self.cur_x, self.cur_y, (190, 80, 255), speed=2.5, life=25))
                    particles.append(Particle(self.cur_x, self.cur_y, (60, 220, 255), speed=2.0, life=20))
            elif not self.impacted:
                self.impacted = True
                self.cur_x = self.target_x
                self.cur_y = self.target_y
                shockwaves.append(ShockwaveRing(self.target_x, self.target_y, (200, 100, 255), max_radius=350, duration=35, width=9))
                shockwaves.append(ShockwaveRing(self.target_x, self.target_y, (255, 235, 120), max_radius=200, duration=25, width=6))
                dmg = int((600 + w * 45) * p.damage_mult)
                for e in all_e:
                    d = dist((self.target_x, self.target_y), (e.x, e.y))
                    if d < 360:
                        pull_x = (self.target_x - e.x) * 0.4
                        pull_y = (self.target_y - e.y) * 0.4
                        e.x += pull_x
                        e.y += pull_y
                        e.take_damage(dmg)
                        damage_numbers.append(DamageNumber(e.x, e.y, dmg, (215, 120, 255), is_crit=True))
                        for _ in range(4):
                            particles.append(Particle(e.x, e.y, (170, 70, 255), speed=4.5, life=35))
            else:
                self.singularity_timer += 1
                if self.singularity_timer % 6 == 0:
                    tick_dmg = int((45 + w * 5) * p.damage_mult)
                    for e in all_e:
                        d = dist((self.target_x, self.target_y), (e.x, e.y))
                        if d < 320:
                            pull_x = (self.target_x - e.x) * 0.12
                            pull_y = (self.target_y - e.y) * 0.12
                            e.x += pull_x
                            e.y += pull_y
                            e.take_damage(tick_dmg)
                            damage_numbers.append(DamageNumber(e.x, e.y, tick_dmg, (160, 220, 255)))

        elif self.char_id == "rogue":
            if self.tick % 2 == 0:
                ax = p.x + random.uniform(-460, 460)
                ay = p.y - 380
                self.arrows.append({
                    "x": ax, "y": ay,
                    "vx": random.uniform(-1.5, 1.5),
                    "vy": random.uniform(16.0, 21.0),
                    "life": 42,
                    "pierce": 4,
                    "hit_set": set(),
                })
            dmg = int((95 + w * 10) * p.damage_mult)
            for arr in self.arrows:
                arr["x"] += arr["vx"]
                arr["y"] += arr["vy"]
                arr["life"] -= 1
                for e in all_e:
                    if id(e) not in arr["hit_set"] and dist((arr["x"], arr["y"]), (e.x, e.y)) < e.radius + 14:
                        arr["hit_set"].add(id(e))
                        arr["pierce"] -= 1
                        e.take_damage(dmg)
                        damage_numbers.append(DamageNumber(e.x, e.y, dmg, (60, 255, 185)))
                        for _ in range(3):
                            particles.append(Particle(arr["x"], arr["y"], (40, 255, 170), speed=3.0, life=20))
                        if arr["pierce"] <= 0:
                            arr["life"] = 0
                            break
            self.arrows = [a for a in self.arrows if a["life"] > 0]

        elif self.char_id == "paladin":
            player.invincible = max(player.invincible, 60)
            elapsed = self.max_life - self.life
            for pil in self.pillars:
                if elapsed >= pil["delay"] and not pil["hit"]:
                    pil["hit"] = True
                    pil["anim"] = 24
                    shockwaves.append(ShockwaveRing(pil["x"], pil["y"], (255, 230, 90), max_radius=85, duration=22, width=5))
                    dmg = int((420 + w * 30) * p.damage_mult)
                    for e in all_e:
                        if dist((pil["x"], pil["y"]), (e.x, e.y)) < e.radius + 75:
                            e.take_damage(dmg)
                            damage_numbers.append(DamageNumber(e.x, e.y, dmg, (255, 235, 110), is_crit=True))
                            for _ in range(4):
                                particles.append(Particle(e.x, e.y, (255, 240, 120), speed=3.8, life=30))
                elif pil.get("anim", 0) > 0:
                    pil["anim"] -= 1

        elif self.char_id == "necromancer":
            dmg = int((280 + w * 22) * p.damage_mult)
            for sk in self.skulls:
                sk["x"] += sk["vx"]
                sk["y"] += sk["vy"]
                sk["vx"] *= 0.992
                sk["vy"] *= 0.992
                sk["life"] -= 1
                for e in all_e:
                    if id(e) not in sk["hit_set"] and dist((sk["x"], sk["y"]), (e.x, e.y)) < e.radius + 18:
                        sk["hit_set"].add(id(e))
                        sk["pierce"] -= 1
                        e.take_damage(dmg)
                        damage_numbers.append(DamageNumber(e.x, e.y, dmg, (40, 245, 195), is_crit=True))
                        if p.hp < p.max_hp:
                            p.hp = min(p.max_hp, p.hp + 1)
                        for _ in range(4):
                            particles.append(Particle(sk["x"], sk["y"], (50, 255, 205), speed=3.2, life=25))
                        if sk["pierce"] <= 0:
                            sk["life"] = 0
                            break
            self.skulls = [s for s in self.skulls if s["life"] > 0]

        elif self.char_id == "dragon_lancer":
            self.beam_angle += 0.075
            dmg = int((240 + w * 20) * p.damage_mult)
            if self.tick % 2 == 0:
                for e in all_e:
                    d = dist((p.x, p.y), (e.x, e.y))
                    if d < self.range_r:
                        ea = math.atan2(e.y - p.y, e.x - p.x)
                        diff = abs((ea - self.beam_angle + math.pi) % (2 * math.pi) - math.pi)
                        if diff < 0.42:
                            e.take_damage(dmg)
                            damage_numbers.append(DamageNumber(e.x, e.y, dmg, (255, 120, 35)))
                            for _ in range(3):
                                particles.append(Particle(e.x, e.y, (255, 140, 40), speed=3.5, life=22))

    def draw(self, surf, cam_x, cam_y, tick):
        p = self.player

        if self.skin_id == "saiyan":
            elapsed = self.max_life - self.life
            psx = int(p.x - cam_x)
            psy = int(p.y - cam_y)
            # Phase 1: Quả cầu Ki Genki Dama tích tụ trên cao
            if elapsed < 40 or elapsed >= 85:
                gx = int(self.genki_pos[0] - cam_x)
                gy = int(self.genki_pos[1] - cam_y)
                gr = int(self.genki_r)
                draw_additive_glow(surf, gx, gy, gr + 30, (80, 220, 255), intensity=0.7)
                pygame.draw.circle(surf, (255, 255, 255), (gx, gy), max(4, int(gr * 0.7)))
                pygame.draw.circle(surf, (100, 230, 255), (gx, gy), gr, 4)
                # Tia điện hoàng kim quanh quả cầu
                for _ in range(2):
                    ra = random.uniform(0, math.tau)
                    rx1 = gx + int(math.cos(ra) * gr)
                    ry1 = gy + int(math.sin(ra) * gr)
                    rx2 = gx + int(math.cos(ra) * (gr + random.uniform(15, 35)))
                    ry2 = gy + int(math.sin(ra) * (gr + random.uniform(15, 35)))
                    pygame.draw.line(surf, (255, 240, 90), (rx1, ry1), (rx2, ry2), 2)
            # Phase 2: Siêu Kamehameha quét chùm tia cực đại
            if 40 <= elapsed < 85:
                beam_dir = p.angle
                beam_len = 800
                bw = 90
                beam_s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
                perp_x = -math.sin(beam_dir) * (bw / 2)
                perp_y = math.cos(beam_dir) * (bw / 2)
                p1 = (psx + perp_x, psy + perp_y)
                p2 = (psx - perp_x, psy - perp_y)
                p3 = (psx + math.cos(beam_dir) * beam_len - perp_x, psy + math.sin(beam_dir) * beam_len - perp_y)
                p4 = (psx + math.cos(beam_dir) * beam_len + perp_x, psy + math.sin(beam_dir) * beam_len + perp_y)
                pygame.draw.polygon(beam_s, (60, 215, 255, 175), [p1, p2, p3, p4])
                perp_core_x = perp_x * 0.45
                perp_core_y = perp_y * 0.45
                c1 = (psx + perp_core_x, psy + perp_core_y)
                c2 = (psx - perp_core_x, psy - perp_core_y)
                c3 = (psx + math.cos(beam_dir) * beam_len - perp_core_x, psy + math.sin(beam_dir) * beam_len - perp_core_y)
                c4 = (psx + math.cos(beam_dir) * beam_len + perp_core_x, psy + math.sin(beam_dir) * beam_len + perp_core_y)
                pygame.draw.polygon(beam_s, (255, 255, 255, 240), [c1, c2, c3, c4])
                surf.blit(beam_s, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
                draw_additive_glow(surf, psx, psy, 65, (100, 230, 255), 0.8)
            return

        elif self.skin_id == "naruto":
            elapsed = self.max_life - self.life
            sx = int(self.shuriken_pos[0] - cam_x)
            sy = int(self.shuriken_pos[1] - cam_y)
            if elapsed < 75:
                draw_additive_glow(surf, sx, sy, 55, (255, 140, 40), 0.65)
                pygame.draw.circle(surf, (20, 5, 10), (sx, sy), 18)
                pygame.draw.circle(surf, (255, 50, 60), (sx, sy), 20, 3)
                ang = self.shuriken_angle
                for b_i in range(4):
                    blade_ang = ang + b_i * (math.pi / 2)
                    bx = sx + int(math.cos(blade_ang) * 44)
                    by = sy + int(math.sin(blade_ang) * 44)
                    wing_x = sx + int(math.cos(blade_ang + 0.4) * 26)
                    wing_y = sy + int(math.sin(blade_ang + 0.4) * 26)
                    pts = [(sx, sy), (wing_x, wing_y), (bx, by)]
                    pygame.draw.polygon(surf, (255, 180, 50), pts)
                    pygame.draw.lines(surf, (255, 255, 220), False, pts, 2)
            else:
                draw_additive_glow(surf, sx, sy, 140, (255, 60, 40), 0.85)
                pygame.draw.circle(surf, (30, 10, 15), (sx, sy), 65)
                pygame.draw.circle(surf, (255, 80, 50), (sx, sy), 70, 4)
            return

        elif self.skin_id == "gojo":
            elapsed = self.max_life - self.life
            if elapsed < 45:
                bx = int(self.blue_pos[0] - cam_x)
                by = int(self.blue_pos[1] - cam_y)
                rx = int(self.red_pos[0] - cam_x)
                ry = int(self.red_pos[1] - cam_y)
                draw_additive_glow(surf, bx, by, 38, (40, 160, 255), 0.7)
                pygame.draw.circle(surf, (255, 255, 255), (bx, by), 9)
                pygame.draw.circle(surf, (40, 180, 255), (bx, by), 15, 2)
                draw_additive_glow(surf, rx, ry, 38, (255, 40, 60), 0.7)
                pygame.draw.circle(surf, (255, 255, 255), (rx, ry), 9)
                pygame.draw.circle(surf, (255, 50, 70), (rx, ry), 15, 2)
            else:
                hx = int(self.hollow_pos[0] - cam_x)
                hy = int(self.hollow_pos[1] - cam_y)
                for p1, p2, lf in self.space_cracks:
                    c1 = (int(p1[0] - cam_x), int(p1[1] - cam_y))
                    c2 = (int(p2[0] - cam_x), int(p2[1] - cam_y))
                    pygame.draw.line(surf, (220, 70, 255), c1, c2, 3)
                    pygame.draw.line(surf, (15, 5, 25), c1, c2, 1)
                draw_additive_glow(surf, hx, hy, 65, (190, 60, 255), 0.85)
                pygame.draw.circle(surf, (255, 255, 255), (hx, hy), 22)
                pygame.draw.circle(surf, (180, 40, 255), (hx, hy), 36, 4)
                pygame.draw.circle(surf, (30, 10, 50), (hx, hy), 14)
            return

        elif self.skin_id == "luffy":
            elapsed = self.max_life - self.life
            fx = int(self.fist_pos[0] - cam_x)
            fy = int(self.fist_pos[1] - cam_y)
            for p1, p2, lf in self.haki_sparks:
                c1 = (int(p1[0] - cam_x), int(p1[1] - cam_y))
                c2 = (int(p2[0] - cam_x), int(p2[1] - cam_y))
                draw_jagged_lightning_arc(surf, c1, c2, (255, 30, 60), (20, 5, 10), width=4, branches=1, dark_haki=True)
            draw_additive_glow(surf, fx, fy, 110, (255, 220, 160), 0.6)
            pygame.draw.circle(surf, (245, 245, 250), (fx, fy), 85)
            pygame.draw.circle(surf, (20, 18, 30), (fx, fy), 85, 5)
            for k in range(4):
                kx = fx - 45 + k * 30
                ky = fy + 35
                pygame.draw.circle(surf, (230, 230, 240), (kx, ky), 20)
                pygame.draw.circle(surf, (20, 18, 30), (kx, ky), 20, 4)
            return

        if self.char_id == "warrior":
            for sl in self.slashes:
                if sl.get("anim", 0) > 0:
                    t_ratio = sl["anim"] / 12.0
                    sx1 = int(sl["x1"] - cam_x)
                    sy1 = int(sl["y1"] - cam_y)
                    sx2 = int(sl["x2"] - cam_x)
                    sy2 = int(sl["y2"] - cam_y)
                    pygame.draw.line(surf, (255, 30, 60), (sx1, sy1), (sx2, sy2), int(10 * t_ratio) + 2)
                    pygame.draw.line(surf, (255, 230, 240), (sx1, sy1), (sx2, sy2), int(4 * t_ratio) + 1)

        elif self.char_id == "mage":
            elapsed = self.max_life - self.life
            if elapsed <= 24:
                msx = int(self.cur_x - cam_x)
                msy = int(self.cur_y - cam_y)
                draw_additive_glow(surf, msx, msy, 45, (190, 80, 255), 0.7)
                pygame.draw.circle(surf, (210, 120, 255), (msx, msy), 24)
                pygame.draw.circle(surf, (255, 240, 255), (msx, msy), 14)
                tail_dx = self.start_x - self.target_x
                tail_dy = self.start_y - self.target_y
                tnx, tny = norm(tail_dx, tail_dy)
                for ti in range(5):
                    tx = int(msx + tnx * ti * 12)
                    ty = int(msy + tny * ti * 12)
                    pygame.draw.circle(surf, (150, 60, 220), (tx, ty), max(2, 18 - ti * 3))
            else:
                tsx = int(self.target_x - cam_x)
                tsy = int(self.target_y - cam_y)
                t_ratio = self.life / float(max(1, self.max_life - 24))
                vr = int(75 + math.sin(tick * 0.25) * 12)
                draw_additive_glow(surf, tsx, tsy, vr + 30, (160, 60, 255), 0.6 * t_ratio)
                for ri in range(6):
                    ra = tick * 0.12 + ri * (math.tau / 6)
                    rx = tsx + int(math.cos(ra) * vr)
                    ry = tsy + int(math.sin(ra) * vr)
                    pygame.draw.circle(surf, (60, 230, 255), (rx, ry), 5)
                pygame.draw.circle(surf, (12, 8, 20), (tsx, tsy), int(36 * t_ratio))
                pygame.draw.circle(surf, (200, 100, 255), (tsx, tsy), int(36 * t_ratio), 2)

        elif self.char_id == "rogue":
            for arr in self.arrows:
                asx = int(arr["x"] - cam_x)
                asy = int(arr["y"] - cam_y)
                tx = int(asx - arr["vx"] * 2.2)
                ty = int(asy - arr["vy"] * 2.2)
                pygame.draw.line(surf, (30, 255, 160), (tx, ty), (asx, asy), 4)
                pygame.draw.circle(surf, (220, 255, 235), (asx, asy), 3)

        elif self.char_id == "paladin":
            for pil in self.pillars:
                if pil.get("anim", 0) > 0:
                    t_ratio = pil["anim"] / 24.0
                    alpha = int(220 * t_ratio)
                    psx = int(pil["x"] - cam_x)
                    psy = int(pil["y"] - cam_y)
                    pw = int(55 * t_ratio) + 12
                    beam_s = pygame.Surface((pw * 2, SCREEN_H), pygame.SRCALPHA)
                    pygame.draw.rect(beam_s, (255, 225, 80, min(255, alpha // 2)), (0, 0, pw * 2, SCREEN_H))
                    pygame.draw.rect(beam_s, (255, 255, 220, alpha), (pw // 2, 0, pw, SCREEN_H))
                    surf.blit(beam_s, (psx - pw, 0), special_flags=pygame.BLEND_RGBA_ADD)
                    draw_additive_glow(surf, psx, psy, int(70 * t_ratio), (255, 220, 90), 0.6)

        elif self.char_id == "necromancer":
            for sk in self.skulls:
                ssx = int(sk["x"] - cam_x)
                ssy = int(sk["y"] - cam_y)
                tx = int(ssx - sk["vx"] * 1.8)
                ty = int(ssy - sk["vy"] * 1.8)
                pygame.draw.line(surf, (35, 220, 180), (tx, ty), (ssx, ssy), 3)
                pygame.draw.circle(surf, (220, 245, 240), (ssx, ssy), 6)
                pygame.draw.circle(surf, (30, 230, 180), (ssx, ssy), 6, 1)
                pygame.draw.circle(surf, (15, 12, 22), (ssx - 2, ssy - 1), 1)
                pygame.draw.circle(surf, (15, 12, 22), (ssx + 2, ssy - 1), 1)

        elif self.char_id == "dragon_lancer":
            psx = int(p.x - cam_x)
            psy = int(p.y - cam_y)
            ang = self.beam_angle
            half_ang = 0.38
            r_len = self.range_r
            pts = [
                (psx, psy),
                (psx + int(math.cos(ang - half_ang) * r_len), psy + int(math.sin(ang - half_ang) * r_len)),
                (psx + int(math.cos(ang) * (r_len + 25)), psy + int(math.sin(ang) * (r_len + 25))),
                (psx + int(math.cos(ang + half_ang) * r_len), psy + int(math.sin(ang + half_ang) * r_len)),
            ]
            cone_s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            pygame.draw.polygon(cone_s, (255, 95, 25, 95), pts)
            pygame.draw.polygon(cone_s, (255, 220, 75, 175), pts, 3)
            tx = psx + int(math.cos(ang) * (r_len + 15))
            ty = psy + int(math.sin(ang) * (r_len + 15))
            pygame.draw.line(cone_s, (255, 250, 190, 220), (psx, psy), (tx, ty), 6)
            surf.blit(cone_s, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)


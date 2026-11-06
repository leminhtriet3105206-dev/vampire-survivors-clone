"""Procedural audio synthesis sound engine and background music loops."""
import array
import math
import random
from typing import Optional
import pygame
import audio_settings

class SoundEngine:
    SR = 44100

    def __init__(self, settings_path=None):
        try:
            pygame.mixer.pre_init(self.SR, -16, 1, 512)
            pygame.mixer.init()
        except Exception as e:
            print("[SoundEngine] Mixer init deferred/skipped:", e)
        self.muted   = False
        self._settings_path = settings_path
        self.volumes = audio_settings.load_settings(settings_path)
        self._cache: dict = {}
        self._last_play: dict = {}
        self._bg_channel: Optional[pygame.mixer.Channel] = None
        self._bg_sound: Optional[pygame.mixer.Sound] = None
        self._menu_sound: Optional[pygame.mixer.Sound] = None
        self._battle_sound: Optional[pygame.mixer.Sound] = None
        self._current_track = "menu"
        from core.dynamic_audio import DynamicMusicDirector
        self.dynamic_music = DynamicMusicDirector(sound_engine=self)
        try:
            self._start_bg()
        except Exception:
            self._bg_channel = None

    # --- Ses seviyesi ayarları ---
    # Seviye yalnızca Sound.set_volume ile uygulanır (kanal sesi 1.0 kalır);
    # mute ayrı bir mekanizmadır ve seviyeleri değiştirmez.
    def _gain(self, key):
        eff = audio_settings.effective_volumes(self.volumes)
        return eff["coin"] if key == 'coin' else eff["sfx"]

    def set_volume(self, name, percent):
        if name in audio_settings.KEYS:
            self.volumes[name] = audio_settings.clamp_percent(
                percent, self.volumes[name])
            self._apply_volumes()

    def _apply_volumes(self):
        for key, snd in self._cache.items():
            if snd:
                try:
                    snd.set_volume(self._gain(key))
                except Exception:
                    pass
        if self._bg_sound:
            try:
                self._bg_sound.set_volume(
                    audio_settings.effective_volumes(self.volumes)["music"])
            except Exception:
                pass
        if hasattr(self, "dynamic_music"):
            self.dynamic_music.apply_volume()

    def save_volumes(self):
        return audio_settings.save_settings(self.volumes, self._settings_path)

    # --- Sinyal üreticiler ---
    def _sine_buf(self, freq, dur, vol=0.45, attack=0.01, decay_exp=1.0):
        n   = int(self.SR * dur)
        buf = array.array('h')
        for i in range(n):
            t   = i / self.SR
            env = min(t / attack, 1.0) * max(0.0, 1.0 - (t / dur) ** decay_exp)
            s   = int(vol * env * 32767 * math.sin(2 * math.pi * freq * t))
            buf.append(s)
        return bytes(buf)

    def _sweep_buf(self, f0, f1, dur, vol=0.4):
        n   = int(self.SR * dur)
        buf = array.array('h')
        ph  = 0.0
        for i in range(n):
            t    = i / self.SR
            env  = max(0.0, 1.0 - t / dur)
            freq = f0 + (f1 - f0) * (t / dur)
            ph  += 2 * math.pi * freq / self.SR
            s    = int(vol * env * 32767 * math.sin(ph))
            buf.append(s)
        return bytes(buf)

    def _tone_seq_buf(self, notes, vol=0.3, shimmer=0.0):
        """notes: [(freq, dur)] sırayla çalınır; her nota kendi içinde söner.
        shimmer: son notanın bir oktav üstüne eklenen hafif katman (0 = yok)."""
        buf = array.array('h')
        last = len(notes) - 1
        for k, (freq, dur) in enumerate(notes):
            n = int(self.SR * dur)
            for i in range(n):
                t   = i / self.SR
                env = min(t / 0.004, 1.0) * math.exp(-4.0 * t / dur)
                w   = math.sin(2 * math.pi * freq * t) + 0.25 * math.sin(4 * math.pi * freq * t)
                if shimmer and k == last:
                    w += shimmer * math.sin(4 * math.pi * freq * t)
                buf.append(int(max(-1.0, min(1.0, vol * env * w)) * 32767))
        return bytes(buf)

    def _noise_buf(self, dur, vol=0.35):
        n   = int(self.SR * dur)
        buf = array.array('h')
        for i in range(n):
            env = max(0.0, 1.0 - i / n)
            s   = int(vol * env * 32767 * (random.random() * 2 - 1))
            buf.append(s)
        return bytes(buf)

    def _make(self, key, fn):
        if key not in self._cache:
            try:
                data = fn()
                snd  = pygame.mixer.Sound(buffer=data)
                snd.set_volume(self._gain(key))
                self._cache[key] = snd
            except Exception:
                return None
        return self._cache.get(key)

    def _play(self, snd):
        if not self.muted and snd:
            try:
                snd.play()
            except Exception:
                pass

    def _throttled(self, key, min_ms):
        """Ses azaltma: yalnızca sesi sınırlar, oyun mantığını etkilemez.
        Sessizdeyken zaman damgasını tüketmez; aynı key min_ms içinde
        tekrar çalınmaz (üst üste binmeyi önler)."""
        if self.muted:
            return False
        now = pygame.time.get_ticks()
        if now - self._last_play.get(key, -min_ms) < min_ms:
            return False
        self._last_play[key] = now
        return True

    # --- Oyun sesleri ---
    def play_coin(self):
        if self._throttled('coin', 70):
            self._play(self._make('coin',
                lambda: self._tone_seq_buf([(988, 0.05), (1319, 0.11)], 0.3)))

    def play_achievement(self):
        if self._throttled('ach', 400):
            self._play(self._make('ach',
                lambda: self._tone_seq_buf(
                    [(523, 0.09), (659, 0.09), (784, 0.09), (1047, 0.28)],
                    0.35, shimmer=0.3)))

    def play_hit(self):
        self._play(self._make('hit',
            lambda: self._noise_buf(0.08, 0.3)))

    def play_whip(self):
        self._play(self._make('whip',
            lambda: self._sweep_buf(600, 150, 0.14, 0.5)))

    def play_orb(self):
        self._play(self._make('orb',
            lambda: self._sine_buf(520, 0.12, 0.35)))

    def play_aura(self):
        self._play(self._make('aura',
            lambda: self._sine_buf(180, 0.18, 0.25, decay_exp=2)))

    def play_xp(self):
        self._play(self._make('xp',
            lambda: self._sweep_buf(400, 900, 0.12, 0.3)))

    def play_levelup(self):
        self._play(self._make('lvlup',
            lambda: self._sweep_buf(500, 1400, 0.35, 0.5)))

    def play_damage(self):
        self._play(self._make('dmg',
            lambda: self._sweep_buf(200, 80, 0.18, 0.45)))

    def play_lightning(self):
        self._play(self._make('lightning',
            lambda: self._sweep_buf(1400, 300, 0.12, 0.45)))

    def play_ice(self):
        self._play(self._make('ice',
            lambda: self._sine_buf(1700, 0.08, 0.35, attack=0.005, decay_exp=1.5)))

    def play_death(self):
        self._play(self._make('death',
            lambda: self._noise_buf(0.5, 0.55)))

    def play_laser(self):
        self._play(self._make('laser',
            lambda: self._sweep_buf(880, 220, 0.08, 0.35)))

    def play_awakened(self):
        self._play(self._make('awakened',
            lambda: self._tone_seq_buf([(220, 0.08), (330, 0.08), (440, 0.08), (660, 0.28)], vol=0.45, shimmer=0.35)))

    def play_beam(self):
        self._play(self._make('beam',
            lambda: self._sweep_buf(1100, 240, 0.20, 0.45)))

    def play_whoosh(self):
        self._play(self._make('whoosh',
            lambda: self._sweep_buf(340, 90, 0.14, 0.4)))

    def play_thunder(self):
        self._play(self._make('thunder',
            lambda: self._noise_buf(0.42, 0.55)))

    def play_chime(self):
        self._play(self._make('chime',
            lambda: self._tone_seq_buf([(587, 0.08), (784, 0.08), (1175, 0.20)], 0.38, shimmer=0.35)))

    # --- Arka plan müziği (prosedürel loop) ---
    def _build_menu_bg(self):
        """Bản nhạc Menu / Sảnh Chờ (Lobby): Giai điệu Fantasy anh hùng, tươi sáng, kỳ ảo."""
        dur = 4.0
        n = int(self.SR * dur)
        buf = array.array('h')
        chords = [
            [261.63, 329.63, 392.00],  # C
            [196.00, 246.94, 293.66],  # G
            [220.00, 261.63, 329.63],  # Am
            [174.61, 220.00, 261.63],  # F
        ]
        melody_notes = [523.25, 587.33, 659.25, 783.99, 659.25, 523.25, 392.00, 440.00]
        for i in range(n):
            t = i / self.SR
            beat = t * 2.0  # 120 BPM
            ch_idx = int(beat) % 4
            chord = chords[ch_idx]
            pad = sum(math.sin(2 * math.pi * f * t) for f in chord) * 0.05
            m_idx = int(beat * 2) % len(melody_notes)
            m_freq = melody_notes[m_idx]
            env_m = math.exp(-4.0 * ((beat * 2) % 1.0))
            bell = math.sin(2 * math.pi * m_freq * t) * 0.08 * env_m
            bass_f = chord[0] * 0.5
            bass = math.sin(2 * math.pi * bass_f * t) * 0.12 * (0.6 + 0.4 * math.sin(beat * math.pi))
            val = int((pad + bell + bass) * 32767 * 0.65)
            val = max(-32767, min(32767, val))
            buf.append(val)
        return bytes(buf)

    def _build_battle_bg(self):
        """Bản nhạc Chiến Đấu: Tiết tấu Synthwave / Chiptune sôi động, dồn dập, hào hùng."""
        dur = 4.0
        n = int(self.SR * dur)
        buf = array.array('h')
        bass_seq = [110, 110, 130.8, 110, 146.8, 130.8, 164.8, 146.8]
        lead_seq = [440, 523.25, 659.25, 587.33, 783.99, 659.25, 523.25, 587.33]
        for i in range(n):
            t = i / self.SR
            beat = t * 2.25  # ~135 BPM
            b_idx = int(beat * 2) % len(bass_seq)
            bf = bass_seq[b_idx]
            b_env = math.exp(-5.0 * ((beat * 2) % 1.0))
            bass = (math.sin(2 * math.pi * bf * t) + 0.3 * math.sin(4 * math.pi * bf * t)) * 0.16 * b_env
            l_idx = int(beat * 4) % len(lead_seq)
            lf = lead_seq[l_idx]
            l_env = math.exp(-6.0 * ((beat * 4) % 1.0))
            lead = (math.sin(2 * math.pi * lf * t) + 0.25 * math.sin(6 * math.pi * lf * t)) * 0.12 * l_env
            k_env = math.exp(-12.0 * (beat % 1.0))
            kick = math.sin(2 * math.pi * max(40, 120 - (beat % 1.0) * 160) * t) * 0.22 * k_env
            sn_step = (beat + 0.5) % 1.0
            sn_env = math.exp(-14.0 * sn_step)
            snare = (random.random() * 2 - 1) * 0.12 * sn_env
            val = int((bass + lead + kick + snare) * 32767 * 0.65)
            val = max(-32767, min(32767, val))
            buf.append(val)
        return bytes(buf)

    def _build_bg(self):
        return self._build_battle_bg()

    def _start_bg(self):
        try:
            data = self._build_menu_bg()
            snd  = pygame.mixer.Sound(buffer=data)
            snd.set_volume(audio_settings.effective_volumes(self.volumes)["music"])
            self._menu_sound = snd
            self._bg_sound   = snd
            self._bg_channel = snd.play(loops=-1)
        except Exception:
            self._bg_channel = None

    def play_menu_bgm(self):
        if hasattr(self, "dynamic_music"):
            self.dynamic_music.stop()
        if self._current_track == "menu" and self._bg_channel and self._bg_channel.get_busy():
            return
        self._current_track = "menu"
        try:
            if self._menu_sound is None:
                self._menu_sound = pygame.mixer.Sound(buffer=self._build_menu_bg())
            if self._bg_channel:
                self._bg_channel.stop()
            self._bg_sound = self._menu_sound
            self._bg_sound.set_volume(audio_settings.effective_volumes(self.volumes)["music"])
            if not self.muted:
                self._bg_channel = self._bg_sound.play(loops=-1)
        except Exception:
            pass

    def play_battle_bgm(self):
        self._current_track = "battle"
        if self._bg_channel:
            try:
                self._bg_channel.stop()
            except Exception:
                pass
        try:
            if self._battle_sound is None:
                self._battle_sound = pygame.mixer.Sound(buffer=self._build_battle_bg())
            self._bg_sound = self._battle_sound
            self._bg_sound.set_volume(audio_settings.effective_volumes(self.volumes)["music"])
        except Exception:
            pass

        if hasattr(self, "dynamic_music"):
            if not self.dynamic_music.active:
                self.dynamic_music.start()
        else:
            try:
                if not self.muted and self._bg_sound:
                    self._bg_channel = self._bg_sound.play(loops=-1)
            except Exception:
                pass

    def toggle_mute(self):
        self.muted = not self.muted
        if hasattr(self, "dynamic_music"):
            self.dynamic_music.apply_volume()
        if self._bg_channel:
            try:
                if self.muted:
                    pygame.mixer.pause()
                else:
                    pygame.mixer.unpause()
            except Exception:
                pass

# ---------------------------------------------------------------------------

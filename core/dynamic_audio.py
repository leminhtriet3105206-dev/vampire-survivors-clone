"""Procedural Dynamic Multi-Phase Background Music Synthesizer & Director.

Generates and phase-locks 4 procedural music layers at 120 BPM:
  - Layer 0 (Ambient Drone): Atmospheric dark fantasy pad & sub-bass baseline.
  - Layer 1 (Battle Pulse): Driving 4-on-the-floor house kick, rolling 16th-note arpeggio, hi-hats.
  - Layer 2 (Swarm Climax): Cracking rock/electro snare backbeats, screaming dual-saw lead, open hats.
  - Layer 3 (Boss Cataclysm): Distorted power-chug bass, dramatic brass chord stabs, tension risers.

Dynamically shifts layer volumes in real-time according to enemy swarm density,
boss presence, and player health urgency.
"""
import array
import math
import random
from typing import Any, Dict, List, Optional
import pygame

from spatial.math_utils import clamp, lerp


class DynamicMusicDirector:
    """Manages multi-track synchronized procedural BGM with real-time intensity scaling."""

    SR: int = 44100
    BPM: float = 120.0
    LOOP_DURATION: float = 4.0  # Exactly 8 beats = 2 bars of 4/4 at 120 BPM

    def __init__(self, sound_engine: Optional[Any] = None):
        self.sound_engine = sound_engine
        self.active: bool = False
        self.paused: bool = False

        # 4 Dynamic Layers
        self.target_volumes: List[float] = [1.0, 0.0, 0.0, 0.0]
        self.current_volumes: List[float] = [1.0, 0.0, 0.0, 0.0]

        # Pygame mixer sound and channel references
        self.sounds: List[Optional[pygame.mixer.Sound]] = [None, None, None, None]
        self.channels: List[Optional[pygame.mixer.Channel]] = [None, None, None, None]
        self.channel_indices: List[int] = [8, 9, 10, 11]

        self._buffers_built: bool = False
        self._raw_buffers: List[Optional[bytes]] = [None, None, None, None]

    # -------------------------------------------------------------------------
    # Procedural Audio Synthesis (120 BPM, 4.0s Seamless Loops)
    # -------------------------------------------------------------------------
    @staticmethod
    def _apply_loop_window(buf: array.array, n_samples: int, fade_len: int = 256) -> None:
        """Applies a micro crossfade window at loop seams to guarantee zero DC clicks."""
        for i in range(fade_len):
            gain = i / float(fade_len)
            buf[i] = int(buf[i] * gain)
            tail_idx = n_samples - 1 - i
            buf[tail_idx] = int(buf[tail_idx] * gain)

    def _build_layer_0_ambient(self) -> bytes:
        """Layer 0: Ambient Drone / Bass & Warm Dark Fantasy Pad (Dm - Bb - F - C)."""
        n = int(self.SR * self.LOOP_DURATION)
        buf = array.array('h')
        chords = [
            (146.83, 174.61, 220.00),  # Dm (D3, F3, A3)
            (116.54, 146.83, 174.61),  # Bb (Bb2, D3, F3)
            (174.61, 220.00, 261.63),  # F  (F3, A3, C4)
            (130.81, 164.81, 196.00),  # C  (C3, E3, G3)
        ]

        for i in range(n):
            t = i / self.SR
            beat = t * 2.0  # 120 BPM -> 2 beats/sec
            chord_idx = int(beat * 0.5) % 4
            chord = chords[chord_idx]

            # Slow pulsing warm pad
            pad = sum(math.sin(2 * math.pi * f * t) + 0.3 * math.sin(4 * math.pi * f * t) for f in chord) * 0.06
            # Deep sub-bass drone (55Hz / 73Hz root sub)
            sub_f = chord[0] * 0.5
            sub = math.sin(2 * math.pi * sub_f * t) * 0.14 * (0.85 + 0.15 * math.sin(beat * math.pi))

            sample = int((pad + sub) * 32767 * 0.7)
            buf.append(max(-32767, min(32767, sample)))

        self._apply_loop_window(buf, n)
        return bytes(buf)

    def _build_layer_1_pulse(self) -> bytes:
        """Layer 1: Battle Escalation (House 4-on-the-floor kick, 16th-note arp, hi-hats)."""
        n = int(self.SR * self.LOOP_DURATION)
        buf = array.array('h')
        # 16th note arpeggio sequence across Dm progression
        arp_freqs = [
            220.0, 293.66, 349.23, 440.0,   # Dm
            233.08, 293.66, 349.23, 466.16, # Bb
            261.63, 329.63, 392.00, 523.25, # C
            174.61, 220.00, 261.63, 349.23, # F
        ]

        for i in range(n):
            t = i / self.SR
            beat = t * 2.0  # 120 BPM

            # 4-on-the-floor punchy kick (at every beat)
            kick_t = beat % 1.0
            kick_env = math.exp(-14.0 * kick_t)
            kick_freq = max(42.0, 140.0 - kick_t * 220.0)
            kick = math.sin(2 * math.pi * kick_freq * t) * 0.22 * kick_env

            # 16th-note rolling arpeggio (4 notes per beat)
            step_16th = beat * 4.0
            note_idx = int(step_16th) % len(arp_freqs)
            note_f = arp_freqs[note_idx]
            step_t = step_16th % 1.0
            arp_env = math.exp(-7.0 * step_t)
            arp = (math.sin(2 * math.pi * note_f * t) + 0.2 * math.sin(4 * math.pi * note_f * t)) * 0.12 * arp_env

            # Closed hi-hat on offbeats (0.5, 1.5, 2.5, etc.)
            hat_step = (beat + 0.5) % 1.0
            hat_env = math.exp(-24.0 * hat_step)
            hat = (random.random() * 2.0 - 1.0) * 0.08 * hat_env

            sample = int((kick + arp + hat) * 32767 * 0.65)
            buf.append(max(-32767, min(32767, sample)))

        self._apply_loop_window(buf, n)
        return bytes(buf)

    def _build_layer_2_climax(self) -> bytes:
        """Layer 2: Swarm Climax (Rock/Electro snare crack, screaming dual-saw lead, open hats)."""
        n = int(self.SR * self.LOOP_DURATION)
        buf = array.array('h')
        # Searing heroic high-register melody
        lead_notes = [587.33, 659.25, 698.46, 880.00, 783.99, 698.46, 659.25, 587.33]

        for i in range(n):
            t = i / self.SR
            beat = t * 2.0

            # Powerful Snare crack on beats 2 and 4 (1 and 3 in 0-index)
            snare_step = (beat + 1.0) % 2.0
            snare_env = math.exp(-12.0 * snare_step)
            snare_noise = (random.random() * 2.0 - 1.0) * 0.18 * snare_env
            snare_tone = math.sin(2 * math.pi * 185.0 * t) * 0.12 * snare_env
            snare = snare_noise + snare_tone

            # Screaming Dual-Saw Lead
            l_step = beat * 2.0
            l_idx = int(l_step) % len(lead_notes)
            lf = lead_notes[l_idx]
            l_env = math.exp(-4.5 * (l_step % 1.0))
            # Pseudo-sawtooth with slight chorus detune (+1.5Hz)
            saw1 = 2.0 * (t * lf - math.floor(0.5 + t * lf))
            saw2 = 2.0 * (t * (lf + 1.5) - math.floor(0.5 + t * (lf + 1.5)))
            lead = (saw1 * 0.6 + saw2 * 0.4) * 0.14 * l_env

            # Sizzling open hi-hat
            open_hat_step = (beat + 0.5) % 1.0
            open_hat_env = math.exp(-10.0 * open_hat_step)
            open_hat = (random.random() * 2.0 - 1.0) * 0.09 * open_hat_env

            sample = int((snare + lead + open_hat) * 32767 * 0.65)
            buf.append(max(-32767, min(32767, sample)))

        self._apply_loop_window(buf, n)
        return bytes(buf)

    def _build_layer_3_boss(self) -> bytes:
        """Layer 3: Boss Cataclysm (Heavy rock distorted bass chug & brass chord stabs)."""
        n = int(self.SR * self.LOOP_DURATION)
        buf = array.array('h')
        power_roots = [73.42, 73.42, 58.27, 58.27, 87.31, 87.31, 65.41, 65.41]  # D, Bb, F, C

        for i in range(n):
            t = i / self.SR
            beat = t * 2.0

            # Distorted bass overdrive power-chug (16th rhythm)
            chug_step = beat * 4.0
            r_idx = int(chug_step * 0.25) % len(power_roots)
            rf = power_roots[r_idx]
            chug_env = math.exp(-9.0 * (chug_step % 1.0))
            raw_wave = (
                math.sin(2 * math.pi * rf * t)
                + 0.5 * math.sin(2 * math.pi * (rf * 1.5) * t)
                + 0.3 * math.sin(2 * math.pi * (rf * 2.0) * t)
            )
            # Soft-clip saturation / distortion
            distorted = math.tanh(raw_wave * 2.2) * 0.19 * chug_env

            # Dramatic Brass / Choir Stabs on key beat accents (beats 0, 3, 5)
            brass_accent = beat % 8.0
            is_accent = (brass_accent < 0.35) or (3.0 <= brass_accent < 3.35) or (5.0 <= brass_accent < 5.35)
            brass = 0.0
            if is_accent:
                b_env = math.exp(-5.0 * (brass_accent % 1.0))
                brass = (
                    math.sin(2 * math.pi * 293.66 * t)
                    + math.sin(2 * math.pi * 349.23 * t)
                    + math.sin(2 * math.pi * 440.00 * t)
                ) * 0.12 * b_env

            sample = int((distorted + brass) * 32767 * 0.70)
            buf.append(max(-32767, min(32767, sample)))

        self._apply_loop_window(buf, n)
        return bytes(buf)

    def prepare_buffers(self) -> None:
        """Pre-generate procedural audio buffers for all 4 dynamic layers."""
        if self._buffers_built:
            return
        self._raw_buffers[0] = self._build_layer_0_ambient()
        self._raw_buffers[1] = self._build_layer_1_pulse()
        self._raw_buffers[2] = self._build_layer_2_climax()
        self._raw_buffers[3] = self._build_layer_3_boss()
        self._buffers_built = True

    # -------------------------------------------------------------------------
    # Channel & Playback Management
    # -------------------------------------------------------------------------
    def _ensure_channels(self) -> bool:
        """Ensure pygame mixer channels are allocated and available."""
        try:
            if not pygame.mixer.get_init():
                return False
            curr_channels = pygame.mixer.get_num_channels()
            if curr_channels < 16:
                pygame.mixer.set_num_channels(16)
            for idx, ch_num in enumerate(self.channel_indices):
                self.channels[idx] = pygame.mixer.Channel(ch_num)
            return True
        except Exception:
            return False

    def start(self) -> None:
        """Start all 4 synchronized layers playing in phase loops."""
        self.prepare_buffers()
        if not self._ensure_channels():
            self.active = True
            return

        master_music_vol = self._get_master_music_volume()

        try:
            for i in range(4):
                if self.sounds[i] is None and self._raw_buffers[i] is not None:
                    self.sounds[i] = pygame.mixer.Sound(buffer=self._raw_buffers[i])
                ch = self.channels[i]
                snd = self.sounds[i]
                if ch is not None and snd is not None:
                    vol = self.current_volumes[i] * master_music_vol
                    snd.set_volume(vol)
                    ch.play(snd, loops=-1)
                    ch.set_volume(vol)
            self.active = True
            self.paused = False
        except Exception:
            self.active = True

    def stop(self) -> None:
        """Stop all dynamic audio tracks."""
        self.active = False
        self.paused = False
        for ch in self.channels:
            if ch is not None:
                try:
                    ch.stop()
                except Exception:
                    pass

    def pause(self) -> None:
        """Pause playback across all 4 dynamic tracks."""
        self.paused = True
        for ch in self.channels:
            if ch is not None:
                try:
                    ch.pause()
                except Exception:
                    pass

    def unpause(self) -> None:
        """Resume playback across all 4 dynamic tracks."""
        self.paused = False
        for ch in self.channels:
            if ch is not None:
                try:
                    ch.unpause()
                except Exception:
                    pass

    def _get_master_music_volume(self) -> float:
        """Retrieve the effective master music volume from SoundEngine or fallback."""
        if self.sound_engine is None:
            return 0.5
        if getattr(self.sound_engine, "muted", False):
            return 0.0
        try:
            import audio_settings
            eff = audio_settings.effective_volumes(self.sound_engine.volumes)
            return float(eff.get("music", 0.5))
        except Exception:
            return 0.5

    # -------------------------------------------------------------------------
    # Real-Time Dynamic Intensity Scaling
    # -------------------------------------------------------------------------
    def update(
        self,
        enemy_count: int,
        boss_count: int,
        player_hp_pct: float = 1.0,
    ) -> None:
        """
        Evaluate battlefield threat level and crossfade dynamic tracks smoothly:
          - enemy_count: 0-20 (Calm/Base), 20-60 (Escalating), 60-150+ (Swarm Climax)
          - boss_count: > 0 triggers Boss Cataclysm power layer
          - player_hp_pct: low HP (< 35%) raises urgency and brings in climax beats early
        """
        if not self.active or self.paused:
            return

        # Target Volume Calculations
        # Layer 0: Always audible background baseline
        self.target_volumes[0] = 0.85

        # Layer 1 (Pulse): Ramps in between 15 and 45 enemies
        if enemy_count < 15:
            self.target_volumes[1] = 0.0
        elif enemy_count < 45:
            self.target_volumes[1] = (enemy_count - 15) / 30.0
        else:
            self.target_volumes[1] = 1.0

        # Layer 2 (Swarm Climax): Ramps in between 55 and 110 enemies, or if player is near death
        if player_hp_pct < 0.35:
            self.target_volumes[2] = 1.0
        elif enemy_count < 55:
            self.target_volumes[2] = 0.0
        elif enemy_count < 110:
            self.target_volumes[2] = (enemy_count - 55) / 55.0
        else:
            self.target_volumes[2] = 1.0

        # Layer 3 (Boss Cataclysm): Activated when any boss is present
        self.target_volumes[3] = 1.0 if boss_count > 0 else 0.0

        # Exponential Volume Smoothing (smooth ~1 second crossfades)
        master_music_vol = self._get_master_music_volume()
        for i in range(4):
            self.current_volumes[i] = lerp(self.current_volumes[i], self.target_volumes[i], 0.06)
            eff_vol = clamp(self.current_volumes[i] * master_music_vol, 0.0, 1.0)
            ch = self.channels[i]
            if ch is not None:
                try:
                    ch.set_volume(eff_vol)
                except Exception:
                    pass

    def apply_volume(self) -> None:
        """Force re-application of current layer volumes (e.g. after slider changes)."""
        master_music_vol = self._get_master_music_volume()
        for i in range(4):
            eff_vol = clamp(self.current_volumes[i] * master_music_vol, 0.0, 1.0)
            ch = self.channels[i]
            if ch is not None:
                try:
                    ch.set_volume(eff_vol)
                except Exception:
                    pass

    def get_debug_state(self) -> Dict[str, Any]:
        """Inspection snapshot for unit tests and telemetry."""
        return {
            "active": self.active,
            "paused": self.paused,
            "target_volumes": [round(v, 3) for v in self.target_volumes],
            "current_volumes": [round(v, 3) for v in self.current_volumes],
            "master_music_volume": round(self._get_master_music_volume(), 3),
        }


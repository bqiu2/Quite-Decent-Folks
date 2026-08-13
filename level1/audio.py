"""Small procedural chiptune soundtrack and level-one sound effects."""

from __future__ import annotations

from array import array
import math
import random
import sys

import pygame

from shared_game_data import ElementType

from .config import AUDIO_SAMPLE_RATE, MUSIC_VOLUME, SOUND_EFFECT_VOLUME


COLLECT_FREQUENCIES: dict[ElementType, float] = {
    "water": 587.33,
    "light": 783.99,
    "nitrogen": 659.25,
    "phosphorus": 698.46,
    "potassium": 523.25,
    "pesticide": 880.00,
}


def _envelope(time_value: float, duration: float, attack: float, release: float) -> float:
    attack_gain = min(1.0, time_value / max(attack, 1e-6))
    release_gain = min(1.0, (duration - time_value) / max(release, 1e-6))
    return max(0.0, min(attack_gain, release_gain))


def _to_pcm(samples: list[float], channels: int) -> bytes:
    pcm = array("h")
    for sample in samples:
        value = round(max(-1.0, min(1.0, sample)) * 32767)
        for _ in range(channels):
            pcm.append(value)
    if sys.byteorder != "little":
        pcm.byteswap()
    return pcm.tobytes()


def _sequence_pcm(
    notes: list[tuple[float, float]],
    sample_rate: int,
    channels: int,
    *,
    volume: float,
) -> bytes:
    samples: list[float] = []
    phase = 0.0
    for frequency, duration in notes:
        frame_count = max(1, round(duration * sample_rate))
        for frame in range(frame_count):
            t = frame / sample_rate
            if frequency <= 0.0:
                wave = 0.0
            else:
                phase += frequency / sample_rate
                wave = 1.0 if phase % 1.0 < 0.5 else -1.0
            gain = _envelope(t, duration, 0.008, min(0.045, duration * 0.35))
            samples.append(wave * gain * volume)
    return _to_pcm(samples, channels)


def _collect_pcm(
    element: ElementType,
    sample_rate: int,
    channels: int,
) -> bytes:
    base = COLLECT_FREQUENCIES[element]
    notes = [(base, 0.075), (base * 1.25, 0.065), (base * 1.50, 0.09)]
    return _sequence_pcm(notes, sample_rate, channels, volume=0.42)


def _hurt_pcm(sample_rate: int, channels: int) -> bytes:
    duration = 0.28
    frame_count = round(duration * sample_rate)
    samples: list[float] = []
    phase = 0.0
    rng = random.Random(2026)
    for frame in range(frame_count):
        t = frame / sample_rate
        frequency = 240.0 - 150.0 * (t / duration)
        phase += frequency / sample_rate
        square = 1.0 if phase % 1.0 < 0.5 else -1.0
        noise = rng.uniform(-1.0, 1.0)
        gain = _envelope(t, duration, 0.004, 0.10)
        samples.append((square * 0.58 + noise * 0.42) * gain * 0.48)
    return _to_pcm(samples, channels)


def _music_pcm(sample_rate: int, channels: int) -> bytes:
    melody = [
        523.25, 659.25, 783.99, 659.25,
        587.33, 698.46, 880.00, 698.46,
        493.88, 587.33, 739.99, 587.33,
        523.25, 659.25, 783.99, 987.77,
        880.00, 783.99, 698.46, 587.33,
        659.25, 783.99, 987.77, 783.99,
        587.33, 698.46, 880.00, 698.46,
        523.25, 587.33, 659.25, 493.88,
    ]
    bass_roots = [130.81, 146.83, 123.47, 130.81]
    note_duration = 0.18
    samples: list[float] = []
    melody_phase = 0.0
    bass_phase = 0.0

    for index, frequency in enumerate(melody):
        bass = bass_roots[(index // 8) % len(bass_roots)]
        frame_count = round(note_duration * sample_rate)
        for frame in range(frame_count):
            t = frame / sample_rate
            melody_phase += frequency / sample_rate
            bass_phase += bass / sample_rate
            melody_wave = 1.0 if melody_phase % 1.0 < 0.5 else -1.0
            bass_position = bass_phase % 1.0
            bass_wave = 4.0 * abs(bass_position - 0.5) - 1.0
            note_gain = _envelope(t, note_duration, 0.006, 0.035)
            beat_gain = 1.0 if frame < sample_rate * 0.025 else 0.0
            beat = math.sin(2.0 * math.pi * 72.0 * t) * beat_gain
            mixed = melody_wave * 0.14 * note_gain + bass_wave * 0.10 + beat * 0.07
            samples.append(mixed)
    return _to_pcm(samples, channels)


class AudioManager:
    """Own level-one mixer channels while tolerating unavailable audio devices."""

    def __init__(self) -> None:
        self.enabled = False
        self.muted = False
        self.error: str | None = None
        self.collect_sounds: dict[ElementType, pygame.mixer.Sound] = {}
        self.hurt_sound: pygame.mixer.Sound | None = None
        self.music_sound: pygame.mixer.Sound | None = None
        self.music_channel: pygame.mixer.Channel | None = None
        self.collect_channel: pygame.mixer.Channel | None = None
        self.hurt_channel: pygame.mixer.Channel | None = None

        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(
                    frequency=AUDIO_SAMPLE_RATE,
                    size=-16,
                    channels=2,
                    buffer=512,
                )
            sample_rate, _, channels = pygame.mixer.get_init()
            pygame.mixer.set_num_channels(max(8, pygame.mixer.get_num_channels()))
            pygame.mixer.set_reserved(3)
            self.music_channel = pygame.mixer.Channel(0)
            self.collect_channel = pygame.mixer.Channel(1)
            self.hurt_channel = pygame.mixer.Channel(2)
            self.collect_sounds = {
                element: pygame.mixer.Sound(
                    buffer=_collect_pcm(element, sample_rate, channels)
                )
                for element in COLLECT_FREQUENCIES
            }
            self.hurt_sound = pygame.mixer.Sound(
                buffer=_hurt_pcm(sample_rate, channels)
            )
            self.music_sound = pygame.mixer.Sound(
                buffer=_music_pcm(sample_rate, channels)
            )
            self._apply_volumes()
            self.enabled = True
        except (pygame.error, OSError, ValueError) as exc:
            self.error = str(exc)

    def _apply_volumes(self) -> None:
        effect_volume = 0.0 if self.muted else SOUND_EFFECT_VOLUME
        music_volume = 0.0 if self.muted else MUSIC_VOLUME
        if self.collect_channel is not None:
            self.collect_channel.set_volume(effect_volume)
        if self.hurt_channel is not None:
            self.hurt_channel.set_volume(effect_volume)
        if self.music_channel is not None:
            self.music_channel.set_volume(music_volume)

    def start_music(self) -> None:
        if self.enabled and self.music_channel is not None and self.music_sound is not None:
            self.music_channel.play(self.music_sound, loops=-1)

    def play_collect(self, element: ElementType) -> None:
        if self.enabled and self.collect_channel is not None:
            self.collect_channel.play(self.collect_sounds[element])

    def play_hurt(self) -> None:
        if self.enabled and self.hurt_channel is not None and self.hurt_sound is not None:
            self.hurt_channel.play(self.hurt_sound)

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        self._apply_volumes()
        return self.muted

    def close(self) -> None:
        for channel in (self.music_channel, self.collect_channel, self.hurt_channel):
            if channel is not None:
                channel.stop()


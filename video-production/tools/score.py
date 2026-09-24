#!/usr/bin/env python3
"""Temp score + sound design for the Sydney animatic, synthesized from scratch.

No samples, no third-party audio: every sound is sine/FM/filtered-noise synthesis,
placed on the cue sheet defined in sound-design.md. It is a TEMP track for the
animatic only — the final film uses a commissioned or licensed score and foley.

    python3 tools/score.py main  assets/music/temp-score-main.wav
    python3 tools/score.py 15    assets/music/temp-score-15s.wav
    python3 tools/score.py 06    assets/music/temp-score-06s.wav

The output is normalized to -14 LUFS with linear gain and an ffmpeg peak limiter
(-1.5 dBFS), so the silence at 00:17.50 stays digital silence.
"""
import json
import subprocess
import sys
import wave

import numpy as np

SR = 48000
RNG = np.random.default_rng(7)

NOTE = {}
for i, n in enumerate(['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']):
    for octv in range(0, 8):
        NOTE[f'{n}{octv}'] = 440.0 * 2 ** ((i - 9) / 12 + (octv - 4))


def hz(n):
    return NOTE[n] if isinstance(n, str) else n


def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def db(x):
    return 10 ** (x / 20)


# ---------------------------------------------------------------- filters
def band(x, lo, hi, soft=0.15):
    """Zero-phase FFT band-pass with soft edges (numpy only)."""
    n = len(x)
    if n < 16:
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    m = np.ones_like(f)
    if lo > 0:
        m *= 1 / (1 + (lo / np.maximum(f, 1e-3)) ** (2 / soft * 0.2))
    if hi < SR / 2:
        m *= 1 / (1 + (f / hi) ** (2 / soft * 0.2))
    return np.fft.irfft(X * m, n)


def pink(dur):
    n = int(dur * SR)
    X = np.fft.rfft(RNG.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    X /= np.sqrt(np.maximum(f, 20))
    y = np.fft.irfft(X, n)
    return y / (np.abs(y).max() + 1e-9)


def noise(dur):
    return RNG.standard_normal(int(dur * SR))


def env_exp(dur, attack, tau):
    t = t_axis(dur)
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-np.maximum(t - attack, 0) / tau)


def env_ar(dur, attack, release):
    t = t_axis(dur)
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    r = np.clip((dur - t) / max(release, 1e-4), 0, 1)
    return a * r


# ---------------------------------------------------------------- instruments
def beep(f, dur=0.19):
    t = t_axis(dur)
    f = hz(f)
    y = np.sin(2 * np.pi * f * t) + 0.22 * np.sin(2 * np.pi * 2 * f * t) + 0.06 * np.sin(2 * np.pi * 3 * f * t)
    return y * env_ar(dur, 0.004, 0.07) * 0.5


def pluck(f, dur=1.6, bright=1.0):
    t = t_axis(dur)
    f = hz(f)
    y = (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.9)
         + 0.28 * bright * np.sin(2 * np.pi * 3.92 * f * t) * np.exp(-t / 0.16)
         + 0.08 * bright * np.sin(2 * np.pi * 9.2 * f * t) * np.exp(-t / 0.05))
    return y * np.clip(t / 0.002, 0, 1) * 0.45


def piano(f, dur=3.0, vel=1.0):
    t = t_axis(dur)
    f = hz(f)
    y = np.zeros_like(t)
    B = 0.00035
    for k in range(1, 9):
        fk = f * k * np.sqrt(1 + B * k * k)
        if fk > 9000:
            break
        amp = (1 / k ** 1.5) * (0.6 + 0.4 * vel) ** (k - 1)
        tau = 2.4 / (k ** 0.6) * (1.3 if f < 200 else 1.0)
        y += amp * np.sin(2 * np.pi * fk * t + k) * np.exp(-t / tau)
    thump = band(noise(0.03), 80, 900) * env_exp(0.03, 0.001, 0.008) * 0.3
    y[:len(thump)] += thump
    return y * np.clip(t / 0.006, 0, 1) * 0.28 * vel


def pad(notes, dur, attack=1.4, release=1.6, level=1.0, bright=0.3):
    t = t_axis(dur)
    y = np.zeros_like(t)
    for n in notes:
        f = hz(n)
        for d in (-0.0028, 0.0, 0.0031):
            y += np.sin(2 * np.pi * f * (1 + d) * t + RNG.random() * 6)
            y += bright * 0.35 * np.sin(2 * np.pi * 2 * f * (1 + d) * t)
    y *= (1 + 0.08 * np.sin(2 * np.pi * 0.23 * t)) / (3 * len(notes))
    return y * env_ar(dur, attack, release) * 0.5 * level


def drone(dur, sweep_from=None):
    t = t_axis(dur)
    f = hz('E2')
    y = np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * 1.5 * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t)
    trem = 1 + 0.12 * np.sin(2 * np.pi * 0.17 * t)
    bright = np.zeros_like(t)
    if sweep_from is not None:
        bright = np.clip((t - sweep_from) / (dur - sweep_from), 0, 1) ** 1.5
    for k in (3, 4, 5, 6, 8):
        y += bright * (0.35 / k) * np.sin(2 * np.pi * k * f * t)
    return y * trem * env_ar(dur, 1.2, 0.01) * 0.22


def kick():
    d = 0.22
    t = t_axis(d)
    fr = 45 + 75 * np.exp(-t / 0.03)
    ph = 2 * np.pi * np.cumsum(fr) / SR
    return np.sin(ph) * env_exp(d, 0.002, 0.07) * 0.55


def shaker(level=1.0):
    d = 0.06
    return band(noise(d), 5000, 16000) * env_exp(d, 0.006, 0.018) * 0.06 * level


def sub(f, dur):
    t = t_axis(dur)
    return np.sin(2 * np.pi * hz(f) * t) * env_ar(dur, 0.05, 0.4) * 0.25


# ---------------------------------------------------------------- foley
def click(level=1.0, lo=1200, hi=7000, dur=0.012):
    return band(noise(dur), lo, hi) * env_exp(dur, 0.0005, 0.002) * 0.5 * level


def lamp_click():
    y = np.zeros(int(0.08 * SR))
    a = click(1.0, 800, 6000) + 0
    y[:len(a)] += a
    lo = np.sin(2 * np.pi * 180 * t_axis(0.02)) * env_exp(0.02, 0.0005, 0.005) * 0.25
    y[:len(lo)] += lo
    b = click(0.45, 900, 5000)
    y[int(0.035 * SR):int(0.035 * SR) + len(b)] += b
    return y


def lid_thock():
    d = 0.14
    t = t_axis(d)
    y = np.sin(2 * np.pi * 105 * t) * env_exp(d, 0.001, 0.035) * 0.6
    y += band(noise(d), 200, 1600) * env_exp(d, 0.001, 0.02) * 0.25
    return y


def pencil(dur, level=1.0):
    n = noise(dur)
    strokes = np.abs(band(noise(dur), 8, 40))
    strokes /= strokes.max() + 1e-9
    return band(n, 2200, 7500) * strokes * env_ar(dur, 0.02, 0.05) * 0.18 * level


def crinkle(dur=0.35):
    y = np.zeros(int(dur * SR))
    for _ in range(38):
        c = click(RNG.uniform(0.2, 0.8), 1500, 9000, 0.006)
        i = int(RNG.uniform(0, dur - 0.01) * SR)
        y[i:i + len(c)] += c
    return y * 0.5


def exhale(dur=0.6, level=1.0):
    t = t_axis(dur)
    return band(noise(dur), 300, 2000) * np.sin(np.pi * t / dur) ** 2 * 0.05 * level


def rustle(dur=0.4, level=1.0):
    t = t_axis(dur)
    return band(noise(dur), 500, 4500) * np.sin(np.pi * t / dur) ** 1.5 * 0.06 * level


def creak(dur=0.3):
    t = t_axis(dur)
    f = 260 + 60 * np.sin(2 * np.pi * 7 * t)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 38 * t)))
    return band(y, 200, 2500) * np.sin(np.pi * t / dur) * 0.05


def footstep(level=1.0):
    d = 0.09
    t = t_axis(d)
    return (np.sin(2 * np.pi * 85 * t) * env_exp(d, 0.002, 0.025) * 0.35 + band(noise(d), 300, 3000) * env_exp(d, 0.001, 0.015) * 0.08) * level


def door(level=1.0):
    d = 0.4
    y = np.zeros(int(d * SR))
    c = click(0.6, 1500, 6000, 0.015)
    y[:len(c)] += c
    t = t_axis(0.25)
    th = np.sin(2 * np.pi * 70 * t) * env_exp(0.25, 0.003, 0.06) * 0.5 + band(noise(0.25), 150, 2500) * env_exp(0.25, 0.002, 0.04) * 0.2
    i = int(0.12 * SR)
    y[i:i + len(th)] += th
    return y * level


def spoon():
    d = 0.5
    t = t_axis(d)
    y = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / tau) for f, a, tau in ((2350, 1, .22), (5120, .5, .12), (7900, .25, .07)))
    return y * np.clip(t / 0.0008, 0, 1) * 0.08


def ui_tick(f='E6', level=1.0):
    d = 0.07
    t = t_axis(d)
    return np.sin(2 * np.pi * hz(f) * t) * env_exp(d, 0.001, 0.018) * 0.22 * level


def chime(f='G#5'):
    d = 0.9
    t = t_axis(d)
    f = hz(f)
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2.76 * f * t) * np.exp(-t / .1)) * env_exp(d, 0.002, 0.3) * 0.12


def swoosh(dur=0.35, level=1.0):
    t = t_axis(dur)
    return band(noise(dur), 400, 3000) * np.sin(np.pi * t / dur) ** 2 * 0.025 * level


def scooter(dur=1.3):
    t = t_axis(dur)
    f = 96 - 12 * (t / dur)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = sum((1 / k) * np.sin(k * ph) for k in range(1, 12))
    y = band(y, 60, 1800)
    return y * np.exp(-((t - dur / 2) / (dur / 3.2)) ** 2) * 0.03


def room(dur, level_db, lo=40, hi=2500):
    return band(pink(dur), lo, hi) * db(level_db)


def hum(dur, level_db):
    t = t_axis(dur)
    y = 0.6 * np.sin(2 * np.pi * 100 * t) + 0.3 * np.sin(2 * np.pi * 150 * t) + 0.15 * np.sin(2 * np.pi * 200 * t)
    y += band(pink(dur), 60, 900) * 0.5
    return y * db(level_db)


def fan(dur, level_db):
    t = t_axis(dur)
    return (band(noise(dur), 300, 3500) * 0.3 + 0.05 * np.sin(2 * np.pi * 1210 * t)) * db(level_db)


# ---------------------------------------------------------------- mixing
class Mix:
    def __init__(self, dur):
        self.dur = dur
        n = int(dur * SR)
        self.buses = {k: np.zeros((n, 2)) for k in ('music', 'fx', 'amb')}

    def add(self, bus, at, sig, gain_db=0.0, pan=0.0):
        if sig.ndim == 1:
            l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
            sig = np.stack([sig * l * 1.414, sig * r * 1.414], axis=1)
        i = int(round(at * SR))
        b = self.buses[bus]
        if i >= len(b):
            return
        j = min(len(b), i + len(sig))
        b[i:j] += sig[: j - i] * db(gain_db)

    def gate(self, a, b, fade=0.01, buses=None):
        """Hard silence between a and b (with a tiny anti-click fade)."""
        for name, buf in self.buses.items():
            if buses and name not in buses:
                continue
            ia, ib = int(a * SR), int(b * SR)
            nf = int(fade * SR)
            buf[max(0, ia - nf):ia] *= np.linspace(1, 0, min(nf, ia))[:, None]
            buf[ia:ib] = 0

    def render(self):
        music = self.buses['music']
        music = music + 0.28 * reverb(music, 2.2)
        fx = self.buses['fx'] + 0.08 * reverb(self.buses['fx'], 0.8)
        out = music + fx + self.buses['amb']
        return out


def reverb(x, rt):
    n_ir = int(rt * SR)
    t = np.arange(n_ir) / SR
    irL = RNG.standard_normal(n_ir) * np.exp(-6.9 * t / rt)
    irR = RNG.standard_normal(n_ir) * np.exp(-6.9 * t / rt)
    irL, irR = band(irL, 150, 6000), band(irR, 150, 6000)
    irL[: int(0.012 * SR)] = 0
    irR[: int(0.017 * SR)] = 0
    out = np.zeros_like(x)
    N = 1 << int(np.ceil(np.log2(len(x) + n_ir)))
    for c, ir in ((0, irL), (1, irR)):
        y = np.fft.irfft(np.fft.rfft(x[:, c], N) * np.fft.rfft(ir / np.sqrt((ir ** 2).sum()), N), N)
        out[:, c] = y[: len(x)]
    return out


def eighths(a, b, step=0.3125):
    t = a
    while t < b - 1e-6:
        yield t
        t += step


# ---------------------------------------------------------------- cue sheets
def sonic_logo(m, at, fade_end):
    for k, n in enumerate(['B4', 'E5', 'G#5']):
        m.add('music', at + 0.25 * k, pluck(n, 2.2), -2, pan=(k - 1) * 0.15)
        m.add('music', at + 0.25 * k, beep(n, 0.12), -14)
    c = at + 0.75
    for n in ['E2', 'B2', 'E3', 'G#3', 'B3', 'E4']:
        m.add('music', c, piano(n, fade_end - c + 0.5, 0.8), -4)
    for n in ['E5', 'G#5', 'B5']:
        m.add('music', c, pluck(n, 2.8, 0.6), -8)
    m.add('music', c, pad(['E3', 'B3', 'E4', 'G#4'], fade_end - c, 0.6, 1.2, 1.0, 0.4), -6)


def cue_main(m):
    D = m.dur
    # ---- Act I: day
    m.add('amb', 0, room(7.0, -36), 0)
    m.add('fx', 0.46, click(0.8, 3000, 9000, 0.008), -6)
    m.add('fx', 0.50, beep('B4'), -2)
    m.add('amb', 0.9, creak(0.35), -18, pan=0.6)
    m.add('fx', 1.90, rustle(0.35), -6, pan=0.3)
    m.add('fx', 2.25, beep('E5'), -2)
    m.add('fx', 3.75, beep('G#5'), -2)
    m.add('music', 3.75, pad(['E3', 'B3', 'F#4', 'G#4'], 3.2, 0.25, 0.05, 0.9), -3)
    for n in ['E2', 'E3', 'B3', 'F#4', 'G#4']:
        m.add('music', 3.75, piano(n, 3.2, 0.9), -3)
    for n in ['C#3', 'G#3', 'B3', 'E4']:
        m.add('music', 6.25, piano(n, 0.7, 0.7), -5)
    for k, n in enumerate(['B5', 'E6', 'G#6']):
        m.add('music', 4.375 + 0.3125 * k, pluck(n, 1.2), -16, pan=0.2)
    for t in eighths(3.75, 6.85):
        m.add('music', t, shaker(1 if int(round((t - 3.75) / 0.3125)) % 2 else 0.6), -4)
    for i, t in enumerate(np.arange(4.6, 6.2, 0.42)):
        m.add('fx', t, footstep(0.8), -10, pan=-0.2 - 0.1 * i)
    m.add('fx', 6.40, click(0.6, 1500, 6000, 0.015), -8, pan=-0.6)
    m.add('amb', 6.40, room(0.5, -30, 100, 5000), 0, pan=-0.6)
    m.gate(6.85, 7.19, buses=['music'])  # the music stops dead on the door close
    m.add('fx', 6.85, door(0.9), -6, pan=-0.6)
    # ---- Act II: night 1
    m.add('amb', 6.80, hum(10.70, -40), 0)
    m.add('fx', 7.50, lamp_click(), -4)
    m.add('fx', 7.55, click(0.15, 3000, 8000, 0.004), -10)
    m.add('music', 7.20, drone(10.30, sweep_from=8.05), -2)
    m.add('music', 8.50, pad(['F#4', 'E4'], 9.0, 2.0, 0.01, 0.55, 0.1), -6)
    m.add('amb', 8.50, fan(9.0, -44), 0)
    m.add('amb', 9.50, scooter(1.3), -4, pan=-0.5)
    m.add('amb', 10.10, scooter(1.0)[: int(0.7 * SR)], -8, pan=0.5)
    m.add('fx', 10.30, click(0.35, 2000, 7000, 0.006), -8)
    m.add('fx', 11.60, pencil(0.6), -2, pan=0.1)
    m.add('fx', 12.55, pencil(0.28, 2.0), -1, pan=0.1)
    m.add('fx', 12.90, crinkle(), -6, pan=0.3)
    m.add('fx', 13.90, click(0.35, 2000, 7000, 0.006), -8)
    m.add('fx', 14.40, rustle(0.3, 0.8), -6)
    m.add('fx', 14.70, exhale(0.6), 0)
    m.add('fx', 15.60, creak(0.3), -2)
    m.add('fx', 15.80, rustle(0.5), -6)
    m.gate(17.50, 18.60)
    # ---- Act III: the turn
    m.add('music', 18.60, piano('E5', 3.0, 0.8), -2)
    # ---- Act IV: discovery
    m.add('amb', 20.00, room(1.4, -38), 0)
    m.add('fx', 20.46, click(0.8, 3000, 9000, 0.008), -6)
    m.add('fx', 20.50, beep('B4'), -2)
    chords = [(20.50, ['E3', 'B3', 'F#4', 'G#4']), (23.00, ['C#3', 'G#3', 'B3', 'E4']), (25.50, ['A2', 'E3', 'B3', 'C#4']), (28.00, ['B2', 'F#3', 'B3', 'E4'])]
    for i, (a, ns) in enumerate(chords):
        dur = (chords[i + 1][0] if i + 1 < len(chords) else 29.0) - a
        m.add('music', a, pad(ns, dur + 0.3, 0.3 if i == 0 else 0.15, 0.3, 1.0, 0.35), -4)
    for t in np.arange(20.50, 29.0, 1.25):
        m.add('music', t, kick(), -3)
    for t in eighths(20.50, 29.0):
        m.add('music', t, shaker(1 if int(round((t - 20.5) / 0.3125)) % 2 else 0.55), -3)
    motif = ['B4', 'E5', 'G#5', 'E5']
    for k, t in enumerate(eighths(21.75, 28.9)):
        n = motif[k % 4]
        m.add('music', t, pluck(n, 1.0, 0.8), -9, pan=0.25 if k % 2 else -0.25)
        if t >= 25.25:
            m.add('music', t, pluck(hz(n) * 2, 0.8, 0.5), -17)
    for a, f in ((25.25, 'E1'), (25.50, 'A1'), (28.00, 'B1')):
        m.add('music', a, sub(f, 2.6 if a != 25.25 else 0.3), -3)
    m.add('fx', 21.45, swoosh(0.35), 0)
    m.add('fx', 21.50, ui_tick('E6'), 0)
    for t, n in ((25.30, 'E6'), (25.55, 'G#6'), (25.80, 'B6')):
        m.add('fx', t, ui_tick(n, 0.6), -3)
    m.add('music', 26.45, pluck('E5', 1.6, 0.4), -4)
    m.add('music', 26.45, pluck('G#5', 1.6, 0.4), -6)
    # ---- Act V: night 2
    m.add('amb', 28.75, hum(7.9, -44), 0)
    m.add('music', 29.00, pad(['E3', 'B3', 'F#4', 'G#4'], 2.6, 0.5, 0.4, 1.0, 0.25), -4)
    m.add('music', 31.50, pad(['A2', 'E3', 'B3', 'C#4'], 2.6, 0.3, 0.4, 1.0, 0.25), -5)
    m.add('music', 34.00, pad(['B2', 'F#3', 'B3', 'D#4'], 1.6, 0.3, 0.3, 1.0, 0.25), -5)
    m.add('music', 35.50, pad(['E3', 'B3', 'E4', 'G#4'], 2.9, 0.3, 2.4, 1.0, 0.25), -5)
    for n in ['E2', 'B2', 'G#3']:
        m.add('music', 29.00, piano(n, 3.0, 0.7), -5)
    for t, n in ((29.50, 'B4'), (30.125, 'E5'), (30.75, 'G#5'), (32.00, 'G#5'), (32.625, 'F#5'), (33.25, 'E5')):
        m.add('music', t, piano(n, 2.4, 0.75), -3)
    for n in ['A2', 'E3', 'C#4']:
        m.add('music', 31.50, piano(n, 2.5, 0.6), -7)
    for n in ['E2', 'B2', 'E3', 'G#3', 'B3']:
        m.add('music', 35.50, piano(n, 3.0, 0.7), -5)
    m.add('fx', 30.20, spoon(), -2)
    m.add('fx', 30.60, exhale(0.3, 0.5), -6)
    m.add('fx', 32.50, click(0.35, 2000, 7000, 0.006), -6)
    m.add('fx', 32.80, chime('G#5'), -2)
    m.add('fx', 32.85, swoosh(0.45), -2)
    m.add('fx', 34.90, exhale(0.5, 0.7), -2)
    m.add('fx', 36.10, lid_thock(), -2)
    m.add('fx', 36.75, lamp_click(), -4)
    m.add('fx', 37.00, creak(0.25), -8)
    m.add('fx', 37.20, rustle(0.35), -6)
    for i, t in enumerate(np.arange(37.30, 37.95, 0.2)):
        m.add('fx', t, footstep(0.6), -12, pan=-0.3 - 0.15 * i)
    m.add('fx', 38.20, door(0.6), -12, pan=-0.8)
    m.add('amb', 38.40, room(1.6, -40, 60, 1500), 0)
    # ---- End card
    m.add('music', 38.50, pad(['E3', 'B3', 'E4', 'G#4'], D - 38.5, 1.2, 0.8, 1.0, 0.3), -6)
    for n in ['E3', 'B3', 'G#4']:
        m.add('music', 38.50, piano(n, 3.0, 0.6), -8)
    m.add('music', 39.50, piano('B4', 2.0, 0.6), -6)
    sonic_logo(m, 41.00, D)


def cue_15(m):
    D = m.dur
    m.add('amb', 0, room(1.5, -36), 0)
    m.add('fx', 0.46, click(0.8, 3000, 9000, 0.008), -6)
    m.add('fx', 0.50, beep('B4'), -2)
    m.add('amb', 1.30, hum(4.2, -40), 0)
    m.add('music', 1.50, drone(4.0, sweep_from=2.0), -2)
    m.add('music', 1.75, pad(['F#4', 'E4'], 3.75, 1.2, 0.01, 0.55, 0.1), -6)
    m.add('amb', 1.50, fan(4.0, -44), 0)
    m.add('fx', 2.30, click(0.35, 2000, 7000, 0.006), -8)
    m.add('fx', 3.60, creak(0.3), -2)
    m.add('fx', 3.80, rustle(0.5), -6)
    m.gate(5.50, 6.25)
    m.add('fx', 6.40, swoosh(0.35), 0)
    m.add('fx', 6.45, ui_tick('E6'), 0)
    m.add('music', 6.25, pad(['E3', 'B3', 'F#4', 'G#4'], 3.0, 0.2, 0.3, 1.0, 0.35), -4)
    m.add('music', 9.25, pad(['A2', 'E3', 'B3', 'C#4'], 1.8, 0.15, 0.3, 1.0, 0.35), -4)
    for t in np.arange(6.25, 10.75, 1.25):
        m.add('music', t, kick(), -3)
    for t in eighths(6.25, 10.75):
        m.add('music', t, shaker(1 if int(round((t - 6.25) / 0.3125)) % 2 else 0.55), -3)
    motif = ['B4', 'E5', 'G#5', 'E5']
    for k, t in enumerate(eighths(6.5625, 10.7)):
        m.add('music', t, pluck(motif[k % 4], 1.0, 0.8), -9, pan=0.25 if k % 2 else -0.25)
    m.add('music', 9.25, sub('A1', 1.6), -3)
    for t, n in ((9.45, 'E6'), (9.70, 'G#6'), (9.95, 'B6')):
        m.add('fx', t, ui_tick(n, 0.6), -3)
    m.add('music', 10.60, pluck('E5', 1.6, 0.4), -4)
    m.add('music', 10.75, pad(['E3', 'B3', 'E4', 'G#4'], 1.2, 0.2, 0.6, 1.0, 0.25), -6)
    m.add('amb', 10.60, hum(1.2, -46), 0)
    m.add('fx', 11.60, lid_thock(), -2)
    m.add('music', 11.75, pad(['E3', 'B3', 'E4', 'G#4'], D - 11.75, 0.8, 0.6, 1.0, 0.3), -6)
    m.add('music', 11.85, piano('E4', 2.0, 0.6), -7)
    m.add('music', 12.30, piano('B4', 2.0, 0.6), -7)
    sonic_logo(m, 12.75, D)


def cue_06(m):
    D = m.dur
    m.add('amb', 0, room(2.75, -38), 0)
    m.add('fx', 0.46, click(0.8, 3000, 9000, 0.008), -6)
    m.add('fx', 0.50, beep('B4'), -2)
    m.add('fx', 1.40, swoosh(0.35), 0)
    m.add('fx', 1.45, ui_tick('E6'), 0)
    m.add('music', 2.75, pad(['E3', 'B3', 'E4'], 1.4, 0.8, 0.4, 0.6, 0.2), -12)
    sonic_logo(m, 4.00, D)


def fade_out(x, a, b):
    ia, ib = int(a * SR), int(b * SR)
    x[ia:ib] *= np.linspace(1, 0, ib - ia)[:, None] ** 1.5
    x[ib:] = 0
    return x


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def measure(src):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-i', src, '-af', 'loudnorm=I=-14:TP=-1:print_format=json', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    js = json.loads(r[r.rindex('{'):r.rindex('}') + 1])
    return float(js['input_i']), float(js['input_tp'])


def loudnorm(src, dst):
    """Linear gain to -14 LUFS, then a peak limiter at -1.5 dBFS (standard mastering chain)."""
    measured, _ = measure(src)
    gain = -14.0 - measured
    for _ in range(3):
        subprocess.run(['ffmpeg', '-hide_banner', '-y', '-i', src, '-af',
                        f'volume={gain:.2f}dB,alimiter=limit=0.84:attack=4:release=60:level=disabled',
                        '-ar', '48000', '-c:a', 'pcm_s24le', dst], capture_output=True, check=True)
        out_i, out_tp = measure(dst)
        if abs(out_i + 14.0) < 0.3:
            break
        gain += -14.0 - out_i
    return measured, out_i, out_tp, 'linear+limiter'


def main():
    cut, dst = sys.argv[1], sys.argv[2]
    dur = {'main': 45.0, '15': 15.0, '06': 6.0}[cut]
    m = Mix(dur)
    {'main': cue_main, '15': cue_15, '06': cue_06}[cut](m)
    x = m.render()
    if cut == 'main':
        x[int(17.50 * SR):int(18.60 * SR)] = 0  # reverb tails must not leak into the silence
    fade_out(x, dur - 0.8, dur)
    x /= np.abs(x).max() + 1e-9
    x *= 0.5
    tmp = dst + '.raw.wav'
    write_wav(tmp, x)
    measured, out_i, out_tp, kind = loudnorm(tmp, dst)
    subprocess.run(['rm', '-f', tmp])
    print(f'{cut}: measured {measured} LUFS -> {out_i} LUFS, TP {out_tp} dBTP ({kind}) -> {dst}')


if __name__ == '__main__':
    main()

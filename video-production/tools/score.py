#!/usr/bin/env python3
"""Temp score + sound design for "מרעש לבהירות" (From noise to clarity), 120 BPM, E major.

Synthesized from scratch with numpy (sine/additive/filtered-noise synthesis, no samples,
no third-party audio). It is a TEMP track: the final film should use a licensed or
commissioned track built on the same cue points (see sound-design.md).

    python3 tools/score.py main assets/music/temp-score-main.wav
    python3 tools/score.py 15   assets/music/temp-score-15.wav
    python3 tools/score.py 06   assets/music/temp-score-06.wav

The cutdowns are spliced from the main mix at the same source times the picture uses
(tools/film.html CUTS), so picture and sound stay in sync by construction. Output is
normalized to -14 LUFS (linear gain + ffmpeg peak limiter at -1.5 dBFS).
"""
import json
import subprocess
import sys
import wave

import numpy as np

SR = 48000
RNG = np.random.default_rng(11)
BEAT = 0.5          # 120 BPM
BAR = 2.0

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


# ------------------------------------------------------------------ dsp helpers
def band(x, lo, hi, order=4.0):
    n = len(x)
    if n < 16:
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    m = np.ones_like(f)
    if lo > 0:
        m *= 1 / (1 + (lo / np.maximum(f, 1e-3)) ** order)
    if hi < SR / 2:
        m *= 1 / (1 + (f / hi) ** order)
    return np.fft.irfft(X * m, n)


def noise(dur):
    return RNG.standard_normal(int(dur * SR))


def env_exp(dur, attack, tau):
    t = t_axis(dur)
    return np.clip(t / max(attack, 1e-4), 0, 1) * np.exp(-np.maximum(t - attack, 0) / tau)


def env_ar(dur, attack, release):
    t = t_axis(dur)
    return np.clip(t / max(attack, 1e-4), 0, 1) * np.clip((dur - t) / max(release, 1e-4), 0, 1)


def additive_saw(f, dur, bright=1.0, detune=(0.0,)):
    """Band-limited saw via additive synthesis; `bright` scales the harmonic roll-off."""
    t = t_axis(dur)
    y = np.zeros_like(t)
    for d in detune:
        fd = f * (1 + d)
        ph = RNG.random() * 6.28
        k = 1
        while fd * k < 9000 and k <= 24:
            y += (1 / k) * np.exp(-(k - 1) / (3.0 * bright)) * np.sin(2 * np.pi * fd * k * t + ph * k)
            k += 1
    return y / max(1, len(detune))


# ------------------------------------------------------------------ instruments
def beep(f, dur=0.16):
    t = t_axis(dur)
    f = hz(f)
    y = np.sin(2 * np.pi * f * t) + 0.22 * np.sin(2 * np.pi * 2 * f * t) + 0.07 * np.sin(2 * np.pi * 3 * f * t)
    return y * env_ar(dur, 0.003, 0.06) * 0.5


def pluck(f, dur=1.2, bright=1.0):
    t = t_axis(dur)
    f = hz(f)
    y = (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.5)
         + 0.3 * bright * np.sin(2 * np.pi * 3.92 * f * t) * np.exp(-t / 0.12)
         + 0.1 * bright * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 0.25))
    return y * np.clip(t / 0.002, 0, 1) * 0.45


def piano(f, dur=3.0, vel=1.0):
    t = t_axis(dur)
    f = hz(f)
    y = np.zeros_like(t)
    for k in range(1, 9):
        fk = f * k * np.sqrt(1 + 0.00035 * k * k)
        if fk > 9000:
            break
        y += (1 / k ** 1.5) * np.sin(2 * np.pi * fk * t + k) * np.exp(-t / (2.4 / k ** 0.6))
    return y * np.clip(t / 0.005, 0, 1) * 0.28 * vel


def pad(notes, dur, attack=0.4, release=0.8, bright=0.35):
    y = sum(additive_saw(hz(n), dur, bright, (-0.004, 0.0, 0.0045)) for n in notes) / len(notes)
    return y * env_ar(dur, attack, release) * 0.35


def stab(notes, dur=0.45, bright=1.4):
    y = sum(additive_saw(hz(n), dur, bright, (-0.006, 0.0, 0.007)) for n in notes) / len(notes)
    return y * env_exp(dur, 0.004, 0.14) * 0.55


def bass(f, dur, bright=0.8):
    f = hz(f)
    t = t_axis(dur)
    y = additive_saw(f, dur, bright) * 0.6 + np.sin(2 * np.pi * f * t) * 0.8
    return np.tanh(1.4 * y) * env_ar(dur, 0.004, 0.05) * 0.45


def kick(level=1.0):
    d = 0.32
    t = t_axis(d)
    fr = 48 + 110 * np.exp(-t / 0.035)
    y = np.sin(2 * np.pi * np.cumsum(fr) / SR) * env_exp(d, 0.001, 0.11)
    y[: int(0.004 * SR)] += band(noise(0.004), 2000, 9000) * 0.4
    return np.tanh(1.6 * y) * 0.75 * level


def clap(level=1.0):
    d = 0.25
    y = np.zeros(int(d * SR))
    for k, off in enumerate((0.0, 0.011, 0.022)):
        b = band(noise(0.012), 900, 3800) * env_exp(0.012, 0.0005, 0.004)
        i = int(off * SR)
        y[i:i + len(b)] += b * (0.8 if k < 2 else 1.0)
    tail = band(noise(0.2), 900, 3200) * env_exp(0.2, 0.001, 0.05)
    i = int(0.03 * SR)
    y[i:i + len(tail)] += tail * 0.7
    return y * 0.45 * level


def hat(level=1.0, open_=False):
    d = 0.16 if open_ else 0.05
    return band(noise(d), 7000, 18000) * env_exp(d, 0.0008, 0.07 if open_ else 0.014) * 0.28 * level


def impact(level=1.0):
    d = 1.4
    t = t_axis(d)
    fr = 34 + 40 * np.exp(-t / 0.08)
    y = np.sin(2 * np.pi * np.cumsum(fr) / SR) * env_exp(d, 0.002, 0.45) * 0.9
    y += band(noise(d), 60, 1400) * env_exp(d, 0.001, 0.12) * 0.5
    return np.tanh(1.3 * y) * 0.7 * level


def riser(dur, level=1.0):
    n = int(dur * SR)
    t = t_axis(dur)
    y = np.zeros(n)
    chunks = 24
    for c in range(chunks):
        a, b = c * n // chunks, (c + 1) * n // chunks
        lo = 300 * (1 + 12 * (c / chunks) ** 2)
        y[a:b] += band(noise((b - a) / SR + 0.02), lo, lo * 3)[: b - a]
    f = 180 * np.exp(np.log(1400 / 180) * t / dur)
    y += 0.25 * np.sin(2 * np.pi * np.cumsum(f) / SR)
    return y * (t / dur) ** 2.2 * 0.22 * level


def whoosh(dur=0.35, level=1.0, up=True):
    n = int(dur * SR)
    t = t_axis(dur)
    y = np.zeros(n)
    chunks = 10
    for c in range(chunks):
        a, b = c * n // chunks, (c + 1) * n // chunks
        k = c / chunks if up else 1 - c / chunks
        lo = 400 * (1 + 8 * k)
        y[a:b] = band(noise((b - a) / SR + 0.01), lo, lo * 4)[: b - a]
    return y * np.sin(np.pi * t / dur) ** 2 * 0.2 * level


def crash(level=1.0):
    d = 1.6
    return band(noise(d), 4000, 16000) * env_exp(d, 0.002, 0.45) * 0.12 * level


def cluster(dur=0.35):
    """Dissonant 'question' hit: minor-second cluster."""
    return stab(['E4', 'F4', 'A#4'], dur, 0.9) * 0.8


def ui_tick(f='E6', level=1.0):
    d = 0.07
    t = t_axis(d)
    return np.sin(2 * np.pi * hz(f) * t) * env_exp(d, 0.001, 0.018) * 0.3 * level


def key_click(level=1.0):
    return band(noise(0.006), 2500, 9000) * env_exp(0.006, 0.0003, 0.0015) * 0.35 * level


def chime(f='G#5'):
    d = 0.9
    t = t_axis(d)
    f = hz(f)
    return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2.76 * f * t) * np.exp(-t / .1)) * env_exp(d, 0.002, 0.3) * 0.16


# ------------------------------------------------------------------ mixing
class Mix:
    BUSES = ('drums', 'bass', 'music', 'fx')

    def __init__(self, dur):
        self.dur = dur
        self.n = int(dur * SR)
        self.b = {k: np.zeros((self.n, 2)) for k in self.BUSES}
        self.kicks = []

    def add(self, bus, at, sig, gain_db=0.0, pan=0.0):
        if sig.ndim == 1:
            l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
            sig = np.stack([sig * l * 1.414, sig * r * 1.414], axis=1)
        i = int(round(at * SR))
        if i >= self.n:
            return
        j = min(self.n, i + len(sig))
        self.b[bus][i:j] += sig[: j - i] * db(gain_db)

    def kick(self, at, level=1.0):
        self.kicks.append(at)
        self.add('drums', at, kick(level), 0)

    def sidechain(self, depth=0.55, tau=0.11):
        g = np.ones(self.n)
        t = np.arange(self.n) / SR
        for k in self.kicks:
            i = int(k * SR)
            seg = t[i:i + int(0.5 * SR)] - k
            g[i:i + len(seg)] = np.minimum(g[i:i + len(seg)], 1 - depth * np.exp(-seg / tau))
        return g[:, None]

    def render(self, gaps=()):
        music = self.b['music'] * self.sidechain()
        music = music + 0.22 * reverb(music, 1.6)
        bass_ = self.b['bass'] * self.sidechain(0.7, 0.09)
        fx = self.b['fx'] + 0.12 * reverb(self.b['fx'], 1.2)
        out = self.b['drums'] + bass_ + music + fx
        for a, b in gaps:
            out[int(a * SR):int(b * SR)] = 0
        return out


def reverb(x, rt):
    n_ir = int(rt * SR)
    t = np.arange(n_ir) / SR
    out = np.zeros_like(x)
    N = 1 << int(np.ceil(np.log2(len(x) + n_ir)))
    for c in range(2):
        ir = band(RNG.standard_normal(n_ir) * np.exp(-6.9 * t / rt), 200, 7000)
        ir[: int((0.012 + 0.005 * c) * SR)] = 0
        ir /= np.sqrt((ir ** 2).sum())
        out[:, c] = np.fft.irfft(np.fft.rfft(x[:, c], N) * np.fft.rfft(ir, N), N)[: len(x)]
    return out


# ------------------------------------------------------------------ the cue sheet (main, 30 s)
CHORDS = {  # chord -> (pad voicing, bass root)
    'E': (['E3', 'B3', 'F#4', 'G#4'], 'E1'),
    'C#m': (['C#3', 'G#3', 'B3', 'E4'], 'C#2'),
    'A': (['A2', 'E3', 'B3', 'C#4'], 'A1'),
    'B': (['B2', 'F#3', 'B3', 'D#4'], 'B1'),
}
PENTA = ['E5', 'F#5', 'G#5', 'B5', 'C#6', 'E6', 'B4', 'G#5']


def groove(m, a, b, prog_):
    """Drop groove from a to b; one chord per 2 s bar."""
    t = a
    while t < b - 1e-6:
        beat_in_bar = int(round((t - a) / BEAT)) % 4
        m.kick(t)
        if beat_in_bar in (1, 3):
            m.add('drums', t, clap(), -2)
        m.add('drums', t + 0.25, hat(), -2, pan=0.2)
        m.add('drums', t + 0.125, hat(0.35), -6, pan=-0.2)
        m.add('drums', t + 0.375, hat(0.35), -6, pan=-0.2)
        t += BEAT
    for k, bar in enumerate(np.arange(a, b - 1e-6, BAR)):
        voicing, root = CHORDS[prog_[k % len(prog_)]]
        dur = min(BAR, b - bar)
        m.add('music', bar, pad(voicing, dur + 0.1, 0.02, 0.1, 0.6), -2)
        for e in np.arange(0, dur - 1e-6, 0.25):
            if abs(e % 1.0 - 0.75) < 1e-6:
                continue
            m.add('bass', bar + e, bass(root, 0.2, 0.7), -1)
    motif = ['B4', 'E5', 'G#5', 'E5']
    for k, t in enumerate(np.arange(a, b - 1e-6, 0.25)):
        m.add('music', t, pluck(motif[k % 4], 0.6, 0.9), -9, pan=0.3 if k % 2 else -0.3)


def cue_main(m):
    # ---- Act A: the sales (0-4) — each amount is a beep; the beeps are the melody
    for t, n in ((0.0, 'B4'), (0.5, 'E5'), (1.0, 'G#5'), (1.5, 'B5')):
        m.add('fx', t, beep(n), -1)
        m.add('bass', t, np.sin(2 * np.pi * hz('E1') * t_axis(0.35)) * env_exp(0.35, 0.003, 0.12) * 0.7, -4)
    for k, t in enumerate(np.arange(2.0, 4.0, 0.25)):
        m.add('fx', t, beep(PENTA[k % len(PENTA)], 0.12), -8, pan=(k % 3 - 1) * 0.4)
    m.add('music', 2.0, stab(['E3', 'B3', 'E4', 'G#4', 'F#5']), -2)
    m.add('fx', 2.0, impact(0.6), -6)
    for t in np.arange(2.0, 4.0, BEAT):
        m.kick(t, 0.9)
        m.add('drums', t + 0.25, hat(), -3)
    # ---- Act B: the noise (4-7.75)
    for t in np.arange(4.0, 7.75, BEAT):
        m.kick(t)
        m.add('drums', t + 0.25, hat(), -2)
    for t in np.arange(4.0, 7.75, 0.125):
        m.add('drums', t, hat(0.25 + 0.5 * (t - 4) / 3.75), -8, pan=0.3)
    for t in (4.5, 5.5, 6.5, 7.5):
        m.add('drums', t, clap(), -2)
    for t in np.arange(4.0, 7.75, 0.25):
        m.add('bass', t, bass('E1', 0.22, 0.3 + 1.2 * (t - 4) / 3.75), -1)
    for t in (4.0, 4.5, 5.0, 5.5):
        m.add('music', t, cluster(), -4, pan=RNG.uniform(-.5, .5))
    for t in np.arange(4.25, 7.6, 0.37):
        m.add('fx', t, whoosh(0.25, 0.5), -10, pan=RNG.uniform(-.8, .8))
    m.add('fx', 6.0, impact(0.8), -3)
    m.add('music', 6.0, stab(['E3', 'F3', 'B3', 'C4']), -1)
    m.add('fx', 4.0, riser(3.75), 0)
    for t in np.arange(7.0, 7.75, 0.0625):
        m.add('drums', t, clap(0.35 + 0.65 * (t - 7.0) / 0.75), -8)
    # ---- the gap 7.75-8.0 (silence, applied in render), then the DROP
    m.add('fx', 8.0, impact(1.0), 0)
    m.add('fx', 8.0, whoosh(0.4, 1.4, up=False), -2)
    m.add('drums', 8.0, crash(), -2)
    m.add('music', 8.0, stab(['E3', 'B3', 'E4', 'G#4', 'B4', 'F#5'], 0.6, 1.8), 0)
    groove(m, 8.0, 25.0, ['E', 'C#m', 'A', 'B'])
    # ---- UI sounds
    for t in (10.5, 11.5, 12.5):
        m.add('fx', t, ui_tick('E6'), 0)
        m.add('fx', t - 0.05, whoosh(0.2, 0.4), -8)
    for t, n in ((14.6, 'E6'), (15.0, 'G#6'), (15.2, 'B6'), (15.4, 'E7')):
        m.add('fx', t, ui_tick(n, 0.6), -4)
    m.add('fx', 15.8, chime('B5'), -2)
    m.add('fx', 19.5, key_click(1.2), -2)
    m.add('fx', 19.55, chime('G#5'), -1)
    m.add('fx', 19.8, whoosh(0.35, 0.6), -6)
    for k in range(18):
        m.add('fx', 22.35 + k * (0.7 / 18), key_click(0.7), -8)
    m.add('fx', 23.15, whoosh(0.3, 0.6), -6)
    m.add('fx', 23.8, chime('E6'), -2)
    for t in (13.85, 17.85, 21.85):
        m.add('fx', t, whoosh(0.35, 1.0), -2)
    for t in (14.0, 18.0, 22.0):
        m.add('drums', t, crash(0.6), -6)
    # ---- Finale (25-30): breakdown, then the sonic logo
    m.add('fx', 25.0, whoosh(0.6, 1.2, up=False), -2)
    m.add('drums', 25.0, crash(0.8), -3)
    m.add('music', 25.0, pad(['E3', 'B3', 'E4', 'G#4'], 5.0, 0.8, 1.6, 0.25), 2)
    m.add('bass', 25.0, np.sin(2 * np.pi * hz('E1') * t_axis(3.0)) * env_ar(3.0, 0.5, 1.5) * 0.4, -2)
    m.add('fx', 26.0, impact(0.4), -8)
    for n in ('E3', 'B3', 'G#4'):
        m.add('music', 26.0, piano(n, 3.0, 0.8), -4)
    m.add('music', 26.35, piano('B4', 2.5, 0.7), -4)
    for k, n in enumerate(('B4', 'E5', 'G#5')):
        m.add('fx', 27.25 + 0.25 * k, pluck(n, 2.0), -1, pan=(k - 1) * 0.2)
        m.add('fx', 27.25 + 0.25 * k, beep(n, 0.1), -12)
    for n in ('E2', 'B2', 'E3', 'G#3', 'B3', 'E4'):
        m.add('music', 28.0, piano(n, 2.4, 0.9), -3)
    for n in ('E5', 'G#5', 'B5'):
        m.add('fx', 28.0, pluck(n, 2.0, 0.6), -7)
    m.add('fx', 28.0, impact(0.35), -10)


# ------------------------------------------------------------------ cuts (same source times as film.html)
CUTS = {
    'main': [(0, 30, 0)],
    '15': [(0, 2, 0), (2, 4, 6.0), (4, 6, 8.0), (6, 8, 11.0), (8, 10.5, 14.0), (10.5, 15, 25.5)],
    '06': [(0, 2, 0), (2, 3, 8.0), (3, 6, 27.0)],
}


def splice(x, segs):
    dur = segs[-1][1]
    out = np.zeros((int(dur * SR), 2))
    xf = int(0.008 * SR)
    for a, b, src in segs:
        ia, ib, isrc = int(a * SR), int(b * SR), int(src * SR)
        seg = x[isrc:isrc + (ib - ia)].copy()
        if a > 0:
            seg[:xf] *= np.linspace(0, 1, xf)[:, None]
        if b < dur:
            seg[-xf:] *= np.linspace(1, 0, xf)[:, None]
        out[ia:ia + len(seg)] += seg
    return out


def fade_out(x, a, b):
    ia, ib = int(a * SR), int(b * SR)
    x[ia:ib] *= (np.linspace(1, 0, ib - ia) ** 1.5)[:, None]
    x[ib:] = 0
    return x


def write_wav(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype('<i2')
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
    return measured, out_i, out_tp


def main():
    cut, dst = sys.argv[1], sys.argv[2]
    m = Mix(30.0)
    cue_main(m)
    x = m.render(gaps=[(7.75, 8.0)])
    x = splice(x, CUTS[cut])
    dur = CUTS[cut][-1][1]
    fade_out(x, dur - 0.7, dur)
    x = x / (np.abs(x).max() + 1e-9) * 0.5
    tmp = dst + '.raw.wav'
    write_wav(tmp, x)
    measured, out_i, out_tp = loudnorm(tmp, dst)
    subprocess.run(['rm', '-f', tmp])
    print(f'{cut}: {dur:.0f}s, measured {measured} LUFS -> {out_i} LUFS, TP {out_tp} dBTP -> {dst}')


if __name__ == '__main__':
    main()

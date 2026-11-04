"""
sound_generator.py

Generated sounds, so instruments don't depend on sample files:

* PartialVoice    - additive / inharmonic-partial synthesis (piano, strings,
                    brass, woodwinds, organ, mallets, synth leads and pads)
* FMVoice         - FM layers (electric piano)
* PluckVoice      - Karplus-Strong plucked string (guitars, basses)
* GeneratorEngine - SynthEngine that plays the patches above
* DrumEngine      - drum kit that loads WAV files when it finds them and
                    synthesizes any missing part (generate_drum_sample)

Everything is vectorised with numpy so it can run inside the audio callback.
"""

import math
import os

import numpy as np

from synth_engine import (
    SAMPLE_RATE,
    Sample,
    SynthEngine,
    load_wav_file,
    midi_note_to_freq,
)

TWO_PI = 2.0 * math.pi

# ---------------------------------------------------------------------------
# Patches
# ---------------------------------------------------------------------------
# a/d/s/r  : envelope (attack s, decay s, sustain level, release s)
# gain     : output level
# vib_*    : vibrato (rate Hz, depth as frequency ratio), fades in over 0.35 s
# trem_*   : tremolo (rate Hz, depth 0..1)
# unison   : detune of each unison voice in cents (chorus / ensemble)
# noise    : breath / hammer noise level, noise_decay = time constant (s)
# bt, br0  : brightness ramp - upper partials start at br0 and open over bt s
# B        : piano-style inharmonicity
# decay_pitch : higher notes decay faster (exponent)
# t60, bright, drive : plucked-string decay time, pick brightness, distortion

DEFAULTS = dict(
    a=0.005, d=0.3, s=0.7, r=0.25, gain=0.35,
    vib_rate=5.0, vib_depth=0.0, trem_rate=5.0, trem_depth=0.0,
    unison=(0.0,), noise=0.0, noise_decay=0.05,
    bt=0.0, br0=1.0, B=0.0, decay_pitch=0.0,
    t60=2.0, bright=0.5, drive=1.0,
)


def _patch(kind, **kw):
    patch = dict(DEFAULTS)
    patch["kind"] = kind
    patch.update(kw)
    return patch


def _partials(n, roll, odd=False, base=0.0, slope=0.0):
    """Harmonic series with 1/k^roll amplitudes and optional per-partial decay."""
    ks = [k for k in range(1, n + 1) if not odd or k % 2 == 1]
    return dict(
        ratios=ks,
        amps=[k ** -roll for k in ks],
        decays=[base + slope * (k - 1) for k in ks],
    )


def _with_sub(p, amp=0.7):
    """Add a sub-octave partial."""
    return dict(
        ratios=[0.5] + p["ratios"],
        amps=[amp] + p["amps"],
        decays=[0.0] + p["decays"],
    )


PATCHES = {
    # ----- Piano ---------------------------------------------------------
    "Grand Piano": _patch(
        "partials", **_partials(14, 1.1, base=1.2, slope=0.55),
        B=0.0003, a=0.003, d=1.0, s=1.0, r=0.2,
        noise=0.04, noise_decay=0.03, decay_pitch=0.35, gain=0.4),
    "Bright Piano": _patch(
        "partials", **_partials(16, 0.8, base=1.0, slope=0.5),
        B=0.0002, a=0.003, d=1.0, s=1.0, r=0.2,
        noise=0.04, noise_decay=0.03, decay_pitch=0.35, gain=0.38),
    "Honky Tonk": _patch(
        "partials", **_partials(12, 0.95, base=1.3, slope=0.6),
        unison=(-14.0, 0.0, 11.0), B=0.0004, a=0.003, d=1.0, s=1.0,
        r=0.2, decay_pitch=0.35, gain=0.38),
    "Electric Piano": _patch(
        "fm",
        layers=[
            dict(c=1.0, m=1.0, i0=2.4, i1=0.35, idec=0.5, g=1.0),
            dict(c=1.0, m=14.0, i0=1.1, i1=0.0, idec=0.05, g=0.22),
        ],
        a=0.003, d=1.6, s=0.12, r=0.25,
        trem_rate=4.8, trem_depth=0.12, gain=0.4),

    # ----- Guitar --------------------------------------------------------
    "Classic Guitar": _patch("pluck", t60=2.0, bright=0.3, a=0.001, d=0.3, s=1.0, r=0.15, gain=0.7),
    "Electric Guitar": _patch("pluck", t60=3.2, bright=0.8, drive=2.2, a=0.001, d=0.3, s=1.0, r=0.15, gain=0.55),
    "Spanish Guitar": _patch("pluck", t60=1.7, bright=0.75, a=0.001, d=0.3, s=1.0, r=0.15, gain=0.7),
    "Acoustic Guitar": _patch("pluck", t60=2.4, bright=0.6, a=0.001, d=0.3, s=1.0, r=0.15, gain=0.7),

    # ----- Bass ----------------------------------------------------------
    "Electric Bass": _patch("pluck", t60=2.6, bright=0.3, a=0.001, d=0.3, s=1.0, r=0.12, gain=0.8),
    "Acoustic Bass": _patch("pluck", t60=3.2, bright=0.2, a=0.001, d=0.3, s=1.0, r=0.15, gain=0.8),
    "Synth Bass": _patch(
        "partials", **_with_sub(_partials(14, 1.0)),
        a=0.004, d=0.25, s=0.5, r=0.1, bt=0.18, br0=0.2, gain=0.38),
    "Fretless Bass": _patch(
        "partials", ratios=[1, 2, 3, 4], amps=[1.0, 0.45, 0.2, 0.1],
        decays=[0.0, 0.5, 1.0, 2.0],
        a=0.02, d=0.4, s=0.7, r=0.2, vib_rate=4.5, vib_depth=0.002, gain=0.5),

    # ----- Strings -------------------------------------------------------
    "Violin": _patch(
        "partials", **_partials(20, 1.0),
        unison=(-5.0, 5.0), a=0.09, d=0.2, s=0.9, r=0.2,
        vib_rate=5.5, vib_depth=0.004, bt=0.15, br0=0.55,
        noise=0.01, noise_decay=50.0, gain=0.35),
    "Viola": _patch(
        "partials", **_partials(18, 1.2),
        unison=(-5.0, 4.0), a=0.11, d=0.2, s=0.9, r=0.22,
        vib_rate=5.2, vib_depth=0.0035, bt=0.15, br0=0.55, gain=0.35),
    "Cello": _patch(
        "partials", **_partials(16, 1.3),
        unison=(-4.0, 4.0), a=0.13, d=0.25, s=0.9, r=0.25,
        vib_rate=4.8, vib_depth=0.003, bt=0.2, br0=0.5, gain=0.35),
    "String Ensemble": _patch(
        "partials", **_partials(16, 1.15),
        unison=(-16.0, -6.0, 6.0, 16.0), a=0.3, d=0.3, s=0.9, r=0.45,
        vib_rate=5.0, vib_depth=0.0025, bt=0.3, br0=0.5, gain=0.3),

    # ----- Brass ---------------------------------------------------------
    "Trumpet": _patch(
        "partials", **_partials(18, 0.75),
        a=0.04, d=0.15, s=0.85, r=0.12, bt=0.07, br0=0.35,
        vib_rate=5.5, vib_depth=0.002, gain=0.3),
    "Trombone": _patch(
        "partials", **_partials(16, 0.95),
        a=0.06, d=0.15, s=0.85, r=0.15, bt=0.1, br0=0.3, gain=0.32),
    "French Horn": _patch(
        "partials", **_partials(14, 1.4),
        a=0.09, d=0.2, s=0.85, r=0.2, bt=0.12, br0=0.45, gain=0.35),
    "Brass Section": _patch(
        "partials", **_partials(16, 0.85),
        unison=(-10.0, 0.0, 10.0), a=0.07, d=0.15, s=0.85, r=0.18,
        bt=0.09, br0=0.35, gain=0.28),

    # ----- Woodwinds -----------------------------------------------------
    "Flute": _patch(
        "partials", ratios=[1, 2, 3], amps=[1.0, 0.22, 0.08],
        a=0.07, d=0.1, s=0.92, r=0.15, noise=0.06, noise_decay=99.0,
        vib_rate=5.2, vib_depth=0.003, gain=0.45),
    "Clarinet": _patch(
        "partials", **_partials(10, 0.9, odd=True),
        a=0.05, d=0.1, s=0.9, r=0.12, noise=0.015, noise_decay=99.0, gain=0.4),
    "Oboe": _patch(
        "partials", ratios=list(range(1, 11)),
        amps=[1.0, 0.9, 1.4, 1.2, 0.8, 0.5, 0.35, 0.25, 0.15, 0.1],
        a=0.05, d=0.1, s=0.9, r=0.12, vib_rate=5.4, vib_depth=0.003,
        noise=0.015, noise_decay=99.0, gain=0.33),
    "Saxophone": _patch(
        "partials", **_partials(16, 0.85),
        a=0.05, d=0.12, s=0.88, r=0.12, bt=0.08, br0=0.5,
        vib_rate=5.3, vib_depth=0.0035, noise=0.02, noise_decay=99.0, gain=0.33),

    # ----- Synth ---------------------------------------------------------
    "Lead": _patch(
        "partials", **_partials(14, 1.0, odd=True),
        unison=(-7.0, 7.0), a=0.01, d=0.1, s=0.85, r=0.1,
        vib_rate=5.5, vib_depth=0.002, gain=0.3),
    "Pad": _patch(
        "partials", **_partials(10, 1.3),
        unison=(-14.0, 0.0, 14.0), a=0.5, d=0.5, s=0.85, r=0.9,
        bt=0.7, br0=0.25, gain=0.3),
    "Pluck": _patch(
        "partials", **_partials(14, 1.0, base=2.0, slope=1.6),
        a=0.002, d=0.4, s=0.0, r=0.06, bt=0.12, br0=0.3, gain=0.4),
    "Synth Brass": _patch(
        "partials", **_partials(14, 0.7),
        unison=(-8.0, 8.0), a=0.03, d=0.1, s=0.88, r=0.15,
        bt=0.08, br0=0.25, gain=0.28),

    # ----- Organ ---------------------------------------------------------
    "Pipe Organ": _patch(
        "partials", ratios=[0.5, 1, 2, 3, 4, 6, 8],
        amps=[0.4, 1.0, 0.7, 0.35, 0.25, 0.15, 0.1],
        a=0.03, d=0.05, s=1.0, r=0.12, trem_rate=6.0, trem_depth=0.05, gain=0.35),
    "Rock Organ": _patch(
        "partials", ratios=[1, 2, 3, 4, 6, 3],
        amps=[1.0, 0.9, 0.45, 0.4, 0.3, 0.9],
        decays=[0.0, 0.0, 0.0, 0.0, 0.0, 12.0],
        a=0.003, d=0.05, s=1.0, r=0.05, trem_rate=6.8, trem_depth=0.14, gain=0.35),
    "Church Organ": _patch(
        "partials", ratios=[0.5, 1, 2, 3, 4, 5, 6, 8],
        amps=[0.6, 1.0, 0.8, 0.5, 0.4, 0.3, 0.25, 0.15],
        unison=(-5.0, 0.0, 5.0), a=0.12, d=0.1, s=1.0, r=0.35, gain=0.3),

    # ----- Mallets -------------------------------------------------------
    "Marimba": _patch(
        "partials", ratios=[1, 4, 10], amps=[1.0, 0.35, 0.1],
        decays=[4.5, 12.0, 25.0], a=0.001, d=0.1, s=1.0, r=0.08,
        decay_pitch=0.3, gain=0.5),
    "Vibraphone": _patch(
        "partials", ratios=[1, 4, 10], amps=[1.0, 0.3, 0.12],
        decays=[1.1, 3.0, 6.0], a=0.002, d=0.1, s=1.0, r=0.35,
        trem_rate=5.5, trem_depth=0.28, decay_pitch=0.3, gain=0.45),
    "Xylophone": _patch(
        "partials", ratios=[1, 3, 6], amps=[1.0, 0.6, 0.3],
        decays=[8.0, 16.0, 26.0], a=0.001, d=0.1, s=1.0, r=0.05,
        decay_pitch=0.3, gain=0.5),
    "Glockenspiel": _patch(
        "partials", ratios=[1, 2.76, 5.4, 8.93], amps=[1.0, 0.5, 0.25, 0.15],
        decays=[2.2, 4.0, 7.0, 10.0], a=0.001, d=0.1, s=1.0, r=0.25,
        decay_pitch=0.3, gain=0.45),
}

# Sounds that prefer real recordings when the sample files exist.
SAMPLE_BACKED = {"Grand Piano": "piano"}


# ---------------------------------------------------------------------------
# Voices
# ---------------------------------------------------------------------------

class _GenVoice:
    """Shared envelope / bookkeeping. Duck-types synth_engine.Voice."""

    def __init__(self, note, velocity, patch):
        self.note = note
        self.p = patch
        self.freq = midi_note_to_freq(note)
        self.vel = max(0.05, velocity / 127.0)
        self.n_done = 0
        self.released = False
        self.rel_t = 0.0
        self.rel_level = 0.0

    def _times(self, n):
        return (self.n_done + np.arange(n, dtype=np.float64)) / SAMPLE_RATE

    def _envelope(self, t):
        p = self.p
        a = max(p["a"], 1e-4)
        d = max(p["d"], 1e-3)
        s = p["s"]
        attack = np.minimum(t / a, 1.0)
        decay = s + (1.0 - s) * np.exp(-np.maximum(t - a, 0.0) * 3.0 / d)
        env = attack * decay

        if self.released:
            since = t - self.rel_t
            fade = np.clip(1.0 - since / max(p["r"], 1e-3), 0.0, 1.0) ** 2
            env = np.where(since >= 0.0, self.rel_level * fade, env)

        return env

    def _vibrato(self, t):
        depth = self.p["vib_depth"]
        if depth <= 0.0:
            return None
        fade_in = np.minimum(t / 0.35, 1.0)
        return 1.0 + depth * fade_in * np.sin(TWO_PI * self.p["vib_rate"] * t)

    def _tremolo(self, t):
        depth = self.p["trem_depth"]
        if depth <= 0.0:
            return 1.0
        return 1.0 - depth * (0.5 + 0.5 * np.sin(TWO_PI * self.p["trem_rate"] * t))

    def _phase_increment(self, t):
        inc = self.freq / SAMPLE_RATE
        vib = self._vibrato(t)
        if vib is None:
            return np.full(len(t), inc, dtype=np.float64)
        return inc * vib

    def note_off(self):
        if self.released:
            return
        now = self.n_done / SAMPLE_RATE
        self.rel_level = float(self._envelope(np.array([now]))[0])
        self.rel_t = now
        self.released = True

    def is_active(self):
        now = self.n_done / SAMPLE_RATE
        if self.released:
            return (now - self.rel_t) < self.p["r"]
        if self.p["s"] <= 0.0:
            return now < self.p["a"] + self.p["d"] * 2.5
        return True


class PartialVoice(_GenVoice):
    """Sum of sine partials with per-partial decay, optional unison."""

    def __init__(self, note, velocity, patch):
        super().__init__(note, velocity, patch)
        p = patch

        ratios = np.asarray(p["ratios"], dtype=np.float64)
        if p["B"]:
            ratios = ratios * np.sqrt(1.0 + p["B"] * ratios ** 2)

        amps = np.asarray(p["amps"], dtype=np.float64)
        # Drop partials above the Nyquist limit to avoid aliasing.
        amps = np.where(self.freq * ratios < 0.45 * SAMPLE_RATE, amps, 0.0)
        power = math.sqrt(float(np.sum(amps ** 2)))
        if power > 0.0:
            amps = amps / power

        decays = p.get("decays")
        if decays is None:
            decays = np.zeros(len(ratios))
        decays = np.asarray(decays, dtype=np.float64)

        self.ratios = ratios
        self.amps = amps
        self.decays = decays * (self.freq / 261.63) ** p["decay_pitch"]
        self.idx = np.arange(len(ratios), dtype=np.float64)
        self.u = np.array([2.0 ** (c / 1200.0) for c in p["unison"]], dtype=np.float64)

        if len(self.u) > 1:
            self.ph = np.random.random(len(self.u))
        else:
            self.ph = np.zeros(1)

    def render(self, n):
        p = self.p
        t = self._times(n)
        env = self._envelope(t)

        inc = self._phase_increment(t)
        pb = self.ph[None, :] + np.cumsum(inc[:, None] * self.u[None, :], axis=0)
        self.ph = pb[-1]

        amp = self.amps[None, :] * np.exp(-t[:, None] * self.decays[None, :])
        if p["bt"] > 0.0:
            bright = p["br0"] + (1.0 - p["br0"]) * np.minimum(t / p["bt"], 1.0)
            amp = amp * bright[:, None] ** self.idx[None, :]

        wave = np.sin(TWO_PI * pb[:, :, None] * self.ratios[None, None, :])
        out = np.einsum("nuk,nk->n", wave, amp) / math.sqrt(len(self.u))

        if p["noise"] > 0.0:
            raw = np.random.standard_normal(n + 2)
            soft = 0.25 * raw[:-2] + 0.5 * raw[1:-1] + 0.25 * raw[2:]
            out = out + p["noise"] * soft * np.exp(-t / p["noise_decay"])

        out = out * self._tremolo(t) * env * (self.vel * p["gain"])
        self.n_done += n
        return out.astype(np.float32)


class FMVoice(_GenVoice):
    """One or more FM carrier/modulator layers with decaying mod index."""

    def __init__(self, note, velocity, patch):
        super().__init__(note, velocity, patch)
        self.ph = 0.0
        self.layers = patch["layers"]

    def render(self, n):
        p = self.p
        t = self._times(n)
        env = self._envelope(t)

        pb = self.ph + np.cumsum(self._phase_increment(t))
        self.ph = float(pb[-1])

        brightness = 0.5 + 0.7 * self.vel
        out = np.zeros(n, dtype=np.float64)

        for layer in self.layers:
            index = layer["i1"] + (layer["i0"] - layer["i1"]) * np.exp(-t / layer["idec"])
            mod = np.sin(TWO_PI * layer["m"] * pb)
            out += layer["g"] * np.sin(TWO_PI * layer["c"] * pb + index * brightness * mod)

        out = out * self._tremolo(t) * env * (self.vel * p["gain"])
        self.n_done += n
        return out.astype(np.float32)


class PluckVoice(_GenVoice):
    """Karplus-Strong plucked string."""

    def __init__(self, note, velocity, patch):
        super().__init__(note, velocity, patch)
        p = patch

        # The two-point average adds half a sample of delay.
        self.length = max(2, int(round(SAMPLE_RATE / self.freq - 0.5)))
        self.g = min(0.9999, 10.0 ** (-3.0 / (p["t60"] * self.freq)))

        burst = np.random.uniform(-1.0, 1.0, self.length + 1)
        width = 1 + int(round((1.0 - p["bright"]) * 8))
        width = min(width, self.length + 1)
        if width > 1:
            burst = np.convolve(burst, np.ones(width) / width, mode="same")
        burst = burst - burst.mean()
        peak = float(np.max(np.abs(burst)))
        self.hist = burst / peak if peak > 0.0 else burst

    def render(self, n):
        p = self.p
        t = self._times(n)
        env = self._envelope(t)

        out = np.empty(n, dtype=np.float64)
        pos = 0
        while pos < n:
            m = min(n - pos, self.length)
            new = self.g * 0.5 * (self.hist[:m] + self.hist[1:m + 1])
            out[pos:pos + m] = new
            self.hist = np.concatenate((self.hist[m:], new))
            pos += m

        if p["drive"] > 1.0:
            out = np.tanh(out * p["drive"])

        out = out * env * (self.vel * p["gain"])
        self.n_done += n
        return out.astype(np.float32)


_VOICE_KINDS = {
    "partials": PartialVoice,
    "fm": FMVoice,
    "pluck": PluckVoice,
}


def make_voice(note, velocity, patch):
    return _VOICE_KINDS[patch["kind"]](note, velocity, patch)


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------

class GeneratorEngine(SynthEngine):
    """
    SynthEngine that plays generated instrument patches.

    Instrument tracks never use drums, so the per-engine drum sample loading
    done by SynthEngine.__init__ is skipped (faster track creation).
    """

    def __init__(self, *args, **kwargs):
        self.patch = None
        self.sound_name = None
        super().__init__(*args, **kwargs)

    def load_drum_samples(self, drum_folder):
        pass

    def set_sound(self, sound):
        self.sound_name = sound

        backed = SAMPLE_BACKED.get(sound)
        if backed is not None:
            self.set_instrument(backed)
            if self._samples.get(backed):
                # Real recordings found - use them.
                self.patch = None
                return
        else:
            self.set_instrument(None)

        self.patch = PATCHES.get(sound) or PATCHES["Lead"]

    def note_on(self, note, velocity=100):
        if self.patch is None:
            super().note_on(note, velocity)
            return

        with self._lock:
            if len(self._voices) >= self.max_voices and note not in self._voices:
                del self._voices[next(iter(self._voices))]

            self._voices[note] = make_voice(note, velocity, self.patch)


# ---------------------------------------------------------------------------
# Drums
# ---------------------------------------------------------------------------

DRUM_FILE_STEMS = {
    "Kick": ("kick_1", "kick"),
    "Snare": ("snare_1", "snare"),
    "Closed Hat": ("hat_1", "closed_hat", "closed_hat_1"),
    "Open Hat": ("open_hat", "open_hat_1"),
    "Crash": ("crash_1", "crash"),
    "Low Tom": ("lo_tom_1", "low_tom_1", "low_tom"),
    "High Tom": ("hi_tom_1", "high_tom_1", "high_tom"),
}


def generate_drum_sample(part):
    """Synthesize a one-shot drum hit (treated as C4 by DrumVoice)."""
    sr = SAMPLE_RATE
    rng = np.random.default_rng(sum(ord(c) for c in part))

    def times(seconds):
        return np.arange(int(sr * seconds)) / sr

    def highpass(x):
        return np.diff(x, prepend=x[0])

    def metallic(t):
        freqs = (205.3, 304.4, 369.6, 522.7, 540.0, 800.0)
        return sum(np.sign(np.sin(TWO_PI * f * t)) for f in freqs) / len(freqs)

    def sweep(t, f_end, f_start_extra, rate):
        freq = f_end + f_start_extra * np.exp(-t * rate)
        return np.sin(TWO_PI * np.cumsum(freq) / sr)

    if part == "Kick":
        t = times(0.55)
        y = sweep(t, 45.0, 110.0, 28.0) * np.exp(-t * 7.5)
        y = y + 0.25 * rng.standard_normal(t.size) * np.exp(-t * 220.0)
    elif part == "Snare":
        t = times(0.35)
        body = np.sin(TWO_PI * 185.0 * t) * np.exp(-t * 28.0) * 0.6
        noise = highpass(rng.standard_normal(t.size)) * np.exp(-t * 16.0) * 0.8
        y = body + noise
    elif part == "Closed Hat":
        t = times(0.14)
        raw = metallic(t) * 0.6 + rng.standard_normal(t.size) * 0.7
        y = highpass(highpass(raw)) * np.exp(-t * 70.0)
    elif part == "Open Hat":
        t = times(0.7)
        raw = metallic(t) * 0.6 + rng.standard_normal(t.size) * 0.7
        y = highpass(highpass(raw)) * np.exp(-t * 10.0)
    elif part == "Crash":
        t = times(1.8)
        raw = metallic(t) * 0.5 + rng.standard_normal(t.size) * 0.8
        y = highpass(highpass(raw)) * np.exp(-t * 2.6)
    elif part == "Low Tom":
        t = times(0.55)
        y = sweep(t, 70.0, 55.0, 16.0) * np.exp(-t * 7.0)
    elif part == "High Tom":
        t = times(0.45)
        y = sweep(t, 135.0, 75.0, 18.0) * np.exp(-t * 9.0)
    else:
        y = np.zeros(1000)

    peak = float(np.max(np.abs(y)))
    if peak > 0.0:
        y = y / peak * 0.9

    return Sample(y.astype(np.float32), sr)


class DrumEngine(SynthEngine):
    """
    Drum kit engine.

    Finds WAVs case-insensitively (Samples/Drums, Lo_Tom_1.wav, ...) and
    synthesizes any part whose file is missing, so every drum part always
    makes sound. sample_sources[part] is the file name or "generated".
    """

    def __init__(self, *args, **kwargs):
        self.sample_sources = {}
        super().__init__(*args, **kwargs)

    def _find_drum_folder(self):
        root = self.sample_root
        if not os.path.isdir(root):
            return None
        for entry in os.listdir(root):
            full = os.path.join(root, entry)
            if entry.lower() == "drums" and os.path.isdir(full):
                return full
        return None

    def load_drum_samples(self, drum_folder):
        folder = self._find_drum_folder()
        files = {}
        if folder is not None:
            files = {name.lower(): name for name in os.listdir(folder)}

        for part, stems in DRUM_FILE_STEMS.items():
            sample = None
            source = "generated"

            for stem in stems:
                filename = files.get(stem + ".wav")
                if filename is None:
                    continue
                try:
                    sample = load_wav_file(os.path.join(folder, filename))
                    source = filename
                    break
                except Exception as exc:
                    print(f"Could not load drum sample {filename}: {exc}")

            if sample is None:
                sample = generate_drum_sample(part)

            self._drum_samples[part] = sample
            self.sample_sources[part] = source

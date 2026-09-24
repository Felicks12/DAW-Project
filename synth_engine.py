"""
synth_engine.py

Core polyphonic synthesizer engine:
- Oscillators
- ADSR envelopes
- Sample-based instruments
- Voice management
- Real-time audio rendering
"""

import math

import os
import numpy as np
import threading
import soundfile as sf

SAMPLE_RATE = 44100


# ==============================================================
# MIDI / frequency
# ==============================================================

def midi_note_to_freq(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


# ==============================================================
# Oscillators
# ==============================================================

def osc_sine(phase):
    return np.sin(2 * np.pi * phase)


def osc_square(phase):
    return np.sign(np.sin(2 * np.pi * phase))


def osc_saw(phase):
    return 2.0 * (phase - np.floor(phase + 0.5))


def osc_triangle(phase):
    return 2.0 * np.abs(
        2.0 * (phase - np.floor(phase + 0.5))
    ) - 1.0


WAVEFORMS = {
    "sine": osc_sine,
    "square": osc_square,
    "saw": osc_saw,
    "triangle": osc_triangle,
}


# ==============================================================
# Instrument definitions
# ==============================================================

# These are the folders the engine will look for.
#
# Example:
#
# Samples/
#   piano/
#       60.wav
#       64.wav
#       67.wav
#
# The filenames are MIDI note numbers.

SAMPLE_INSTRUMENTS = {
    "piano": "Piano",
    "electric piano": "electric_piano",
    "organ": "organ",
    "strings": "strings",
    "bass": "bass",
}

class PianoSample:
    def __init__(self, path):
        self.samples, self.sample_rate = sf.read(path, dtype="float32")

        # Convert stereo samples to mono.
        if self.samples.ndim > 1:
            self.samples = np.mean(self.samples, axis=1)

        # Make sure the sample is a NumPy float32 array.
        self.samples = np.asarray(self.samples, dtype=np.float32)

        if len(self.samples) == 0:
            raise ValueError(f"Piano sample is empty: {path}")

    def get_samples(self, n):
        """Return up to n samples from the piano recording."""
        return self.samples[:n]

# ==============================================================
# ADSR
# ==============================================================

class ADSR:
    def __init__(
        self,
        attack=0.01,
        decay=0.1,
        sustain=0.7,
        release=0.3
    ):
        self.attack = attack
        self.decay = decay
        self.sustain = sustain
        self.release = release

        self._stage = "idle"
        self._level = 0.0
        self._release_start_level = 0.0
        self._time_in_stage = 0.0

    def note_on(self):
        self._stage = "attack"
        self._time_in_stage = 0.0

    def note_off(self):
        if self._stage != "idle":
            self._stage = "release"
            self._time_in_stage = 0.0
            self._release_start_level = self._level

    def is_active(self):
        return self._stage != "idle"

    def next_samples(self, n):
        out = np.zeros(n, dtype=np.float32)
        dt = 1.0 / SAMPLE_RATE

        for i in range(n):
            if self._stage == "attack":
                if self.attack <= 0:
                    self._level = 1.0
                    self._stage = "decay"
                    self._time_in_stage = 0.0
                else:
                    self._level = min(
                        1.0,
                        self._time_in_stage / self.attack
                    )

                    if self._level >= 1.0:
                        self._stage = "decay"
                        self._time_in_stage = 0.0

            elif self._stage == "decay":
                if self.decay <= 0:
                    self._level = self.sustain
                    self._stage = "sustain"
                else:
                    frac = min(
                        1.0,
                        self._time_in_stage / self.decay
                    )

                    self._level = (
                        1.0
                        + (self.sustain - 1.0) * frac
                    )

                    if frac >= 1.0:
                        self._stage = "sustain"
                        self._time_in_stage = 0.0

            elif self._stage == "sustain":
                self._level = self.sustain

            elif self._stage == "release":
                if self.release <= 0:
                    self._level = 0.0
                    self._stage = "idle"
                else:
                    frac = min(
                        1.0,
                        self._time_in_stage / self.release
                    )

                    self._level = (
                        self._release_start_level
                        * (1.0 - frac)
                    )

                    if frac >= 1.0:
                        self._level = 0.0
                        self._stage = "idle"

            out[i] = self._level
            self._time_in_stage += dt

        return out


# ==============================================================
# Sample loading
# ==============================================================

class Sample:
    def __init__(self, data, sample_rate=SAMPLE_RATE):
        self.data = np.asarray(data, dtype=np.float32)
        self.sample_rate = sample_rate

        if self.data.ndim > 1:
            self.data = np.mean(self.data, axis=1)

        peak = np.max(np.abs(self.data))

        if peak > 1.0:
            self.data /= peak

    def get_samples(self, start, count, pitch_ratio):
        """
        Return count Samples while playing this sample at pitch_ratio.
        """

        if len(self.data) == 0:
            return np.zeros(count, dtype=np.float32)

        positions = (
            start
            + np.arange(count, dtype=np.float32)
            * pitch_ratio
        )

        valid = positions < len(self.data)

        out = np.zeros(count, dtype=np.float32)

        if not np.any(valid):
            return out

        valid_positions = positions[valid]

        left = np.floor(valid_positions).astype(np.int64)
        right = np.minimum(left + 1, len(self.data) - 1)

        frac = valid_positions - left

        out[valid] = (
            self.data[left] * (1.0 - frac)
            + self.data[right] * frac
        )

        return out

def load_wav_file(path):
    """
    Load a WAV file using soundfile.

    Returns:
        Sample
    """

    data, sample_rate = sf.read(
        path,
        dtype="float32"
    )

    # Convert stereo to mono
    if data.ndim > 1:
        data = np.mean(data, axis=1)

    data = np.asarray(data, dtype=np.float32)

    if len(data) == 0:
        raise ValueError(
            f"Audio file is empty: {path}"
        )

    # Resample to 44100 Hz if necessary
    if sample_rate != SAMPLE_RATE:
        old_positions = np.arange(len(data))

        new_length = int(
            len(data)
            * SAMPLE_RATE
            / sample_rate
        )

        new_positions = np.linspace(
            0,
            len(data) - 1,
            new_length
        )

        data = np.interp(
            new_positions,
            old_positions,
            data
        ).astype(np.float32)

        sample_rate = SAMPLE_RATE

    return Sample(data, sample_rate)

# ==============================================================
# Voice
# ==============================================================

class Voice:
    def __init__(
        self,
        note,
        velocity,
        waveform_fn,
        adsr_params,
        sample=None,
        sample_note=None
    ):
        self.note = note
        self.velocity = velocity / 127.0
        self.freq = midi_note_to_freq(note)

        self.phase = 0.0

        self.waveform_fn = waveform_fn

        self.envelope = ADSR(**adsr_params)
        self.envelope.note_on()

        # Sample playback
        self.sample = sample
        self.sample_note = sample_note
        self.sample_position = 0.0

        if sample is not None and sample_note is not None:
            self.sample_ratio = (
                midi_note_to_freq(note)
                / midi_note_to_freq(sample_note)
            )
        else:
            self.sample_ratio = 1.0

    def note_off(self):
        self.envelope.note_off()

    def is_active(self):
        return self.envelope.is_active()

    def render(self, n):
        env = self.envelope.next_samples(n)

        # ----------------------------------------------------------
        # Sample-based voice
        # ----------------------------------------------------------
        if self.sample is not None:
            wave = self.sample.get_samples(
                self.sample_position,
                n,
                self.sample_ratio
            )

            self.sample_position += (
                n * self.sample_ratio
            )

            return (
                wave
                * env
                * self.velocity
            )

        # ----------------------------------------------------------
        # Synthesized voice
        # ----------------------------------------------------------
        phase_inc = self.freq / SAMPLE_RATE

        phases = (
            self.phase
            + phase_inc * np.arange(n)
        )

        self.phase = (
            self.phase
            + phase_inc * n
        ) % 1.0

        wave = self.waveform_fn(phases % 1.0)

        return (
            wave
            * env
            * self.velocity
        )

class DrumVoice:
    """
    One-shot pitched drum sample.

    The source sample is treated as C4 (MIDI 60).
    Other piano-roll pitches transpose the sample accordingly.
    """

    def __init__(self, sample, pitch=60, velocity=100):
        self.sample = sample
        self.position = 0.0
        self.active = True

        self.velocity = velocity / 127.0

        # C4 (MIDI 60) is the original sample pitch.
        # C5 = 2x playback speed.
        # C3 = 0.5x playback speed.
        self.pitch_ratio = (
            2.0 ** ((pitch - 60) / 12.0)
        )

    def is_active(self):
        return self.active

    def render(self, n):
        if not self.active:
            return np.zeros(n, dtype=np.float32)

        data = self.sample.data

        if len(data) == 0:
            self.active = False
            return np.zeros(n, dtype=np.float32)

        positions = (
            self.position
            + np.arange(n, dtype=np.float32)
            * self.pitch_ratio
        )

        valid = positions < len(data)

        out = np.zeros(
            n,
            dtype=np.float32
        )

        if np.any(valid):
            source_positions = positions[valid]

            left = np.floor(
                source_positions
            ).astype(np.int64)

            right = np.minimum(
                left + 1,
                len(data) - 1
            )

            fraction = (
                source_positions - left
            )

            out[valid] = (
                data[left] * (1.0 - fraction)
                + data[right] * fraction
            )

            out[valid] *= self.velocity

        self.position += (
            n * self.pitch_ratio
        )

        if self.position >= len(data):
            self.active = False

        return out

# ==============================================================
# SynthEngine
# ==============================================================

class SynthEngine:
    def __init__(
        self,
        waveform="saw",
        adsr_params=None,
        max_voices=16,
        master_volume=0.3,
        sample_root=None
    ):
        self.waveform_name = waveform

        self.adsr_params = adsr_params or dict(
            attack=0.01,
            decay=0.15,
            sustain=0.6,
            release=0.3
        )

        self.max_voices = max_voices
        self.master_volume = master_volume

        self._voices = {}
        self._lock = threading.Lock()

        # ----------------------------------------------------------
        # Sample instruments
        # ----------------------------------------------------------

        if sample_root is None:
            sample_root = os.path.join(
                os.path.dirname(
                    os.path.abspath(__file__)
                ),
                "Samples"
            )

        self.sample_root = sample_root

        self._drum_samples = {}
        self._drum_voices = []

        drum_folder = os.path.join(
            self.sample_root,
            "drums"
        )

        self.load_drum_samples(drum_folder)

        self.instrument_name = None

        # {
        #     "piano": {
        #         60: Sample(...),
        #         72: Sample(...)
        #     }
        # }
        self._samples = {}

    # ==========================================================
    # Synth settings
    # ==========================================================

    def set_waveform(self, name):
        if name not in WAVEFORMS:
            raise ValueError(
                f"Unknown waveform: {name}. "
                f"Options: {list(WAVEFORMS)}"
            )

        self.waveform_name = name

    def set_adsr(self, **kwargs):
        self.adsr_params.update(kwargs)

    # ==========================================================
    # Instrument loading
    # ==========================================================

    def set_instrument(self, name):
        """
        Select an instrument.

        If the instrument has Samples available, notes will use
        those Samples.

        Otherwise the engine falls back to the oscillator.
        """

        if name is None:
            self.instrument_name = None
            return

        name = name.lower()

        self.instrument_name = name

        if name in SAMPLE_INSTRUMENTS:
            self.load_instrument(name)

    def load_instrument(self, name):
        folder_name = SAMPLE_INSTRUMENTS.get(name)

        if folder_name is None:
            return

        if name in self._samples:
            return

        folder = os.path.join(
            self.sample_root,
            folder_name
        )

        samples = {}

        if not os.path.isdir(folder):
            print(f"Sample folder not found: {folder}")
            self._samples[name] = samples
            return

        # Note names -> MIDI pitch classes
        piano_notes = {
            "C": 0,
            "C#": 1,
            "D": 2,
            "D#": 3,
            "E": 4,
            "F": 5,
            "F#": 6,
            "G": 7,
            "G#": 8,
            "A": 9,
            "A#": 10,
            "B": 11,
        }

        for filename in os.listdir(folder):

            if not filename.lower().endswith(".wav"):
                continue

            name_without_ext = os.path.splitext(filename)[0]

            midi_note = None

            # ------------------------------------------------------
            # Format 1:
            #
            #   60.wav
            #   64.wav
            #   67.wav
            # ------------------------------------------------------

            try:
                midi_note = int(name_without_ext)

            except ValueError:

                # --------------------------------------------------
                # Format 2:
                #
                #   mf_C4.wav
                #   mf_C#4.wav
                #   mf_D4.wav
                #
                # We currently only use the MF velocity layer.
                # --------------------------------------------------

                if not name_without_ext.lower().startswith("mf_"):
                    continue

                note_name = name_without_ext[3:]

                if len(note_name) < 2:
                    continue

                # Sharp note:
                # C#4, D#4, F#4, etc.
                if len(note_name) >= 3 and note_name[1] == "#":
                    pitch_name = note_name[:2]
                    octave_text = note_name[2:]

                # Natural note:
                # C4, D4, E4, etc.
                else:
                    pitch_name = note_name[:1]
                    octave_text = note_name[1:]

                pitch_name = pitch_name.upper()

                if pitch_name not in piano_notes:
                    continue

                try:
                    octave = int(octave_text)
                except ValueError:
                    continue

                # MIDI note calculation.
                #
                # C-1 = MIDI 0
                # C4  = MIDI 60
                # A4  = MIDI 69
                midi_note = (
                        (octave + 1) * 12
                        + piano_notes[pitch_name]
                )

            # ------------------------------------------------------
            # Validate MIDI note
            # ------------------------------------------------------

            if midi_note is None:
                continue

            if not 0 <= midi_note <= 127:
                continue

            # ------------------------------------------------------
            # Load sample
            # ------------------------------------------------------

            path = os.path.join(
                folder,
                filename
            )

            try:
                samples[midi_note] = load_wav_file(path)

                print(
                    f"Loaded {filename} as MIDI note {midi_note}"
                )

            except Exception as exc:
                print(
                    f"Could not load sample {path}: {exc}"
                )

        self._samples[name] = samples

        print(
            f"Loaded {len(samples)} samples for {name}"
        )

    def load_drum_samples(self, drum_folder):
        """
        Load drum WAV files from a folder.

        The files are converted to mono and resampled to
        SAMPLE_RATE when necessary.
        """

        drum_files = {
            "Kick": "kick_1.wav",
            "Snare": "snare_1.wav",
            "Closed Hat": "Hat_1.wav",
            "Open Hat": "open_hat.wav",
            "Crash": "crash_1.wav",
            "Low Tom": "low_tom_1.wav",
            "High Tom": "hi_tom_1.wav",
        }

        for name, filename in drum_files.items():

            path = os.path.join(
                drum_folder,
                filename
            )

            if not os.path.isfile(path):
                print(
                    f"Drum sample not found: {path}"
                )
                continue

            try:
                sample = load_wav_file(path)

                self._drum_samples[name] = sample

                print(
                    f"Loaded drum: {name}"
                )

            except Exception as exc:
                print(
                    f"Could not load drum sample "
                    f"{path}: {exc}"
                )

    def play_drum(self, name, pitch=60, velocity=100):
        sample = self._drum_samples.get(name)

        if sample is None:
            return

        with self._lock:
            self._drum_voices.append(
                DrumVoice(
                    sample,
                    pitch=pitch,
                    velocity=velocity
                )
            )

    def _get_sample(self, note):
        """
        Find the closest available piano sample.

        The piano samples are spaced across the keyboard, so the
        requested note should normally be no more than a few
        semitones away from the selected sample.
        """

        if self.instrument_name not in self._samples:
            return None, None

        samples = self._samples[self.instrument_name]

        if not samples:
            return None, None

        # ----------------------------------------------------------
        # Find the closest sample by MIDI distance.
        # ----------------------------------------------------------

        closest_note = min(
            samples.keys(),
            key=lambda sample_note: abs(sample_note - note)
        )

        return (
            samples[closest_note],
            closest_note
        )

    # ==========================================================
    # Notes
    # ==========================================================

    def note_on(self, note, velocity=100):
        with self._lock:

            if (
                len(self._voices) >= self.max_voices
                and note not in self._voices
            ):
                oldest = next(iter(self._voices))
                del self._voices[oldest]

            sample = None
            sample_note = None

            if self.instrument_name is not None:
                sample, sample_note = self._get_sample(note)

            self._voices[note] = Voice(
                note,
                velocity,
                WAVEFORMS[self.waveform_name],
                dict(self.adsr_params),
                sample=sample,
                sample_note=sample_note
            )

    def note_off(self, note):
        with self._lock:
            if note in self._voices:
                self._voices[note].note_off()

    def all_notes_off(self):
        with self._lock:
            for voice in self._voices.values():
                voice.note_off()

    # ==========================================================
    # Audio rendering
    # ==========================================================

    def render(self, n):
        mix = np.zeros(
            n,
            dtype=np.float32
        )

        with self._lock:

            # ------------------------------------------------------
            # Piano / synth voices
            # ------------------------------------------------------

            dead = []

            for note, voice in self._voices.items():
                mix += voice.render(n)

                if not voice.is_active():
                    dead.append(note)

            for note in dead:
                del self._voices[note]

            # ------------------------------------------------------
            # Drum voices
            # ------------------------------------------------------

            dead_drums = []

            for drum_voice in self._drum_voices:
                mix += drum_voice.render(n)

                if not drum_voice.is_active():
                    dead_drums.append(drum_voice)

            for drum_voice in dead_drums:
                self._drum_voices.remove(drum_voice)

        # ----------------------------------------------------------
        # Master volume
        # ----------------------------------------------------------

        mix *= self.master_volume

        mix = np.tanh(mix)

        return mix

# ==============================================================
# Three-band EQ
# ==============================================================

class ThreeBandEQ:
    """
    Simple per-track 3-band EQ.
    """

    def __init__(
        self,
        sample_rate=SAMPLE_RATE,
        bass_cutoff=250.0,
        treble_cutoff=4000.0
    ):
        self.sample_rate = sample_rate

        self.bass_gain = 1.0
        self.mid_gain = 1.0
        self.treble_gain = 1.0

        self._lp_alpha = self._one_pole_alpha(
            bass_cutoff
        )

        self._hp_alpha = self._one_pole_alpha(
            treble_cutoff
        )

        self._lp_state = 0.0
        self._hp_prev_in = 0.0
        self._hp_prev_out = 0.0

        self.last_bass_level = 0.0
        self.last_mid_level = 0.0
        self.last_treble_level = 0.0

        self.clipping = False

    def _one_pole_alpha(self, cutoff_hz):
        dt = 1.0 / self.sample_rate
        rc = 1.0 / (2 * math.pi * cutoff_hz)

        return dt / (rc + dt)

    def process(self, samples):
        n = len(samples)

        if n == 0:
            return samples

        low = np.empty(
            n,
            dtype=np.float32
        )

        state = self._lp_state
        alpha = self._lp_alpha

        for i in range(n):
            state += alpha * (
                samples[i] - state
            )

            low[i] = state

        self._lp_state = state

        high = np.empty(
            n,
            dtype=np.float32
        )

        prev_in = self._hp_prev_in
        prev_out = self._hp_prev_out
        alpha_hp = self._hp_alpha

        for i in range(n):
            out = alpha_hp * (
                prev_out
                + samples[i]
                - prev_in
            )

            high[i] = out

            prev_out = out
            prev_in = samples[i]

        self._hp_prev_in = prev_in
        self._hp_prev_out = prev_out

        mid = samples - low - high

        out = (
            low * self.bass_gain
            + mid * self.mid_gain
            + high * self.treble_gain
        )

        self.last_bass_level = float(
            np.sqrt(np.mean(low ** 2))
        )

        self.last_mid_level = float(
            np.sqrt(np.mean(mid ** 2))
        )

        self.last_treble_level = float(
            np.sqrt(np.mean(high ** 2))
        )

        self.clipping = bool(
            np.max(np.abs(out)) > 0.98
        )

        return out.astype(np.float32)


if __name__ == "__main__":
    engine = SynthEngine()

    engine.set_instrument("piano")

    samples = engine._samples["piano"]

    print()
    print("Sample mapping:")
    print()

    worst_note = None
    worst_sample = None
    worst_distance = -1

    for note in range(21, 109):
        sample, sample_note = engine._get_sample(note)

        if sample is None:
            continue

        distance = abs(note - sample_note)

        print(
            f"MIDI {note:3d} -> "
            f"MIDI {sample_note:3d} "
            f"({distance:+d} semitones)"
        )

        if distance > worst_distance:
            worst_distance = distance
            worst_note = note
            worst_sample = sample_note

    print()
    print("Worst case:")
    print(
        f"MIDI {worst_note} uses MIDI {worst_sample} "
        f"({worst_distance} semitones away)"
    )
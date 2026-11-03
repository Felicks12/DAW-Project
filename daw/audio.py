"""Real-time audio output stream."""

import sys

import numpy as np
import sounddevice as sd

from synth_engine import SAMPLE_RATE


def start_audio(app):
    def callback(outdata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)

        mix = np.zeros(
            frames,
            dtype=np.float32
        )

        tracks = list(app.tracks)

        isolated_index = getattr(app, "isolated_track_index", None)

        for track_index, track in enumerate(tracks):

            # Mute only affects the individual track.
            if getattr(track, "muted", False):
                continue

            # Isolate affects the whole mix: when one track is isolated,
            # every other track is silent.
            if isolated_index is not None and track_index != isolated_index:
                continue

            raw = track.engine.render(frames)

            if getattr(track, "is_drum_track", False):
                mix += raw
            else:
                mix += track.eq.process(raw)

        mix *= app.master_volume

        mix = np.clip(
            mix,
            -1.0,
            1.0
        )

        outdata[:, 0] = mix

    stream = sd.OutputStream(
        samplerate=SAMPLE_RATE,
        blocksize=64,
        channels=1,
        dtype="float32",
        latency="low",
        callback=callback,
    )

    stream.start()
    return stream

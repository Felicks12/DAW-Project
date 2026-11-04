"""Track data models: instrument tracks and the drum track."""

from synth_engine import ThreeBandEQ
from sound_generator import GeneratorEngine, DrumEngine

from .paths import resource_path


class Track:
    _next_id = 1

    def __init__(self, name=None, waveform="saw", instrument="Piano", sound="Grand Piano", track_id=None, track_type="instrument"):
        if track_id is None:
            self.id = Track._next_id
            Track._next_id += 1
        else:
            self.id = track_id
            Track._next_id = max(Track._next_id, track_id + 1)

        self.name = name or f"Track {self.id}"
        self.track_type = track_type
        self.is_drum_track = False
        self._instrument = instrument
        self._sound = sound

        # Instrument sounds are generated (see sound_generator.py); setting
        # track.sound later re-configures the engine automatically.
        self.engine = GeneratorEngine(waveform=waveform)
        self.engine.set_sound(sound)
        self.eq = ThreeBandEQ()
        self.notes = set()
        self.sounding = {}

        self.is_drum = False
        self.drum_part = None

        self.muted = False
        self.solo = False

        self.time_signature = (4, 4)

    @property
    def instrument(self):
        return self._instrument

    @instrument.setter
    def instrument(self, value):
        self._instrument = value

    @property
    def sound(self):
        return self._sound

    @sound.setter
    def sound(self, value):
        self._sound = value
        self.engine.all_notes_off()
        self.engine.set_sound(value)


class DrumTrack:
    _id = 999

    @property
    def notes(self):
        return self.parts[self.current_part]

    def __init__(self, name="Drums", sample_root=None):
        self.id = DrumTrack._id
        self.name = name
        self.track_type = "drum"
        self.is_drum_track = True

        self.instrument = "Drums"
        self.sound = "Drum Kit"

        # All drum parts live in this one track. current_part is the part
        # that is being edited / the "brush" used when clicking the grid.
        self.parts = {
            "Kick": set(),
            "Snare": set(),
            "Closed Hat": set(),
            "Open Hat": set(),
            "Crash": set(),
            "Low Tom": set(),
            "High Tom": set(),
        }

        self.current_part = "Kick"

        if sample_root is None:
            sample_root = resource_path("Samples")

        self.engine = DrumEngine(
            waveform="sine",
            master_volume=0.3,
            sample_root=sample_root
        )

        self.muted = False
        self.solo = False

        self.time_signature = (4, 4)

    def sample_label(self, part):
        """Short description of where a part's sound comes from."""
        source = self.engine.sample_sources.get(part, "")
        if source == "generated" or not source:
            return "generated"
        return source.rsplit(".", 1)[0]

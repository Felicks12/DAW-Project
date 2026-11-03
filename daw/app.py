"""PianoRollApp: owns the application state and wires the feature mixins together.

Feature code lives in the sibling modules (toolbar, playback, note_editing,
dropdowns, track_menu, ...). Add new features in their own module/mixin so
that parallel work doesn't collide in one giant file.
"""

import ctypes
import sys

import pygame

from .audio import start_audio
from .config import *
from .dropdowns import DropdownsMixin
from .drawing import DrawingMixin
from .events import EventsMixin
from .mouse_down import MouseDownMixin
from .mouse_motion import MouseMotionMixin
from .note_editing import NoteEditingMixin
from .paths import resource_path
from .playback import PlaybackMixin
from .preview import PreviewMixin
from .project_io import ProjectIOMixin
from .toolbar import ToolbarMixin
from .track_menu import TrackMenuMixin
from .track_naming import TrackNamingMixin
from .tracks import Track, DrumTrack
from .viewport import ViewportMixin


class PianoRollApp(
    ToolbarMixin,
    ViewportMixin,
    PlaybackMixin,
    PreviewMixin,
    NoteEditingMixin,
    DropdownsMixin,
    TrackMenuMixin,
    TrackNamingMixin,
    ProjectIOMixin,
    EventsMixin,
    MouseDownMixin,
    MouseMotionMixin,
    DrawingMixin,
):
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("CS Sound")
        icon = pygame.image.load(resource_path("MusicApp.ico"))
        pygame.display.set_icon(icon)

        pygame.mixer.init(
            frequency=44100,
            size=-16,
            channels=1,
            buffer=512
        )

        self.undo_stack = []
        self.max_undo_history = 100

        self.playhead_visual_time = 0.0
        self.playhead_delay = 0
        self.playback_start_time = 0.0
        self.last_playback_step = -1
        self.audio_lead = 0.20

        self.windowed_size = (DEFAULT_WINDOW_W, DEFAULT_WINDOW_H)
        self.fullscreen = False
        self.screen = pygame.display.set_mode(
            self.windowed_size,
            pygame.RESIZABLE
        )

        # Windows dark title bar
        import ctypes

        wm_info = pygame.display.get_wm_info()
        hwnd = wm_info.get("window")

        if hwnd:
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = ctypes.c_int(1)

            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value),
                ctypes.sizeof(value)
            )

        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("Arial", 12)
        self.font_small = pygame.font.SysFont("Arial", 10)
        self.font_title = pygame.font.SysFont("Arial", 15, bold=True)

        self.current_track_index = 0
        # None = no track isolated. Otherwise this is the index of the
        # single track that is allowed to play while isolation is active.
        self.isolated_track_index = None

        self.tracks = [Track(waveform="saw")]

        self.drum_track = DrumTrack()
        self.tracks.append(self.drum_track)
        self.drum_part = "Kick"
        self.editing_drum = False

        self.stream = start_audio(self)

        self.scroll_x = 0
        self.scroll_y = 0
        self.step_width = DEFAULT_STEP_WIDTH

        self.num_measures = INITIAL_MEASURES
        self.bpm = 120

        self.dragging_master_volume = False

        # Master output controls
        self.master_volume = 1.0

        # Metronome
        self.metronome_enabled = False

        # Playhead dragging
        self.dragging_playhead = False
        self.playhead_step = 0.0

        # Tap BPM
        self.tap_times = []


        self.playing = False
        self.play_pos_seconds = 0.0
        self.playhead_step = 0.0

        self.preview_pitch = None
        self.grid_preview_pitch = None
        self.grid_preview_release_at = 0

        self.resizing = None
        self.moving = None
        self.erasing = False

        # multi-select / clipboard
        self.selected_notes = set()
        self.marquee = None            # {"start": (x,y), "current": (x,y)}
        self.clipboard = []            # [(pitch, rel_start, length), ...]
        self.clipboard_end = 0

        self.editing_bpm = False
        self.bpm_input_str = ""

        self.show_help = False
        self.show_menu = False
        self.help_scroll = 0
        self.show_tracks_dropdown = False
        self.show_instr_dropdown = False
        self.hovered_instrument_category = None
        self.hovered_drum_track = None

        # track right-click context menu + settings popup
        self.track_context_menu = None     # {"index": i, "pos": (x, y)}
        self.show_track_settings = False
        self.track_settings_index = None
        self.dragging_slider = None        # {"index": i, "band": "bass"|"mid"|"treble"}

        self.show_time_signature_dropdown = False

        self.naming_track = False
        self.track_name_input = ""
        self.track_name_focused = False
        self.new_track_type = "instrument"

        self.current_file = None
        self.status_message = ""
        self.status_until = 0

        self.cursor_state = "arrow"

        mid_row = pitch_to_row(60)
        self.scroll_y = max(0, mid_row * ROW_HEIGHT - 200)

        self.running = True
        self.build_toolbar()

        self.drumNUM = 1
        self.customNUM = 0
        self.trackNUM = 1

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def track(self):
        return self.tracks[self.current_track_index]

    @property
    def notes(self):
        return self.track.notes

    @property
    def engine(self):
        return self.track.engine

    @property
    def total_steps(self):
        return self.num_measures * STEPS_PER_MEASURE

    @property
    def seconds_per_step(self):
        return 60.0 / self.bpm / STEPS_PER_BEAT

    @property
    def viewport_w(self):
        return self.screen.get_width()

    @property
    def viewport_h(self):
        return self.screen.get_height()

    @property
    def max_scroll_x(self):
        return max(
            0,
            self.total_steps * self.step_width
            - (self.viewport_w - KEY_AREA_WIDTH)
            + MEASURE_BTN_WIDTH * 2,
        )

    @property
    def max_scroll_y(self):
        return max(0, TOTAL_ROWS * ROW_HEIGHT - (self.viewport_h - GRID_Y))

    # ------------------------------------------------------------------
    # Status line
    # ------------------------------------------------------------------

    def set_status(self, message, error=False):
        self.status_message = message
        self.status_until = pygame.time.get_ticks() + 3500
        if error:
            print(message, file=sys.stderr)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0

            self.handle_events()
            self.update_previews()
            self.update_playback(dt)
            self.draw()

        for t in self.tracks:
            if getattr(t, "is_drum_track", False):
                t.playback_time = 0.0
            else:
                t.engine.all_notes_off()
                t.sounding.clear()

        self.stream.stop()
        self.stream.close()
        pygame.quit()

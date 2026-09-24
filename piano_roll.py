"""
piano_roll.py

Piano-roll GUI for the synth engine.

Current feature set:
  - 16th-note grid snapping and visible measure/beat/8th/16th subdivisions
  - Track / Instrument dropdown arrows, hierarchical instrument browser
  - Right-click a track in the Tracks dropdown for a Settings / Delete popup
  - Per-track Bass / Mid / Treble sliders (with a redline boost zone and a
    live level meter) in the track Settings popup
  - Pause keeps the playhead visible
  - Reliable BPM text entry
  - Save / Load .pysynth project files with naming (native file dialogs)
  - Note audition when placing/moving notes
  - Notes placed near an existing note auto-shrink instead of overlapping
  - Shift + drag: marquee-select multiple notes; Ctrl+C / Ctrl+V to copy/paste;
    Delete/Backspace removes the current selection
  - Track-name popup when adding a track
"""

import json
import os
import sys
import tkinter as tk
from tkinter import filedialog

import numpy as np
import pygame
import sounddevice as sd
import soundfile as sf
import time

from synth_engine import SynthEngine, ThreeBandEQ, SAMPLE_RATE, WAVEFORMS, load_wav_file


# ---------------------------------------------------------------------------
# Layout / musical constants
# ---------------------------------------------------------------------------

WHITE_KEYS = {0, 2, 4, 5, 7, 9, 11}
MIN_NOTE = 0
MAX_NOTE = 127
TOTAL_ROWS = MAX_NOTE - MIN_NOTE + 1
ROW_HEIGHT = 18

KEY_AREA_WIDTH = 90
TOP_BAR_H = 50
LABEL_H = 22
GRID_Y = TOP_BAR_H + LABEL_H

STEPS_PER_BEAT = 4                 # 4 steps per quarter = 16th notes
BEATS_PER_MEASURE = 4
STEPS_PER_MEASURE = STEPS_PER_BEAT * BEATS_PER_MEASURE
DEFAULT_STEP_WIDTH = 22
MIN_STEP_WIDTH = 3
MAX_STEP_WIDTH = 140
DEFAULT_NOTE_LEN_STEPS = STEPS_PER_BEAT * 2
MEASURE_BTN_WIDTH = 34
EDGE_GRAB_PX = 6

INITIAL_MEASURES = 16
MIN_MEASURES = 1
MAX_MEASURES = 256

DEFAULT_WINDOW_W = 1100
DEFAULT_WINDOW_H = 650

DROPDOWN_ROW_H = 26
TRACK_PANEL_W = 190
INSTR_PANEL_W = 190
SUB_INSTR_PANEL_W = 190
CONTEXT_MENU_W = 150

BG_COLOR = (30, 30, 34)
TOOLBAR_COLOR = (24, 24, 27)
LABEL_BG = (26, 26, 29)
GRID_LINE = (68, 68, 75)
BEAT_LINE = (90, 90, 100)
MEASURE_LINE = (130, 130, 145)
NOTE_COLOR = (90, 170, 230)
NOTE_BORDER = (140, 200, 250)
NOTE_MOVING_COLOR = (140, 220, 140)
NOTE_MOVING_BORDER = (190, 250, 190)
NOTE_SELECTED_BORDER = (255, 215, 90)
NOTE_EDGE_HANDLE = (220, 230, 240)
PLAYHEAD_COLOR = (230, 90, 90)
WHITE_KEY_COLOR = (235, 235, 235)
BLACK_KEY_COLOR = (35, 35, 38)
WHITE_KEY_PRESSED = (160, 200, 240)
BLACK_KEY_PRESSED = (70, 110, 160)
ROW_ALT_COLOR = (38, 38, 43)
BTN_COLOR = (55, 55, 62)
BTN_ACTIVE = (90, 140, 90)
BTN_HELP_ACTIVE = (80, 110, 150)
TEXT_COLOR = (220, 220, 220)
MUTED_TEXT = (140, 140, 145)
INPUT_BOX_COLOR = (15, 15, 17)
INPUT_BOX_EDITING = (60, 60, 100)
HELP_BG = (20, 20, 23)
HELP_BORDER = (90, 90, 100)
DROPDOWN_BG = (32, 32, 37)
DROPDOWN_BORDER = (90, 90, 100)
DROPDOWN_HOVER = (50, 50, 58)
DROPDOWN_SELECTED = (55, 80, 110)
DROPDOWN_ARROW_BG = (40, 40, 46)
FLASH_COLOR = (105, 135, 175)
ADD_BUTTON_COLOR = (65, 150, 80)
MENU_PANEL_W = 150
MODAL_BG = (25, 25, 29)
MODAL_BORDER = (100, 100, 110)
ERROR_COLOR = (220, 100, 100)
MARQUEE_FILL = (120, 170, 255, 60)
MARQUEE_BORDER = (150, 190, 255)
SLIDER_TRACK_COLOR = (55, 55, 62)
SLIDER_REDLINE_COLOR = (110, 45, 45)
SLIDER_HANDLE_COLOR = (200, 205, 215)
SLIDER_HANDLE_HOT = (230, 90, 90)
METER_BG = (40, 40, 46)
METER_OK_COLOR = (95, 180, 110)
METER_HOT_COLOR = (220, 90, 90)

INSTRUMENTS = {
    "Piano": ["Grand Piano", "Bright Piano", "Electric Piano", "Honky Tonk"],
    "Guitar": ["Classic Guitar", "Electric Guitar", "Spanish Guitar", "Acoustic Guitar"],
    "Bass": ["Electric Bass", "Acoustic Bass", "Synth Bass", "Fretless Bass"],
    "Strings": ["Violin", "Cello", "Viola", "String Ensemble"],
    "Brass": ["Trumpet", "Trombone", "French Horn", "Brass Section"],
    "Woodwinds": ["Flute", "Clarinet", "Oboe", "Saxophone"],
    "Synth": ["Lead", "Pad", "Pluck", "Synth Brass"],
    "Organ": ["Pipe Organ", "Rock Organ", "Church Organ"],
    "Mallets": ["Marimba", "Vibraphone", "Xylophone", "Glockenspiel"],
}

EQ_BANDS = ["bass", "mid", "treble"]


def pitch_to_row(pitch):
    return MAX_NOTE - pitch


def row_to_pitch(row):
    return MAX_NOTE - row


def is_white_key(pitch):
    return (pitch % 12) in WHITE_KEYS


HELP_LINES = [
    "Space: play / pause",
    "F11: toggle fullscreen",
    "Left click empty cell: add a 16th-note-snapped note",
    "  (auto-shrinks to fit if it would overlap a neighboring note)",
    "Left click + drag a note's body: move that note",
    "Left click + drag a note's left/right edge: resize that note",
    "Right click: delete a note. Hold + drag: delete across notes",
    "Shift + drag on the grid: rubber-band select multiple notes",
    "Ctrl+C / Ctrl+V: copy / paste the current selection",
    "Delete or Backspace: delete the current selection",
    "Scroll wheel: move left / right along the timeline",
    "Shift + scroll: move up / down the keyboard",
    "Ctrl + scroll: zoom in / out",
    "Up / Down: move up / down the keyboard",
    "Click BPM, type a number, then press Enter",
    "Tracks: switch tracks, or use + Add track to name a new one",
    "Right click a track: open its Settings (incl. Bass/Mid/Treble) or delete it",
    "Instrument: hover a category to open its sound submenu",
    "Save / Load: save or open .pysynth project files",
    "The selected track is edited visually; all tracks play together",
]


# ---------------------------------------------------------------------------
# Small UI helpers
# ---------------------------------------------------------------------------

class Button:
    def __init__(self, rect, label, dropdown=False):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.dropdown = dropdown
        self.pressed_until = 0

    def contains(self, pos):
        return self.rect.collidepoint(pos)

    def flash(self, duration=65):
        self.pressed_until = pygame.time.get_ticks() + duration

    def draw(self, screen, font, active=False, active_color=BTN_ACTIVE):
        now = pygame.time.get_ticks()
        color = active_color if active else BTN_COLOR
        if now < self.pressed_until:
            color = FLASH_COLOR

        pygame.draw.rect(screen, color, self.rect, border_radius=4)
        pygame.draw.rect(screen, (10, 10, 10), self.rect, 1, border_radius=4)

        if self.dropdown:
            section_w = 18
            section = pygame.Rect(self.rect.right - section_w, self.rect.y + 1, section_w - 1, self.rect.height - 2)
            pygame.draw.rect(screen, DROPDOWN_ARROW_BG, section)
            pygame.draw.line(screen, (10, 10, 10), (section.left, section.top), (section.left, section.bottom))
            points = [(section.centerx - 3, section.centery - 2), (section.centerx + 3, section.centery - 2), (section.centerx, section.centery + 3)]
            pygame.draw.polygon(screen, MUTED_TEXT, points)
            text_area_right = section.left - 3
        else:
            text_area_right = self.rect.right

        text = font.render(self.label, True, (20, 20, 20) if now < self.pressed_until else TEXT_COLOR)
        tx = self.rect.x + (text_area_right - self.rect.x - text.get_width()) // 2
        ty = self.rect.y + (self.rect.height - text.get_height()) // 2
        screen.blit(text, (tx, ty))


def draw_arrow(screen, font, x, y, direction="right"):
    """Draw a small text arrow; this is deliberately subtle."""
    symbol = ">" if direction == "right" else "v"
    screen.blit(font.render(symbol, True, MUTED_TEXT), (x, y))


# ---------------------------------------------------------------------------
# Track
# ---------------------------------------------------------------------------

class Track:
    _next_id = 1

    def __init__(self, name=None, waveform="saw", instrument="Piano", sound="Grand Piano", track_id=None):
        if track_id is None:
            self.id = Track._next_id
            Track._next_id += 1
        else:
            self.id = track_id
            Track._next_id = max(Track._next_id, track_id + 1)

        self.name = name or f"Track {self.id}"
        self.instrument = instrument
        self.sound = sound
        # The actual synth implementation still uses waveforms internally.
        # Instrument selection is metadata/UI for now, as requested.
        self.engine = SynthEngine(waveform=waveform)
        self.engine.set_instrument("piano")
        self.eq = ThreeBandEQ()
        self.notes = set()
        self.sounding = {}

        self.is_drum = False
        self.drum_part = None

# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------

def start_audio(app):
    def callback(outdata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)

        mix = np.zeros(
            frames,
            dtype=np.float32
        )

        for track in list(app.tracks):

            raw = track.engine.render(frames)

            if getattr(track, "is_drum_track", False):
                mix += raw
            else:
                mix += track.eq.process(raw)

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

class DrumTrack:
    _id = 999

    @property
    def notes(self):
        return self.parts[self.current_part]

    def __init__(self, name="Drums", sample_root=None):
        self.id = DrumTrack._id
        self.name = name
        self.is_drum_track = True

        self.instrument = "Drums"
        self.sound = "Drum Kit"

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
            sample_root = os.path.join(
                os.path.dirname(
                    os.path.abspath(__file__)
                ),
                "Samples"
            )

        self.engine = SynthEngine(
            waveform="sine",
            master_volume=0.3,
            sample_root=sample_root
        )

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class PianoRollApp:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("pysynth — piano roll")

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
        self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("Arial", 12)
        self.font_small = pygame.font.SysFont("Arial", 10)
        self.font_title = pygame.font.SysFont("Arial", 15, bold=True)

        self.current_track_index = 0

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

        self.playing = False
        self.play_pos_seconds = 0.0

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

        self.naming_track = False
        self.track_name_input = ""
        self.track_name_focused = False

        self.current_file = None
        self.status_message = ""
        self.status_until = 0

        self.cursor_state = "arrow"

        mid_row = pitch_to_row(60)
        self.scroll_y = max(0, mid_row * ROW_HEIGHT - 200)

        self.running = True
        self.build_toolbar()

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
    # Toolbar
    # ------------------------------------------------------------------

    def save_undo_state(self):
        state = []

        for t in self.tracks:
            if getattr(t, "is_drum_track", False):
                state.append({
                    "type": "drum",
                    "parts": {
                        name: set(notes)
                        for name, notes in t.parts.items()
                    }
                })
            else:
                state.append({
                    "type": "instrument",
                    "notes": set(t.notes)
                })

        self.undo_stack.append(state)

        if len(self.undo_stack) > self.max_undo_history:
            self.undo_stack.pop(0)

    def undo(self):
        if not self.undo_stack:
            return

        state = self.undo_stack.pop()

        for t, notes in zip(self.tracks, state):
            t.notes.clear()
            t.notes.update(notes)

        self.selected_notes = set()

        for t in self.tracks:
            t.engine.all_notes_off()
            t.sounding.clear()

    def build_toolbar(self):
        x = 8
        y = 10
        h = TOP_BAR_H - 20
        self.btn_play = Button((x, y, 58, h), "Play"); x += 64
        self.btn_stop = Button((x, y, 58, h), "Stop"); x += 64
        self.btn_bpm_down = Button((x, y, 24, h), "-"); x += 28
        self.bpm_box = pygame.Rect(x, y, 72, h); x += 76
        self.btn_bpm_up = Button((x, y, 24, h), "+"); x += 30
        self.btn_tracks = Button((x, y, 78, h), "Tracks", dropdown=True); x += 84
        self.btn_instr = Button((x, y, 98, h), "Piano", dropdown=True); x += 104
        self.btn_menu = Button((self.windowed_size[0] - 48, y, 40, h), "")

    def reposition_toolbar(self):
        self.btn_menu.rect.x = self.viewport_w - 48

    def update_toolbar_labels(self):
        self.btn_play.label = "Pause" if self.playing else "Play"
        self.btn_instr.label = self.track.instrument
        self.reposition_toolbar()

    # ------------------------------------------------------------------
    # Coordinates / snapping
    # ------------------------------------------------------------------

    def screen_x_to_step(self, x):
        return (x - KEY_AREA_WIDTH + self.scroll_x) / self.step_width

    def step_to_screen_x(self, step):
        return KEY_AREA_WIDTH + step * self.step_width - self.scroll_x

    def screen_y_to_row(self, y):
        return int((y - GRID_Y + self.scroll_y) // ROW_HEIGHT)

    def row_to_screen_y(self, row):
        return GRID_Y + row * ROW_HEIGHT - self.scroll_y

    def current_snap_steps(self):
        # Always snap to a 16th note. The grid may become visually compressed
        # at low zoom, but musical placement remains 16th-note accurate.
        return 1

    # ------------------------------------------------------------------
    # Dropdown geometry
    # ------------------------------------------------------------------

    def tracks_panel_rect(self):
        rows = len(self.tracks) + 1
        h = rows * DROPDOWN_ROW_H + 8
        return pygame.Rect(
            self.btn_tracks.rect.x,
            TOP_BAR_H,
            TRACK_PANEL_W,
            h
        )

    def instr_panel_rect(self):
        h = len(INSTRUMENTS) * DROPDOWN_ROW_H + 8
        return pygame.Rect(self.btn_instr.rect.x, TOP_BAR_H, INSTR_PANEL_W, h)

    def instr_subpanel_rect(self):
        if self.hovered_instrument_category is None:
            return pygame.Rect(0, 0, 0, 0)
        categories = list(INSTRUMENTS)
        idx = categories.index(self.hovered_instrument_category)
        y = TOP_BAR_H + 4 + idx * DROPDOWN_ROW_H
        return pygame.Rect(
            self.instr_panel_rect().right - 2,
            y,
            SUB_INSTR_PANEL_W,
            len(INSTRUMENTS[self.hovered_instrument_category]) * DROPDOWN_ROW_H + 8,
        )

    def close_dropdowns(self):
        self.show_tracks_dropdown = False
        self.show_instr_dropdown = False
        self.hovered_instrument_category = None
        self.hovered_drum_track = None

    # ------------------------------------------------------------------
    # Track right-click context menu (Settings / Delete)
    # ------------------------------------------------------------------

    def track_context_menu_rect(self):
        if self.track_context_menu is None:
            return pygame.Rect(0, 0, 0, 0)

        x, y = self.track_context_menu["pos"]
        w = CONTEXT_MENU_W
        h = DROPDOWN_ROW_H + 8

        x = min(x, self.viewport_w - w - 4)
        y = min(y, self.viewport_h - h - 4)

        return pygame.Rect(x, y, w, h)

    def draw_track_context_menu(self):
        if self.track_context_menu is None:
            return

        rect = self.track_context_menu_rect()

        pygame.draw.rect(
            self.screen,
            DROPDOWN_BG,
            rect,
            border_radius=4
        )
        pygame.draw.rect(
            self.screen,
            DROPDOWN_BORDER,
            rect,
            1,
            border_radius=4
        )
        mouse_pos = pygame.mouse.get_pos()
        delete_row = pygame.Rect(
            rect.x + 4,
            rect.y + 4,
            rect.width - 8,
            DROPDOWN_ROW_H
        )
        can_delete = len(self.tracks) > 1
        if can_delete and delete_row.collidepoint(mouse_pos):
            pygame.draw.rect(
                self.screen,
                DROPDOWN_HOVER,
                delete_row
            )
        delete_color = (210, 120, 120) if can_delete else MUTED_TEXT
        delete_label = self.font.render(
            "Delete Track",
            True,
            delete_color
        )
        self.screen.blit(
            delete_label,
            (
                delete_row.x + 6,
                delete_row.y + (delete_row.height - delete_label.get_height()) // 2
            )
        )

    def handle_track_context_menu_click(self, pos):
        rect = self.track_context_menu_rect()
        idx = self.track_context_menu["index"]

        if not rect.collidepoint(pos):
            self.track_context_menu = None
            return

        delete_row = pygame.Rect(
            rect.x + 4,
            rect.y + 4,
            rect.width - 8,
            DROPDOWN_ROW_H
        )

        if delete_row.collidepoint(pos) and len(self.tracks) > 1:
            self.tracks[idx].engine.all_notes_off()
            del self.tracks[idx]

            if self.current_track_index >= len(self.tracks):
                self.current_track_index = len(self.tracks) - 1
            elif self.current_track_index > idx:
                self.current_track_index -= 1

            self.selected_notes = set()
            self.track_context_menu = None
            self.update_toolbar_labels()
            return

        self.track_context_menu = None

    # ------------------------------------------------------------------
    # Track settings popup (Bass / Mid / Treble)
    # ------------------------------------------------------------------

    def track_settings_panel_rect(self):
        w, h = 380, 320
        return pygame.Rect((self.viewport_w - w) // 2, (self.viewport_h - h) // 2, w, h)

    def track_settings_slider_rects(self):
        panel = self.track_settings_panel_rect()
        slider_h = 180
        slider_top = panel.y + 78
        xs = [panel.x + 80, panel.x + 190, panel.x + 300]
        return {band: pygame.Rect(x - 10, slider_top, 20, slider_h) for band, x in zip(EQ_BANDS, xs)}

    def update_slider_from_mouse(self, pos):
        d = self.dragging_slider
        if d is None:
            return
        rect = self.track_settings_slider_rects()[d["band"]]
        y = max(rect.top, min(rect.bottom, pos[1]))
        frac = 1.0 - (y - rect.top) / rect.height
        gain = max(0.0, min(2.0, frac * 2.0))
        setattr(self.tracks[d["index"]].eq, f"{d['band']}_gain", gain)

    def draw_track_settings(self):
        if not self.show_track_settings:
            return
        if self.track_settings_index is None or self.track_settings_index >= len(self.tracks):
            self.show_track_settings = False
            return

        overlay = pygame.Surface((self.viewport_w, self.viewport_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 130))
        self.screen.blit(overlay, (0, 0))

        track = self.tracks[self.track_settings_index]
        panel = self.track_settings_panel_rect()
        pygame.draw.rect(self.screen, MODAL_BG, panel, border_radius=8)
        pygame.draw.rect(self.screen, MODAL_BORDER, panel, 1, border_radius=8)

        title = self.font_title.render(f"{track.name} — Settings", True, TEXT_COLOR)
        self.screen.blit(title, (panel.x + 18, panel.y + 14))

        close_rect = pygame.Rect(panel.right - 30, panel.y + 8, 22, 22)
        pygame.draw.rect(self.screen, BTN_COLOR, close_rect, border_radius=4)
        self.screen.blit(self.font.render("x", True, TEXT_COLOR), (close_rect.x + 7, close_rect.y + 4))

        if track.eq.clipping:
            clip_label = self.font_small.render("CLIP", True, METER_HOT_COLOR)
            self.screen.blit(clip_label, (panel.right - 70, panel.y + 12))

        sliders = self.track_settings_slider_rects()
        levels = {
            "bass": track.eq.last_bass_level,
            "mid": track.eq.last_mid_level,
            "treble": track.eq.last_treble_level,
        }

        for band in EQ_BANDS:
            rect = sliders[band]
            gain = getattr(track.eq, f"{band}_gain")

            # slider track: lower half (0.0-1.0, cut-to-unity) neutral,
            # upper half (1.0-2.0, boost) tinted red as a "redline" warning
            unity_y = rect.y + rect.height // 2
            lower_rect = pygame.Rect(rect.x, unity_y, rect.width, rect.bottom - unity_y)
            upper_rect = pygame.Rect(rect.x, rect.y, rect.width, unity_y - rect.y)
            pygame.draw.rect(self.screen, SLIDER_TRACK_COLOR, lower_rect)
            pygame.draw.rect(self.screen, SLIDER_REDLINE_COLOR, upper_rect)
            pygame.draw.rect(self.screen, (10, 10, 10), rect, 1)
            pygame.draw.line(self.screen, MUTED_TEXT, (rect.x - 4, unity_y), (rect.right + 4, unity_y), 1)

            # handle
            frac = gain / 2.0
            handle_y = int(rect.y + rect.height * (1.0 - frac))
            handle_color = SLIDER_HANDLE_HOT if gain > 1.5 else SLIDER_HANDLE_COLOR
            handle_rect = pygame.Rect(rect.x - 6, handle_y - 5, rect.width + 12, 10)
            pygame.draw.rect(self.screen, handle_color, handle_rect, border_radius=3)
            pygame.draw.rect(self.screen, (10, 10, 10), handle_rect, 1, border_radius=3)

            # live level meter beside the fader
            meter_rect = pygame.Rect(rect.right + 10, rect.y, 8, rect.height)
            pygame.draw.rect(self.screen, METER_BG, meter_rect)
            level = min(1.0, levels[band] * 4.0)  # scale RMS up so it's visible
            fill_h = int(meter_rect.height * level)
            fill_rect = pygame.Rect(meter_rect.x, meter_rect.bottom - fill_h, meter_rect.width, fill_h)
            meter_color = METER_HOT_COLOR if level > 0.85 else METER_OK_COLOR
            pygame.draw.rect(self.screen, meter_color, fill_rect)
            pygame.draw.rect(self.screen, (10, 10, 10), meter_rect, 1)

            # label + percentage
            label = self.font.render(band.capitalize(), True, TEXT_COLOR)
            self.screen.blit(label, (rect.centerx - label.get_width() // 2, rect.bottom + 10))
            pct = self.font_small.render(f"{int(gain * 100)}%", True, MUTED_TEXT)
            self.screen.blit(pct, (rect.centerx - pct.get_width() // 2, rect.bottom + 28))

        hint = self.font_small.render("Drag a slider — the red zone above center boosts (watch for CLIP).", True, MUTED_TEXT)
        self.screen.blit(hint, (panel.x + 18, panel.bottom - 26))

    # ------------------------------------------------------------------
    # Native save/load dialogs
    # ------------------------------------------------------------------

    @staticmethod
    def _file_dialog_root():
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        return root

    def save_project(self):
        root = self._file_dialog_root()
        initial = os.path.basename(self.current_file) if self.current_file else "MySynthProject.pysynth"
        path = filedialog.asksaveasfilename(
            parent=root,
            title="Save pysynth project",
            defaultextension=".pysynth",
            initialfile=initial,
            filetypes=[("pysynth project", "*.pysynth"), ("JSON", "*.json"), ("All files", "*.*")],
        )
        root.destroy()

        if not path:
            return

        data = {
            "format": "pysynth",
            "version": 1,
            "bpm": self.bpm,
            "num_measures": self.num_measures,
            "tracks": [],
        }

        for track in self.tracks:
            data["tracks"].append({
                "id": track.id,
                "name": track.name,
                "instrument": track.instrument,
                "sound": track.sound,
                "waveform": track.engine.waveform_name,
                "eq": {
                    "bass": track.eq.bass_gain,
                    "mid": track.eq.mid_gain,
                    "treble": track.eq.treble_gain,
                },
                "notes": [list(n) for n in sorted(track.notes)],
            })

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            self.current_file = path
            self.set_status(f"Saved: {os.path.basename(path)}")
        except OSError as exc:
            self.set_status(f"Save failed: {exc}", error=True)

    def load_project(self):
        root = self._file_dialog_root()
        path = filedialog.askopenfilename(
            parent=root,
            title="Load pysynth project",
            filetypes=[("pysynth project", "*.pysynth"), ("JSON", "*.json"), ("All files", "*.*")],
        )
        root.destroy()

        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("format") != "pysynth":
                raise ValueError("Not a pysynth project file.")

            loaded_tracks = []
            for td in data.get("tracks", []):
                track = Track(
                    name=td.get("name"),
                    waveform=td.get("waveform", "saw"),
                    instrument=td.get("instrument", "Piano"),
                    sound=td.get("sound", "Grand Piano"),
                    track_id=td.get("id"),
                )
                track.notes = {
                    (int(n[0]), int(n[1]), int(n[2]))
                    for n in td.get("notes", [])
                    if len(n) == 3
                }
                eq_data = td.get("eq", {})
                track.eq.bass_gain = float(eq_data.get("bass", 1.0))
                track.eq.mid_gain = float(eq_data.get("mid", 1.0))
                track.eq.treble_gain = float(eq_data.get("treble", 1.0))
                loaded_tracks.append(track)

            if not loaded_tracks:
                loaded_tracks = [Track(waveform="saw")]

            self.tracks = loaded_tracks
            self.current_track_index = 0
            self.selected_notes = set()
            self.bpm = max(20, min(300, int(data.get("bpm", 120))))
            self.num_measures = max(
                MIN_MEASURES,
                min(MAX_MEASURES, int(data.get("num_measures", INITIAL_MEASURES))),
            )

            self.current_file = path
            self.play_pos_seconds = 0.0
            for t in self.tracks:
                t.engine.all_notes_off()
                t.sounding.clear()

            self.set_status(f"Loaded: {os.path.basename(path)}")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self.set_status(f"Load failed: {exc}", error=True)

    def set_status(self, message, error=False):
        self.status_message = message
        self.status_until = pygame.time.get_ticks() + 3500
        if error:
            print(message, file=sys.stderr)

    # ------------------------------------------------------------------
    # Track naming popup
    # ------------------------------------------------------------------

    def open_track_naming(self):
        self.close_dropdowns()
        self.naming_track = True
        self.track_name_input = ""
        self.track_name_focused = False
        self._stop_preview()

    def commit_track_naming(self):
        name = self.track_name_input.strip()

        # Don't create a track with an empty name.
        if not name:
            name = f"Track {len(self.tracks) + 1}"

        # Try to copy the setup of the current track.
        current_track = self.tracks[self.current_track_index]

        new_track = type(current_track)(
            name=name,
            instrument=current_track.instrument,
            sound=current_track.sound,
        )

        self.tracks.append(new_track)
        self.current_track_index = len(self.tracks) - 1
        self.selected_notes = set()

        self.naming_track = False
        self.track_name_input = ""
        self.track_name_focused = False

        self.update_toolbar_labels()

    def commit_move(self):
        m = self.moving

        if not m["valid"]:
            return

        selected_orig = m["selected_orig"]
        delta_steps = m.get("current_delta_steps", 0)
        delta_rows = m.get("current_delta_rows", 0)

        if delta_steps == 0 and delta_rows == 0:
            return

        # Save undo state before actually changing the notes.
        self.save_undo_state()

        selected_set = set(selected_orig)

        # Remove all original selected notes.
        for note in selected_orig:
            self.get_current_notes().discard(note)

        # Add all moved notes.
        new_selected = set()

        for pitch, start, length in selected_orig:
            new_note = (
                pitch - delta_rows,
                start + delta_steps,
                length
            )

            self.get_current_notes().add(new_note)
            new_selected.add(new_note)

        # Keep the moved notes selected.
        self.selected_notes = new_selected

    def get_current_notes(self):
        track = self.tracks[self.current_track_index]

        if getattr(track, "is_drum_track", False):
            return track.parts[track.current_part]

        return track.notes

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.VIDEORESIZE:
                if not self.fullscreen:
                    self.windowed_size = (event.w, event.h)

            elif event.type == pygame.KEYDOWN:
                self.handle_keydown(event)

            elif event.type == pygame.MOUSEWHEEL:
                self.handle_wheel(event)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.handle_mouse_down(event.pos, event.button)

            elif event.type == pygame.MOUSEBUTTONUP:
                self.handle_mouse_up(event.pos, event.button)

            elif event.type == pygame.MOUSEMOTION:
                self.handle_mouse_motion(event.pos)

        self.update_toolbar_labels()
        self.update_cursor()

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.windowed_size = self.screen.get_size()
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)

    def handle_keydown(self, event):
        key = event.key

        # --------------------------------------------------------------
        # Track-name popup text entry
        # --------------------------------------------------------------
        if self.naming_track:
            if self.track_name_focused:
                if key == pygame.K_RETURN:
                    self.commit_track_naming()
                    return

                if key == pygame.K_ESCAPE:
                    self.naming_track = False
                    self.track_name_input = ""
                    self.track_name_focused = False
                    return

                if key == pygame.K_BACKSPACE:
                    self.track_name_input = self.track_name_input[:-1]
                    return

                if event.unicode and event.unicode.isprintable():
                    if len(self.track_name_input) < 80:
                        self.track_name_input += event.unicode
                    return

            else:
                if key == pygame.K_ESCAPE:
                    self.naming_track = False
                    self.track_name_input = ""
                    self.track_name_focused = False
                    return

            return

        # --------------------------------------------------------------
        # Track context menu / settings popup gate other keys while open
        # --------------------------------------------------------------
        if self.track_context_menu is not None:
            if key == pygame.K_ESCAPE:
                self.track_context_menu = None
            return

        if self.show_track_settings:
            if key == pygame.K_ESCAPE:
                self.show_track_settings = False
            return

        # --------------------------------------------------------------
        # BPM text entry
        # --------------------------------------------------------------
        if self.editing_bpm:
            if key == pygame.K_RETURN:
                try:
                    value = int(self.bpm_input_str)
                    self.bpm = max(20, min(300, value))
                except ValueError:
                    pass

                self.editing_bpm = False
                self.bpm_input_str = ""
                return

            if key == pygame.K_ESCAPE:
                self.editing_bpm = False
                self.bpm_input_str = ""
                return

            if key == pygame.K_BACKSPACE:
                self.bpm_input_str = self.bpm_input_str[:-1]
                return

            if event.unicode.isdigit():
                if len(self.bpm_input_str) < 3:
                    self.bpm_input_str += event.unicode
                return

            return

        # --------------------------------------------------------------
        # Help / menu
        # --------------------------------------------------------------
        if self.show_help:
            if key == pygame.K_ESCAPE:
                self.show_help = False
                return

            if key == pygame.K_UP:
                self.help_scroll = max(0, self.help_scroll - 1)
                return

            if key == pygame.K_DOWN:
                self.help_scroll += 1
                return

            return

        if self.show_menu:
            if key == pygame.K_ESCAPE:
                self.show_menu = False
            return

        # --------------------------------------------------------------
        # General keyboard controls
        # --------------------------------------------------------------
        if key == pygame.K_SPACE:
            self.toggle_play()
            return

        if key == pygame.K_F11:
            self.toggle_fullscreen()
            return

        mods = pygame.key.get_mods()

        if key == pygame.K_c and (mods & pygame.KMOD_CTRL):
            self.copy_selected_notes()
            return

        if key == pygame.K_v and (mods & pygame.KMOD_CTRL):
            self.paste_notes()
            return

        if key == pygame.K_z and (mods & pygame.KMOD_CTRL):
            self.undo()
            return

        if key in (pygame.K_DELETE, pygame.K_BACKSPACE) and self.selected_notes:
            self.save_undo_state()
            self.get_current_notes().difference_update(self.selected_notes)
            self.selected_notes = set()
            return

        if key == pygame.K_UP:
            self.scroll_y = max(0, self.scroll_y - ROW_HEIGHT)
            return

        if key == pygame.K_DOWN:
            self.scroll_y = min(self.max_scroll_y, self.scroll_y + ROW_HEIGHT)
            return

        if key == pygame.K_LEFT:
            self.scroll_x = max(0, self.scroll_x - self.step_width)
            return

        if key == pygame.K_RIGHT:
            self.scroll_x = min(self.max_scroll_x, self.scroll_x + self.step_width)
            return

    def handle_wheel(self, event):
        if self.naming_track or self.show_track_settings:
            return

        if self.show_help:
            self.help_scroll = max(0, self.help_scroll - event.y * 18)
            return

        mods = pygame.key.get_mods()

        if mods & pygame.KMOD_CTRL:
            self.zoom(event.y if event.y != 0 else event.x)
            return

        if mods & pygame.KMOD_SHIFT:
            delta = event.y if event.y != 0 else event.x
            self.scroll_y -= delta * ROW_HEIGHT * 3
            self.scroll_y = max(0, min(self.scroll_y, self.max_scroll_y))
        else:
            self.scroll_x -= event.y * self.step_width * 2
            self.scroll_x = max(0, min(self.scroll_x, self.max_scroll_x))

    def zoom(self, direction):
        if direction == 0:
            return

        mouse_x, _ = pygame.mouse.get_pos()
        step_under_mouse = self.screen_x_to_step(mouse_x)
        factor = 1.15 if direction > 0 else (1 / 1.15)

        self.step_width = max(MIN_STEP_WIDTH, min(MAX_STEP_WIDTH, self.step_width * factor))

        self.scroll_x = step_under_mouse * self.step_width - (mouse_x - KEY_AREA_WIDTH)
        self.scroll_x = max(0, min(self.scroll_x, self.max_scroll_x))

    # ------------------------------------------------------------------
    # Copy / paste
    # ------------------------------------------------------------------

    def copy_selected_notes(self):
        if not self.selected_notes:
            return
        min_start = min(n[1] for n in self.selected_notes)
        self.clipboard = sorted((n[0], n[1] - min_start, n[2]) for n in self.selected_notes)
        self.clipboard_end = max(n[1] + n[2] for n in self.selected_notes)

    def paste_notes(self):
        if not self.clipboard:
            return
        anchor = self.clipboard_end
        pasted = set()
        for pitch, rel_start, length in self.clipboard:
            new_start = anchor + rel_start
            if new_start + length > self.total_steps:
                continue
            if self.overlaps(pitch, new_start, length):
                continue
            note = (pitch, new_start, length)
            self.get_current_notes().add(note)
            pasted.add(note)

        if pasted:
            self.selected_notes = pasted
            self.clipboard_end = max(n[1] + n[2] for n in pasted)

    # ------------------------------------------------------------------
    # Mouse handling
    # ------------------------------------------------------------------

    def handle_mouse_down(self, pos, button):
        # --------------------------------------------------------------
        # Track-name popup
        # --------------------------------------------------------------
        if self.naming_track:
            panel_w = 420
            panel_h = 190
            panel = pygame.Rect((self.viewport_w - panel_w) // 2, (self.viewport_h - panel_h) // 2, panel_w, panel_h)
            input_rect = pygame.Rect(panel.x + 35, panel.y + 70, panel.w - 70, 38)
            add_rect = pygame.Rect(panel.x + 35, panel.bottom - 55, 120, 35)
            cancel_rect = pygame.Rect(panel.right - 155, panel.bottom - 55, 120, 35)

            if input_rect.collidepoint(pos):
                self.track_name_focused = True
                return

            if add_rect.collidepoint(pos):
                if self.track_name_focused:
                    self.commit_track_naming()
                return

            if cancel_rect.collidepoint(pos):
                self.naming_track = False
                self.track_name_input = ""
                self.track_name_focused = False
                return

            if not panel.collidepoint(pos):
                self.naming_track = False
                self.track_name_input = ""
                self.track_name_focused = False

            return

        # --------------------------------------------------------------
        # Track settings popup
        # --------------------------------------------------------------
        if self.show_track_settings:
            panel = self.track_settings_panel_rect()
            close_rect = pygame.Rect(panel.right - 30, panel.y + 8, 22, 22)

            if close_rect.collidepoint(pos):
                self.show_track_settings = False
                return

            if not panel.collidepoint(pos):
                self.show_track_settings = False
                return

            sliders = self.track_settings_slider_rects()
            for band, rect in sliders.items():
                if rect.inflate(24, 16).collidepoint(pos):
                    self.dragging_slider = {"index": self.track_settings_index, "band": band}
                    self.update_slider_from_mouse(pos)
                    return

            return

        # --------------------------------------------------------------
        # Track right-click context menu
        # --------------------------------------------------------------
        if self.track_context_menu is not None:
            self.handle_track_context_menu_click(pos)
            return

        # --------------------------------------------------------------
        # Help window
        # --------------------------------------------------------------
        if self.show_help:
            help_w = min(700, self.viewport_w - 80)
            help_h = min(500, self.viewport_h - 80)
            help_rect = pygame.Rect((self.viewport_w - help_w) // 2, (self.viewport_h - help_h) // 2, help_w, help_h)

            if not help_rect.collidepoint(pos):
                self.show_help = False

            return

        # --------------------------------------------------------------
        # Menu
        # --------------------------------------------------------------
        if self.show_menu:
            menu_rect = self.menu_panel_rect()

            if not menu_rect.collidepoint(pos):
                self.show_menu = False
                return

            item_h = DROPDOWN_ROW_H
            save_rect = pygame.Rect(menu_rect.x, menu_rect.y + 4, menu_rect.width, item_h)
            load_rect = pygame.Rect(menu_rect.x, menu_rect.y + 4 + item_h, menu_rect.width, item_h)
            help_rect = pygame.Rect(menu_rect.x, menu_rect.y + 4 + item_h * 2, menu_rect.width, item_h)

            if save_rect.collidepoint(pos):
                self.show_menu = False
                self.save_project()
                return

            if load_rect.collidepoint(pos):
                self.show_menu = False
                self.load_project()
                return

            if help_rect.collidepoint(pos):
                self.show_menu = False
                self.show_help = True
                self.help_scroll = 0
                return

            return

        # --------------------------------------------------------------
        # Dropdown panels
        # --------------------------------------------------------------
        if self.show_tracks_dropdown:
            panel = self.tracks_panel_rect()

            # ----------------------------------------------------------
            # DRUM SUBMENU
            # ----------------------------------------------------------
            if self.hovered_drum_track is not None:
                drum_track = self.tracks[self.hovered_drum_track]

                parts = list(drum_track.parts.keys())

                row_y = (
                        panel.y
                        + 4
                        + self.hovered_drum_track * DROPDOWN_ROW_H
                )

                submenu_x = panel.right + 2
                submenu_y = row_y

                submenu_w = 130
                submenu_h = len(parts) * DROPDOWN_ROW_H + 8

                if submenu_x + submenu_w > self.viewport_w:
                    submenu_x = panel.x - submenu_w - 2

                if submenu_y + submenu_h > self.viewport_h:
                    submenu_y = self.viewport_h - submenu_h - 4

                drum_submenu = pygame.Rect(
                    submenu_x,
                    submenu_y,
                    submenu_w,
                    submenu_h
                )

                if drum_submenu.collidepoint(pos):
                    for j, part in enumerate(parts):
                        part_rect = pygame.Rect(
                            submenu_x + 4,
                            submenu_y + 4 + j * DROPDOWN_ROW_H,
                            submenu_w - 8,
                            DROPDOWN_ROW_H
                        )

                        if part_rect.collidepoint(pos):
                            if button == 1:
                                drum_track.current_part = part
                                self.current_track_index = self.hovered_drum_track
                                self.selected_notes = set()
                                self.show_tracks_dropdown = False
                                self.hovered_drum_track = None
                                self.update_toolbar_labels()
                                return

                    return

            # ----------------------------------------------------------
            # MAIN TRACK DROPDOWN
            # ----------------------------------------------------------
            if not panel.collidepoint(pos):
                self.show_tracks_dropdown = False
                self.hovered_drum_track = None
            else:
                row_y = panel.y + 4

                for i, track in enumerate(self.tracks):
                    row_rect = pygame.Rect(
                        panel.x + 4,
                        row_y + i * DROPDOWN_ROW_H,
                        panel.w - 8,
                        DROPDOWN_ROW_H
                    )

                    if row_rect.collidepoint(pos):
                        if button == 3:
                            self.track_context_menu = {
                                "index": i,
                                "pos": pos
                            }
                            return

                        # Drums opens its submenu instead of immediately
                        # selecting a different drum part.
                        if getattr(track, "is_drum_track", False):
                            self.hovered_drum_track = i
                            return

                        self.current_track_index = i
                        self.selected_notes = set()
                        self.show_tracks_dropdown = False
                        self.hovered_instrument_category = None
                        self.update_toolbar_labels()
                        return

            return

        if self.show_instr_dropdown:
            panel = self.instr_panel_rect()
            subpanel = self.instr_subpanel_rect()
            if self.hovered_instrument_category is not None and subpanel.collidepoint(pos):
                sounds = INSTRUMENTS[self.hovered_instrument_category]

                for i, sound in enumerate(sounds):
                    row_rect = pygame.Rect(
                        subpanel.x + 4,
                        subpanel.y + 4 + i * DROPDOWN_ROW_H,
                        subpanel.w - 8,
                        DROPDOWN_ROW_H
                    )

                    if row_rect.collidepoint(pos):
                        self.track.instrument = self.hovered_instrument_category
                        self.track.sound = sound
                        self.show_instr_dropdown = False
                        self.hovered_instrument_category = None
                        self.update_toolbar_labels()
                        return

            if panel.collidepoint(pos):
                categories = list(INSTRUMENTS)

                for i, category in enumerate(categories):
                    row_rect = pygame.Rect(
                        panel.x + 4,
                        panel.y + 4 + i * DROPDOWN_ROW_H,
                        panel.w - 8,
                        DROPDOWN_ROW_H
                    )

                    if row_rect.collidepoint(pos):
                        self.hovered_instrument_category = category
                        return

            self.show_instr_dropdown = False
            self.hovered_instrument_category = None
            return

        # --------------------------------------------------------------
        # Toolbar
        # --------------------------------------------------------------
        if self.btn_play.contains(pos):
            self.btn_play.flash()
            self.toggle_play()
            return

        if self.btn_stop.contains(pos):
            self.btn_stop.flash()
            self.stop_playback()
            return

        if self.btn_bpm_down.contains(pos):
            self.btn_bpm_down.flash()
            self.bpm = max(20, self.bpm - 1)
            return

        if self.bpm_box.collidepoint(pos):
            self.editing_bpm = True
            self.bpm_input_str = str(self.bpm)
            return

        if self.btn_bpm_up.contains(pos):
            self.btn_bpm_up.flash()
            self.bpm = min(300, self.bpm + 1)
            return

        if self.btn_tracks.contains(pos):
            self.btn_tracks.flash()
            self.show_tracks_dropdown = not self.show_tracks_dropdown
            self.show_instr_dropdown = False
            self.hovered_instrument_category = None
            return

        if self.btn_instr.contains(pos):
            self.btn_instr.flash()
            self.show_instr_dropdown = not self.show_instr_dropdown
            self.show_tracks_dropdown = False
            self.hovered_instrument_category = None
            return

        if self.btn_menu.contains(pos):
            self.btn_menu.flash()
            self.show_menu = not self.show_menu
            self.close_dropdowns()
            return

        # --------------------------------------------------------------
        # BPM / toolbar area
        # --------------------------------------------------------------
        if pos[1] < GRID_Y:
            return

        # --------------------------------------------------------------
        # Piano keyboard
        # --------------------------------------------------------------
        if pos[0] < KEY_AREA_WIDTH:
            row = self.screen_y_to_row(pos[1])

            if 0 <= row < TOTAL_ROWS:
                pitch = row_to_pitch(row)

                if button == 1:
                    self.preview_pitch = pitch
                    self.preview_grid_note(pitch)

                return

        # --------------------------------------------------------------
        # Piano-roll grid
        # --------------------------------------------------------------
        row = self.screen_y_to_row(pos[1])

        if not (0 <= row < TOTAL_ROWS):
            return

        pitch = row_to_pitch(row)
        step_float = self.screen_x_to_step(pos[0])

        if button == 1:
            mods = pygame.key.get_mods()

            if mods & pygame.KMOD_SHIFT:
                self.marquee = {"start": pos, "current": pos}
                return

            note, region = self.hit_test_note(pitch, pos[0])

            if note is not None:
                npitch, nstart, nlen = note

                if region == "left":
                    if note in self.selected_notes and len(self.selected_notes) > 1:
                        selected_orig = list(self.selected_notes)
                    else:
                        self.selected_notes = {note}
                        selected_orig = [note]

                    self.resizing = {
                        "edge": "left",
                        "mouse_x_start": pos[0],
                        "selected_orig": selected_orig,
                        "current_delta_steps": 0,
                        "current_notes": list(selected_orig),
                        "valid": True,
                    }

                elif region == "right":
                    if note in self.selected_notes and len(self.selected_notes) > 1:
                        selected_orig = list(self.selected_notes)
                    else:
                        self.selected_notes = {note}
                        selected_orig = [note]

                    self.resizing = {
                        "edge": "right",
                        "mouse_x_start": pos[0],
                        "selected_orig": selected_orig,
                        "current_delta_steps": 0,
                        "current_notes": list(selected_orig),
                        "valid": True,
                    }

                else:
                    # Normal click selects only the clicked note.
                    # Shift + marquee is still used for multi-selection.
                    if note not in self.selected_notes:
                        self.selected_notes = {note}

                    self.moving = {
                        "note": note,
                        "orig": note,
                        "mouse_x_start": pos[0],
                        "mouse_y_start": pos[1],
                        "selected_orig": list(self.selected_notes),
                        "current_delta_steps": 0,
                        "current_delta_rows": 0,
                        "valid": True,
                    }

                self.preview_grid_note(pitch)
                return

            # Empty cell = create a note, auto-shrunk to not overlap neighbors.
            step = int(round(step_float))
            step = max(0, min(self.total_steps - 1, step))
            self.selected_notes = set()
            self.add_note(pitch, step)
            return

        if button == 3:
            self.erasing = True
            self.save_undo_state()

            # Right-clicking a note erases it.
            # Right-clicking empty space deselects everything.
            row = self.screen_y_to_row(pos[1])

            if 0 <= row < TOTAL_ROWS and pos[0] >= KEY_AREA_WIDTH:
                pitch = row_to_pitch(row)
                step = int(self.screen_x_to_step(pos[0]))
                note = self.note_at(pitch, step)

                if note is not None:
                    if getattr(self.track, "is_drum_track", False):
                        self.track.parts[
                            self.track.current_part
                        ].discard(note)
                    else:
                        self.get_current_notes().discard(note)

                    self.selected_notes.discard(note)
                else:
                    self.selected_notes.clear()

            else:
                self.selected_notes.clear()

            return

    def handle_mouse_up(self, pos, button):
        if button == 1:
            if self.dragging_slider is not None:
                self.dragging_slider = None

            if self.marquee is not None:
                self.finish_marquee()

            if self.resizing is not None:
                self.commit_resize()
                self.resizing = None

            if self.moving is not None:
                self.commit_move()
                self.moving = None

            if self.preview_pitch is not None:
                self.engine.note_off(self.preview_pitch)
                self.preview_pitch = None

        elif button == 3:
            self.erasing = False

    def commit_resize(self):
        r = self.resizing

        if not r["valid"]:
            # Restore the original notes if the resize was invalid.
            return

        selected_orig = r["selected_orig"]
        current_notes = r["current_notes"]

        # Nothing changed
        if current_notes == selected_orig:
            return

        # Remove all original notes
        for note in selected_orig:
            self.get_current_notes().discard(note)
            self.selected_notes.discard(note)

        # Add the resized notes
        for note in current_notes:
            self.get_current_notes().add(note)
            self.selected_notes.add(note)

    # ------------------------------------------------------------------
    # Marquee (rubber-band) selection
    # ------------------------------------------------------------------

    def finish_marquee(self):
        if self.marquee is None:
            return

        x0, y0 = self.marquee["start"]
        x1, y1 = self.marquee["current"]
        left, right = sorted((x0, x1))
        top, bottom = sorted((y0, y1))

        step_a = self.screen_x_to_step(left)
        step_b = self.screen_x_to_step(right)
        row_a = self.screen_y_to_row(top)
        row_b = self.screen_y_to_row(bottom)
        pitch_hi = row_to_pitch(row_a)
        pitch_lo = row_to_pitch(row_b)

        selected = set()
        for n in self.get_current_notes():
            npitch, nstart, nlen = n
            if pitch_lo <= npitch <= pitch_hi and nstart < step_b and nstart + nlen > step_a:
                selected.add(n)

        self.selected_notes = selected
        self.marquee = None

    # ------------------------------------------------------------------
    # Note audition
    # ------------------------------------------------------------------

    def _stop_preview(self):
        if self.preview_pitch is not None:
            self.engine.note_off(self.preview_pitch)
            self.preview_pitch = None

        if self.grid_preview_pitch is not None:
            self.engine.note_off(self.grid_preview_pitch)
            self.grid_preview_pitch = None

    def preview_grid_note(self, pitch, duration_ms=260):
        # ----------------------------------------------------------
        # DRUM TRACK
        # ----------------------------------------------------------
        if getattr(self.track, "is_drum_track", False):
            self.track.engine.play_drum(
                self.track.current_part,
                pitch=pitch,
                velocity=100
            )
            return

        # ----------------------------------------------------------
        # NORMAL PIANO / SYNTH TRACK
        # ----------------------------------------------------------

        if self.grid_preview_pitch == pitch:
            self.grid_preview_release_at = (
                    pygame.time.get_ticks() + duration_ms
            )
            return

        if self.grid_preview_pitch is not None:
            self.engine.note_off(
                self.grid_preview_pitch
            )

        self.engine.note_on(
            pitch,
            velocity=100
        )

        self.grid_preview_pitch = pitch

        self.grid_preview_release_at = (
                pygame.time.get_ticks() + duration_ms
        )

    def update_previews(self):
        if self.grid_preview_pitch is not None and pygame.time.get_ticks() >= self.grid_preview_release_at:
            self.engine.note_off(self.grid_preview_pitch)
            self.grid_preview_pitch = None

    # ------------------------------------------------------------------
    # Dragging
    # ------------------------------------------------------------------

    def handle_mouse_motion(self, pos):
        x, y = pos

        if self.dragging_slider is not None:
            self.update_slider_from_mouse(pos)
            return

        if self.marquee is not None:
            self.marquee["current"] = pos
            return

        if self.show_instr_dropdown:
            panel = self.instr_panel_rect()
            if panel.collidepoint(pos):
                rel_y = pos[1] - panel.y - 4
                idx = rel_y // DROPDOWN_ROW_H
                categories = list(INSTRUMENTS)
                if 0 <= idx < len(categories):
                    self.hovered_instrument_category = categories[idx]
                    return
            elif self.instr_subpanel_rect().collidepoint(pos):
                return

        # --------------------------------------------------------------
        # Drum track hover
        # --------------------------------------------------------------
        if self.show_tracks_dropdown:
            panel = self.tracks_panel_rect()

            # Find the drum track.
            drum_index = None

            for i, track in enumerate(self.tracks):
                if getattr(track, "is_drum_track", False):
                    drum_index = i
                    break

            if drum_index is not None:
                row_y = (
                        panel.y
                        + 4
                        + drum_index * DROPDOWN_ROW_H
                )

                submenu_x = panel.right + 2
                submenu_y = row_y

                parts = list(self.drum_track.parts.keys())

                submenu_w = 130
                submenu_h = len(parts) * DROPDOWN_ROW_H + 8

                if submenu_x + submenu_w > self.viewport_w:
                    submenu_x = panel.x - submenu_w - 2

                if submenu_y + submenu_h > self.viewport_h:
                    submenu_y = self.viewport_h - submenu_h - 4

                drum_submenu = pygame.Rect(
                    submenu_x,
                    submenu_y,
                    submenu_w,
                    submenu_h
                )

                # Hovering the Drums row.
                drum_row = pygame.Rect(
                    panel.x + 4,
                    row_y,
                    panel.w - 8,
                    DROPDOWN_ROW_H
                )

                if drum_row.collidepoint(pos):
                    self.hovered_drum_track = drum_index

                # Hovering the submenu keeps it open.
                elif drum_submenu.collidepoint(pos):
                    self.hovered_drum_track = drum_index

                # Anywhere else closes it.
                else:
                    self.hovered_drum_track = None

            else:
                self.hovered_drum_track = None

        else:
            self.hovered_drum_track = None

        if self.resizing is not None:
            r = self.resizing

            dx = x - r["mouse_x_start"]
            delta_steps = round(dx / self.step_width)

            selected_orig = r["selected_orig"]
            edge = r["edge"]

            valid = True
            new_notes = []

            # ----------------------------------------------------------
            # Calculate the resized version of every selected note
            # ----------------------------------------------------------
            for pitch, start, length in selected_orig:

                if edge == "right":
                    new_length = length + delta_steps

                    # Minimum length of 1 step
                    new_length = max(1, new_length)

                    # Don't extend past the end of the piano roll
                    new_length = min(
                        new_length,
                        self.total_steps - start
                    )

                    new_note = (
                        pitch,
                        start,
                        new_length
                    )

                else:
                    # Keep the right edge fixed while moving the left edge
                    right_edge = start + length

                    new_start = start + delta_steps

                    # Minimum length of 1 step
                    new_start = min(
                        new_start,
                        right_edge - 1
                    )

                    # Don't go before the beginning
                    new_start = max(0, new_start)

                    new_length = right_edge - new_start

                    new_note = (
                        pitch,
                        new_start,
                        new_length
                    )

                new_notes.append(new_note)

            # ----------------------------------------------------------
            # Check for collisions with non-selected notes
            # ----------------------------------------------------------
            selected_set = set(selected_orig)

            for pitch, start, length in new_notes:
                if self.overlaps(
                        pitch,
                        start,
                        length,
                        exclude=selected_set
                ):
                    valid = False
                    break

            r["current_delta_steps"] = delta_steps
            r["current_notes"] = new_notes
            r["valid"] = valid

            return

        if self.moving is not None:
            m = self.moving
            snap = self.current_snap_steps()

            dx = x - m["mouse_x_start"]
            dy = y - m["mouse_y_start"]

            delta_steps = round(dx / self.step_width / snap) * snap
            delta_rows = round(dy / ROW_HEIGHT)

            selected_orig = m["selected_orig"]

            # ----------------------------------------------------------
            # Keep the entire selection inside the piano roll
            # ----------------------------------------------------------
            min_start = min(note[1] for note in selected_orig)
            max_end = max(note[1] + note[2] for note in selected_orig)

            if min_start + delta_steps < 0:
                delta_steps = -min_start

            if max_end + delta_steps > self.total_steps:
                delta_steps = self.total_steps - max_end

            # ----------------------------------------------------------
            # Keep the entire selection inside the pitch range
            # ----------------------------------------------------------
            min_pitch = min(note[0] for note in selected_orig)
            max_pitch = max(note[0] for note in selected_orig)

            if max_pitch - delta_rows > MAX_NOTE:
                delta_rows = max_pitch - MAX_NOTE

            if min_pitch - delta_rows < MIN_NOTE:
                delta_rows = min_pitch - MIN_NOTE

            # ----------------------------------------------------------
            # Check for collisions with notes that aren't selected
            # ----------------------------------------------------------
            valid = True
            selected_set = set(selected_orig)

            for pitch, start, length in selected_orig:
                new_pitch = pitch - delta_rows
                new_start = start + delta_steps

                if self.overlaps(
                        new_pitch,
                        new_start,
                        length,
                        exclude=selected_set
                ):
                    valid = False
                    break

            # ----------------------------------------------------------
            # Store movement information
            # ----------------------------------------------------------
            m["current_delta_steps"] = delta_steps
            m["current_delta_rows"] = delta_rows
            m["valid"] = valid

            # Keep "current" for the existing drawing code.
            # This represents the note that was originally clicked.
            orig_note = m["note"]

            new_pitch = orig_note[0] - delta_rows
            new_start = orig_note[1] + delta_steps
            new_length = orig_note[2]

            m["current"] = (new_pitch, new_start, new_length)

            # Preview the pitch when moving vertically.
            if delta_rows != m.get("last_preview_delta_rows", 0):
                self.preview_grid_note(new_pitch)
                m["last_preview_delta_rows"] = delta_rows

            return

        if self.erasing and y >= GRID_Y and x >= KEY_AREA_WIDTH:
            row = self.screen_y_to_row(y)
            pitch = row_to_pitch(row)
            step = int(self.screen_x_to_step(x))

            if MIN_NOTE <= pitch <= MAX_NOTE:
                existing = self.note_at(pitch, step)

                if existing is not None:
                    self.get_current_notes().discard(existing)
                    self.selected_notes.discard(existing)

    def update_cursor(self):
        if self.naming_track or self.show_track_settings:
            state = "arrow"
        elif self.resizing is not None:
            state = "resize"
        elif self.moving is not None:
            state = "move"
        else:
            state = "arrow"
            pos = pygame.mouse.get_pos()
            x, y = pos

            overlay_open = (
                self.show_help or self.show_tracks_dropdown or self.show_instr_dropdown
                or self.track_context_menu is not None
            )

            if y >= GRID_Y and x >= KEY_AREA_WIDTH and not overlay_open:
                row = self.screen_y_to_row(y)
                pitch = row_to_pitch(row)

                if MIN_NOTE <= pitch <= MAX_NOTE:
                    _, region = self.hit_test_note(pitch, x)
                    if region in ("left", "right"):
                        state = "resize"
                    elif region == "body":
                        state = "move"

        if state != self.cursor_state:
            self.cursor_state = state

            if state == "resize":
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_SIZEWE)
            elif state == "move":
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
            else:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)

    # ------------------------------------------------------------------
    # Note data
    # ------------------------------------------------------------------

    def hit_test_note(self, pitch, x):
        """
        Single source of truth for "what's under the cursor at this pitch
        row and x": a note's body, its left/right resize edge, or nothing.

        Both the cursor icon (update_cursor) and the actual click handler
        use this, so the resize arrow and the resize hitbox can never
        drift apart the way they could when each had its own hit-test.
        The edge zone is intentionally allowed to extend EDGE_GRAB_PX
        outside the note's visual bounds, not just inside — otherwise a
        cursor that shows the resize arrow just past the edge would click
        through to "add a new note" instead.
        """
        for n in self.get_current_notes():
            npitch, nstart, nlen = n
            if npitch != pitch:
                continue

            left_x = self.step_to_screen_x(nstart)
            right_x = self.step_to_screen_x(nstart + nlen)

            if left_x - EDGE_GRAB_PX <= x <= right_x + EDGE_GRAB_PX:
                if abs(x - left_x) <= EDGE_GRAB_PX:
                    return n, "left"
                if abs(x - right_x) <= EDGE_GRAB_PX:
                    return n, "right"
                if left_x < x < right_x:
                    return n, "body"

        return None, None

    def erase_note_at(self, pos):
        x, y = pos

        if y < GRID_Y or x < KEY_AREA_WIDTH:
            return

        row = self.screen_y_to_row(y)

        if not (0 <= row < TOTAL_ROWS):
            return

        pitch = row_to_pitch(row)
        step = int(self.screen_x_to_step(x))

        note = self.note_at(pitch, step)

        if note is not None:
            self.get_current_notes().discard(note)
            self.selected_notes.discard(note)

    def note_at(self, pitch, step):
        for n in self.get_current_notes():
            npitch, nstart, nlen = n
            if npitch == pitch and nstart <= step < nstart + nlen:
                return n
        return None

    def overlaps(self, pitch, start, length, exclude=None):
        for n in self.get_current_notes():
            if exclude is not None:
                if isinstance(exclude, set):
                    if n in exclude:
                        continue
                elif n == exclude:
                    continue

            npitch, nstart, nlen = n

            if npitch != pitch:
                continue

            if start < nstart + nlen and start + length > nstart:
                return True

        return False

    def add_note(self, pitch, step, audition=True):
        """
        Add a normal piano/synth note or a pitched drum note.

        Drum notes are stored in the currently selected drum part.
        Their MIDI pitch controls the drum sample's pitch.
        """

        step = max(0, min(step, self.total_steps - 1))

        # ----------------------------------------------------------
        # DRUM TRACK
        # ----------------------------------------------------------
        if getattr(self.track, "is_drum_track", False):

            part = self.track.current_part

            if part not in self.track.parts:
                return

            notes = self.track.parts[part]

            # Prevent two notes on the exact same pitch/step.
            for note in notes:
                npitch, nstart, nlen = note

                if npitch == pitch and nstart == step:
                    return

            self.save_undo_state()

            notes.add(
                (pitch, step, 1)
            )

            if audition:
                self.preview_grid_note(pitch)

            return

        # ----------------------------------------------------------
        # NORMAL PIANO / SYNTH TRACK
        # ----------------------------------------------------------

        max_length = min(
            DEFAULT_NOTE_LEN_STEPS,
            self.total_steps - step
        )

        for n in self.get_current_notes():
            npitch, nstart, nlen = n

            if npitch != pitch:
                continue

            if nstart <= step < nstart + nlen:
                return

            if nstart > step:
                max_length = min(
                    max_length,
                    nstart - step
                )

        length = max(1, max_length)

        if length <= 0:
            return

        self.save_undo_state()

        self.get_current_notes().add(
            (pitch, step, length)
        )

        if audition:
            self.preview_grid_note(pitch)

    def add_measure(self):
        if self.num_measures < MAX_MEASURES:
            self.num_measures += 1

    def remove_measure(self):
        if self.num_measures > MIN_MEASURES:
            new_total = (self.num_measures - 1) * STEPS_PER_MEASURE

            for t in self.tracks:
                t.notes = {n for n in t.notes if n[1] < new_total}

            self.selected_notes = {n for n in self.selected_notes if n[1] < new_total}
            self.num_measures -= 1
            self.scroll_x = min(self.scroll_x, self.max_scroll_x)

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def toggle_play(self):
        self.playing = not self.playing

        if self.playing:
            # Start the playback clock after the startup delay.
            self.playback_start_time = (
                    time.perf_counter() + self.playhead_delay
            )

            # Force step 0 to trigger when playback actually begins.
            self.last_playback_step = -1

            self.play_pos_seconds = 0.0
            self.playhead_visual_time = 0.0

        else:
            for t in self.tracks:
                t.engine.all_notes_off()

                if hasattr(t, "sounding"):
                    t.sounding.clear()

                if getattr(t, "is_drum_track", False):
                    t.playback_time = 0.0

    def stop_playback(self):
        self.playing = False
        self.play_pos_seconds = 0.0
        self.playhead_visual_time = 0.0

        for t in self.tracks:
            t.engine.all_notes_off()

            if hasattr(t, "sounding"):
                t.sounding.clear()

            if getattr(t, "is_drum_track", False):
                t.playback_time = 0.0

        self.last_playback_step = -1

    def update_playback(self, dt):
        if not self.playing:
            return

        step_len = self.seconds_per_step

        # ----------------------------------------------------------
        # AUTHORITATIVE PLAYBACK CLOCK
        # ----------------------------------------------------------
        now = time.perf_counter()

        playback_time = (
                now - self.playback_start_time
        )

        # Still inside the startup delay.
        if playback_time < 0:
            self.play_pos_seconds = 0.0
            self.playhead_visual_time = 0.0
            self.playhead_step = 0.0
            return

        # ----------------------------------------------------------
        # Current playback position
        # ----------------------------------------------------------
        self.play_pos_seconds = playback_time

        audio_time = playback_time + self.audio_lead

        cur_step = int(
            audio_time / step_len
        )

        # ----------------------------------------------------------
        # LOOP
        # ----------------------------------------------------------
        if playback_time >= self.total_steps * step_len:
            self.playback_start_time = (
                now
            )

            self.play_pos_seconds = 0.0
            self.playhead_visual_time = 0.0

            cur_step = 0
            self.last_playback_step = -1

            for t in self.tracks:
                t.engine.all_notes_off()

                if hasattr(t, "sounding"):
                    t.sounding.clear()

        # ----------------------------------------------------------
        # NEW STEP
        # ----------------------------------------------------------
        if cur_step != self.last_playback_step:

            # ------------------------------------------------------
            # Handle EVERY step that may have been crossed.
            #
            # This prevents notes from being skipped if a Pygame
            # frame takes longer than one 16th-note step.
            # ------------------------------------------------------
            first_step = self.last_playback_step + 1

            if self.last_playback_step == -1:
                first_step = 0

            for step in range(
                    first_step,
                    cur_step + 1
            ):

                # --------------------------------------------------
                # NORMAL TRACKS
                # --------------------------------------------------
                for t in self.tracks:

                    if getattr(
                            t,
                            "is_drum_track",
                            False
                    ):
                        continue

                    # Stop notes that ended on or before this step.
                    ended = [
                        k
                        for k, end in t.sounding.items()
                        if end <= step
                    ]

                    for k in ended:
                        t.engine.note_off(k[0])
                        del t.sounding[k]

                    # Start notes on this step.
                    for note in t.notes:
                        pitch, start, length = note

                        if start == step:
                            t.engine.note_on(
                                pitch,
                                velocity=100
                            )

                            t.sounding[note] = (
                                    start + length
                            )

                # --------------------------------------------------
                # DRUM TRACKS
                # --------------------------------------------------
                for t in self.tracks:

                    if not getattr(
                            t,
                            "is_drum_track",
                            False
                    ):
                        continue

                    for name, notes in t.parts.items():

                        for note in notes:
                            pitch, start, length = note

                            if start == step:
                                t.engine.play_drum(
                                    name,
                                    pitch=pitch,
                                    velocity=100
                                )

            self.last_playback_step = cur_step

        # ----------------------------------------------------------
        # PLAYHEAD POSITION
        # ----------------------------------------------------------
        self.playhead_step = (
                self.play_pos_seconds / step_len
        )

        # ----------------------------------------------------------
        # KEEP PLAYHEAD VISIBLE
        # ----------------------------------------------------------
        playhead_x = (
                self.step_to_screen_x(
                    self.playhead_step
                )
                + 1000
        )

        if (
                playhead_x < KEY_AREA_WIDTH
                or playhead_x > self.viewport_w - 150
        ):
            self.scroll_x = max(
                0,
                min(
                    self.playhead_step * self.step_width - 100,
                    self.max_scroll_x
                )
            )

    # ---------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw_toolbar(self):
        pygame.draw.rect(self.screen, TOOLBAR_COLOR, (0, 0, self.viewport_w, TOP_BAR_H))

        self.btn_play.draw(self.screen, self.font, active=self.playing)
        self.btn_stop.draw(self.screen, self.font)
        self.btn_bpm_down.draw(self.screen, self.font)
        self.btn_bpm_up.draw(self.screen, self.font)

        self.btn_tracks.draw(self.screen, self.font, active=self.show_tracks_dropdown, active_color=BTN_HELP_ACTIVE)
        self.btn_instr.draw(self.screen, self.font, active=self.show_instr_dropdown, active_color=BTN_HELP_ACTIVE)
        self.draw_gear_button()

        box_color = INPUT_BOX_EDITING if self.editing_bpm else INPUT_BOX_COLOR
        pygame.draw.rect(self.screen, box_color, self.bpm_box, border_radius=4)
        pygame.draw.rect(self.screen, (10, 10, 10), self.bpm_box, 1, border_radius=4)

        label = self.bpm_input_str if self.editing_bpm else f"{self.bpm}"
        num_text = self.font.render(label, True, TEXT_COLOR)
        suffix = self.font_small.render("BPM", True, MUTED_TEXT)

        self.screen.blit(num_text, (self.bpm_box.x + 6, self.bpm_box.y + (self.bpm_box.height - num_text.get_height()) // 2))
        self.screen.blit(suffix, (self.bpm_box.right - suffix.get_width() - 6, self.bpm_box.y + (self.bpm_box.height - suffix.get_height()) // 2))

        if self.editing_bpm and (pygame.time.get_ticks() // 500) % 2 == 0:
            caret_x = self.bpm_box.x + 6 + num_text.get_width()
            pygame.draw.line(self.screen, TEXT_COLOR, (caret_x, self.bpm_box.y + 5), (caret_x, self.bpm_box.bottom - 5), 2)

    def draw_drum_parts_dropdown(self):
        if self.hovered_drum_track is None:
            return

        # Find the drum track row.
        try:
            drum_index = next(
                i for i, t in enumerate(self.tracks)
                if getattr(t, "is_drum_track", False)
            )
        except StopIteration:
            return

        tracks_rect = self.tracks_panel_rect()

        row_y = (
                tracks_rect.y
                + 4
                + drum_index * DROPDOWN_ROW_H
        )

        # Submenu appears immediately to the right.
        panel_x = tracks_rect.right + 2
        panel_y = row_y

        parts = list(self.drum_track.parts.keys())

        panel_w = 130
        panel_h = len(parts) * DROPDOWN_ROW_H + 8

        # Keep submenu inside the window.
        if panel_x + panel_w > self.viewport_w:
            panel_x = tracks_rect.x - panel_w - 2

        if panel_y + panel_h > self.viewport_h:
            panel_y = self.viewport_h - panel_h - 4

        panel = pygame.Rect(
            panel_x,
            panel_y,
            panel_w,
            panel_h
        )

        pygame.draw.rect(
            self.screen,
            DROPDOWN_BG,
            panel,
            border_radius=4
        )

        pygame.draw.rect(
            self.screen,
            DROPDOWN_BORDER,
            panel,
            1,
            border_radius=4
        )

        mouse_pos = pygame.mouse.get_pos()

        for i, part in enumerate(parts):
            row_rect = pygame.Rect(
                panel.x + 4,
                panel.y + 4 + i * DROPDOWN_ROW_H,
                panel.width - 8,
                DROPDOWN_ROW_H
            )

            if part == self.drum_track.current_part:
                pygame.draw.rect(
                    self.screen,
                    DROPDOWN_SELECTED,
                    row_rect
                )
            elif row_rect.collidepoint(mouse_pos):
                pygame.draw.rect(
                    self.screen,
                    DROPDOWN_HOVER,
                    row_rect
                )

            label = self.font.render(
                part,
                True,
                TEXT_COLOR
            )

            self.screen.blit(
                label,
                (
                    row_rect.x + 6,
                    row_rect.y
                    + (row_rect.height - label.get_height()) // 2
                )
            )

    def draw_tracks_dropdown(self):
        if not self.show_tracks_dropdown:
            return

        rect = self.tracks_panel_rect()
        pygame.draw.rect(self.screen, DROPDOWN_BG, rect, border_radius=4)
        pygame.draw.rect(self.screen, DROPDOWN_BORDER, rect, 1, border_radius=4)

        mouse_pos = pygame.mouse.get_pos()

        for i, t in enumerate(self.tracks):
            row_rect = pygame.Rect(
                rect.x,
                rect.y + 4 + i * DROPDOWN_ROW_H,
                rect.width,
                DROPDOWN_ROW_H
            )

            if i == self.current_track_index:
                pygame.draw.rect(self.screen, DROPDOWN_SELECTED, row_rect)
            elif row_rect.collidepoint(mouse_pos):
                pygame.draw.rect(self.screen, DROPDOWN_HOVER, row_rect)

            label = self.font.render(t.name, True, TEXT_COLOR)
            self.screen.blit(
                label,
                (
                    row_rect.x + 8,
                    row_rect.y + (row_rect.height - label.get_height()) // 2
                )
            )

            # Drum tracks have a right-facing arrow.
            if getattr(t, "is_drum_track", False):
                arrow_x = row_rect.right - 14
                arrow_y = row_rect.centery

                pygame.draw.polygon(
                    self.screen,
                    MUTED_TEXT,
                    [
                        (arrow_x - 3, arrow_y - 5),
                        (arrow_x + 2, arrow_y),
                        (arrow_x - 3, arrow_y + 5),
                    ]
                )

        add_row = pygame.Rect(
            rect.x,
            rect.y + 4 + len(self.tracks) * DROPDOWN_ROW_H,
            rect.width,
            DROPDOWN_ROW_H
        )

        if add_row.collidepoint(mouse_pos):
            pygame.draw.rect(self.screen, DROPDOWN_HOVER, add_row)

        add_label = self.font.render(
            "+ Add track",
            True,
            (150, 210, 150)
        )

        self.screen.blit(
            add_label,
            (
                add_row.x + 8,
                add_row.y + (add_row.height - add_label.get_height()) // 2
            )
        )

        hint = self.font_small.render(
            "Right-click a track for settings / delete",
            True,
            MUTED_TEXT
        )

        self.screen.blit(
            hint,
            (rect.x + 6, rect.bottom + 2)
        )

    def draw_instr_dropdown(self):
        if not self.show_instr_dropdown:
            return

        rect = self.instr_panel_rect()
        pygame.draw.rect(self.screen, DROPDOWN_BG, rect, border_radius=4)
        pygame.draw.rect(self.screen, DROPDOWN_BORDER, rect, 1, border_radius=4)

        mouse_pos = pygame.mouse.get_pos()
        categories = list(INSTRUMENTS)

        for i, category in enumerate(categories):
            row_rect = pygame.Rect(rect.x, rect.y + 4 + i * DROPDOWN_ROW_H, rect.width, DROPDOWN_ROW_H)
            selected = self.track.instrument == category

            if selected:
                pygame.draw.rect(self.screen, DROPDOWN_SELECTED, row_rect)
            elif row_rect.collidepoint(mouse_pos):
                pygame.draw.rect(self.screen, DROPDOWN_HOVER, row_rect)

            label = self.font.render(category, True, TEXT_COLOR)
            self.screen.blit(label, (row_rect.x + 8, row_rect.y + (row_rect.height - label.get_height()) // 2))
            draw_arrow(self.screen, self.font_small, row_rect.right - 16, row_rect.y + 7, "right")

        if self.hovered_instrument_category is not None:
            self.draw_instr_submenu()

    def draw_instr_submenu(self):
        category = self.hovered_instrument_category
        if category is None:
            return

        rect = self.instr_subpanel_rect()
        pygame.draw.rect(self.screen, DROPDOWN_BG, rect, border_radius=4)
        pygame.draw.rect(self.screen, DROPDOWN_BORDER, rect, 1, border_radius=4)

        mouse_pos = pygame.mouse.get_pos()

        for i, sound in enumerate(INSTRUMENTS[category]):
            row_rect = pygame.Rect(rect.x, rect.y + 4 + i * DROPDOWN_ROW_H, rect.width, DROPDOWN_ROW_H)

            if self.track.sound == sound and self.track.instrument == category:
                pygame.draw.rect(self.screen, DROPDOWN_SELECTED, row_rect)
            elif row_rect.collidepoint(mouse_pos):
                pygame.draw.rect(self.screen, DROPDOWN_HOVER, row_rect)

            label = self.font.render(sound, True, TEXT_COLOR)
            self.screen.blit(label, (row_rect.x + 8, row_rect.y + (row_rect.height - label.get_height()) // 2))

    def draw_measure_labels(self):
        pygame.draw.rect(self.screen, LABEL_BG, (0, TOP_BAR_H, self.viewport_w, LABEL_H))

        first_step = int(self.scroll_x // self.step_width)
        last_step = first_step + int((self.viewport_w - KEY_AREA_WIDTH) / self.step_width) + 2

        for measure in range(0, self.num_measures, 4):
            step = measure * STEPS_PER_MEASURE

            if step < first_step - STEPS_PER_MEASURE or step > last_step:
                continue

            x = self.step_to_screen_x(step)
            label = self.font_small.render(str(measure + 1), True, MUTED_TEXT)
            self.screen.blit(label, (x + 4, TOP_BAR_H + 5))

        track_label = self.font_small.render(
            f"Editing: {self.track.name} — {self.track.instrument}: {self.track.sound}",
            True,
            MUTED_TEXT,
        )
        self.screen.blit(track_label, (self.viewport_w - track_label.get_width() - 10, TOP_BAR_H + 5))

    def draw_keyboard(self):
        first_row = self.scroll_y // ROW_HEIGHT
        last_row = first_row + (self.viewport_h - GRID_Y) // ROW_HEIGHT + 2

        for row in range(max(0, first_row), min(TOTAL_ROWS, last_row)):
            pitch = row_to_pitch(row)
            y = self.row_to_screen_y(row)
            pressed = pitch == self.preview_pitch

            if is_white_key(pitch):
                color = WHITE_KEY_PRESSED if pressed else WHITE_KEY_COLOR
            else:
                color = BLACK_KEY_PRESSED if pressed else BLACK_KEY_COLOR

            pygame.draw.rect(self.screen, color, (0, y, KEY_AREA_WIDTH, ROW_HEIGHT))
            pygame.draw.line(self.screen, (10, 10, 10), (0, y), (KEY_AREA_WIDTH, y))

            if pitch % 12 == 0:
                label = self.font_small.render(f"C{pitch // 12 - 1}", True, (120, 120, 120))
                self.screen.blit(label, (KEY_AREA_WIDTH - 28, y + 3))

    def draw_grid(self):
        grid_rect = pygame.Rect(KEY_AREA_WIDTH, GRID_Y, self.viewport_w - KEY_AREA_WIDTH, self.viewport_h - GRID_Y)
        pygame.draw.rect(self.screen, BG_COLOR, grid_rect)

        first_row = max(0, int(self.scroll_y // ROW_HEIGHT))
        last_row = min(TOTAL_ROWS - 1, int((self.scroll_y + self.viewport_h - GRID_Y) // ROW_HEIGHT) + 1)

        for row in range(first_row, last_row + 1):
            y = self.row_to_screen_y(row)
            if y < GRID_Y - ROW_HEIGHT or y > self.viewport_h:
                continue

            pitch = row_to_pitch(row)
            if not is_white_key(pitch):
                pygame.draw.rect(self.screen, ROW_ALT_COLOR, (KEY_AREA_WIDTH, int(y), self.viewport_w - KEY_AREA_WIDTH, ROW_HEIGHT))

            pygame.draw.line(self.screen, GRID_LINE, (KEY_AREA_WIDTH, int(y)), (self.viewport_w, int(y)), 1)

        visible_start_step = max(0, int(self.scroll_x / self.step_width) - 2)
        visible_end_step = min(self.total_steps, int((self.scroll_x + self.viewport_w - KEY_AREA_WIDTH) / self.step_width) + 2)

        if self.step_width < 5:
            grid_level = 0
        elif self.step_width < 12:
            grid_level = 1
        elif self.step_width < 24:
            grid_level = 2
        else:
            grid_level = 3

        for step in range(visible_start_step, visible_end_step + 1):
            x = self.step_to_screen_x(step)
            if x < KEY_AREA_WIDTH or x > self.viewport_w:
                continue

            if step % STEPS_PER_MEASURE == 0:
                pygame.draw.line(self.screen, MEASURE_LINE, (int(x), GRID_Y), (int(x), self.viewport_h), 2)
                continue

            if grid_level == 0:
                continue

            if step % STEPS_PER_BEAT == 0:
                pygame.draw.line(self.screen, BEAT_LINE, (int(x), GRID_Y), (int(x), self.viewport_h), 1)
                continue

            if grid_level >= 2 and step % 2 == 0:
                pygame.draw.line(self.screen, (58, 58, 65), (int(x), GRID_Y), (int(x), self.viewport_h), 1)
                continue

            if grid_level >= 3 and step % 2 != 0:
                pygame.draw.line(self.screen, (48, 48, 54), (int(x), GRID_Y), (int(x), self.viewport_h), 1)

        measure_width = self.step_width * STEPS_PER_MEASURE
        if measure_width > 0:
            first_measure = max(0, int(self.scroll_x / measure_width) - 1)
            last_measure = min(self.num_measures, int((self.scroll_x + self.viewport_w - KEY_AREA_WIDTH) / measure_width) + 2)

            for measure in range(first_measure, last_measure):
                step = measure * STEPS_PER_MEASURE
                x = self.step_to_screen_x(step)
                if x < KEY_AREA_WIDTH - 50 or x > self.viewport_w:
                    continue
                text = self.font_small.render(str(measure + 1), True, MUTED_TEXT)
                self.screen.blit(text, (int(x + 4), TOP_BAR_H + 4))

        for note in list(self.get_current_notes()):
            pitch, start, length = note
            is_selected = note in self.selected_notes

            # ----------------------------------------------------------
            # Moving notes
            # ----------------------------------------------------------
            if self.moving and note in self.moving["selected_orig"]:
                delta_steps = self.moving["current_delta_steps"]
                delta_rows = self.moving["current_delta_rows"]

                pitch = pitch - delta_rows
                start = start + delta_steps

            # ----------------------------------------------------------
            # Resizing notes
            # ----------------------------------------------------------
            if self.resizing and note in self.resizing["selected_orig"]:
                selected_orig = self.resizing["selected_orig"]
                current_notes = self.resizing.get("current_notes", [])

                try:
                    resize_index = selected_orig.index(note)
                    preview_note = current_notes[resize_index]

                    pitch, start, length = preview_note
                except (ValueError, IndexError):
                    pass

            row = pitch_to_row(pitch)
            y = self.row_to_screen_y(row)
            x1 = self.step_to_screen_x(start)
            x2 = self.step_to_screen_x(start + length)

            if x2 < KEY_AREA_WIDTH or x1 > self.viewport_w:
                continue
            if y + ROW_HEIGHT < GRID_Y or y > self.viewport_h:
                continue

            rect = pygame.Rect(
                int(x1),
                int(y + 1),
                max(2, int(x2 - x1)),
                max(2, ROW_HEIGHT - 2)
            )

            color = NOTE_COLOR
            border_color = NOTE_BORDER
            border_width = 1

            # Moving preview
            if self.moving and note in self.moving["selected_orig"]:
                color = NOTE_MOVING_COLOR
                border_color = NOTE_MOVING_BORDER

            # Resizing preview
            if self.resizing and note in self.resizing["selected_orig"]:
                color = NOTE_MOVING_COLOR
                border_color = NOTE_MOVING_BORDER

            if is_selected:
                border_color = NOTE_SELECTED_BORDER
                border_width = 2

            pygame.draw.rect(
                self.screen,
                color,
                rect,
                border_radius=3
            )

            pygame.draw.rect(
                self.screen,
                border_color,
                rect,
                border_width,
                border_radius=3
            )

            if self.step_width >= 12:
                handle_width = min(3, rect.width)

                pygame.draw.rect(
                    self.screen,
                    NOTE_EDGE_HANDLE,
                    (rect.left, rect.top, handle_width, rect.height)
                )

                pygame.draw.rect(
                    self.screen,
                    NOTE_EDGE_HANDLE,
                    (
                        max(rect.left, rect.right - handle_width),
                        rect.top,
                        handle_width,
                        rect.height
                    )
                )

        if self.marquee is not None:
            x0, y0 = self.marquee["start"]
            x1, y1 = self.marquee["current"]
            mrect = pygame.Rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
            overlay = pygame.Surface((max(1, mrect.width), max(1, mrect.height)), pygame.SRCALPHA)
            overlay.fill(MARQUEE_FILL)
            self.screen.blit(overlay, (mrect.x, mrect.y))
            pygame.draw.rect(self.screen, MARQUEE_BORDER, mrect, 1)

        if self.playing or self.play_pos_seconds > 0:
            if self.playing and self.playhead_visual_time < self.playhead_delay:
                return

            current_step = (
                self.playhead_step
                if self.playing
                else self.play_pos_seconds / self.seconds_per_step
            )

            x = self.step_to_screen_x(current_step)

            if KEY_AREA_WIDTH <= x <= self.viewport_w:
                pygame.draw.line(
                    self.screen,
                    PLAYHEAD_COLOR,
                    (int(x), GRID_Y),
                    (int(x), self.viewport_h),
                    2
                )

    # ------------------------------------------------------------------
    # Popup drawing
    # ------------------------------------------------------------------

    def menu_panel_rect(self):
        return pygame.Rect(self.viewport_w - 158, TOP_BAR_H, MENU_PANEL_W, DROPDOWN_ROW_H * 3 + 8)

    def draw_track_naming(self):
        if not self.naming_track:
            return

        overlay = pygame.Surface((self.viewport_w, self.viewport_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 145))
        self.screen.blit(overlay, (0, 0))

        panel_w = 420
        panel_h = 190
        panel = pygame.Rect((self.viewport_w - panel_w) // 2, (self.viewport_h - panel_h) // 2, panel_w, panel_h)

        pygame.draw.rect(self.screen, MODAL_BG, panel, border_radius=8)
        pygame.draw.rect(self.screen, MODAL_BORDER, panel, 1, border_radius=8)

        title = self.font_title.render("New Track", True, TEXT_COLOR)
        self.screen.blit(title, (panel.x + 35, panel.y + 22))

        input_rect = pygame.Rect(panel.x + 35, panel.y + 70, panel.w - 70, 38)
        input_color = INPUT_BOX_EDITING if self.track_name_focused else INPUT_BOX_COLOR
        pygame.draw.rect(self.screen, input_color, input_rect, border_radius=4)
        pygame.draw.rect(self.screen, NOTE_BORDER if self.track_name_focused else MODAL_BORDER, input_rect, 1, border_radius=4)

        if self.track_name_input:
            text_surface = self.font.render(self.track_name_input, True, TEXT_COLOR)
            self.screen.blit(text_surface, (input_rect.x + 10, input_rect.y + (input_rect.height - text_surface.get_height()) // 2))
        elif not self.track_name_focused:
            placeholder = self.font.render("Type a track name", True, MUTED_TEXT)
            self.screen.blit(placeholder, (input_rect.x + 10, input_rect.y + (input_rect.height - placeholder.get_height()) // 2))

        if self.track_name_focused and (pygame.time.get_ticks() // 500) % 2 == 0:
            if self.track_name_input:
                cursor_text = self.font.render(self.track_name_input, True, TEXT_COLOR)
                cursor_x = input_rect.x + 10 + cursor_text.get_width()
            else:
                cursor_x = input_rect.x + 10
            pygame.draw.line(self.screen, TEXT_COLOR, (cursor_x, input_rect.y + 7), (cursor_x, input_rect.bottom - 7), 2)

        add_rect = pygame.Rect(panel.x + 35, panel.bottom - 55, 120, 35)
        cancel_rect = pygame.Rect(panel.right - 155, panel.bottom - 55, 120, 35)

        add_color = ADD_BUTTON_COLOR if self.track_name_focused else BTN_COLOR
        pygame.draw.rect(self.screen, add_color, add_rect, border_radius=4)
        pygame.draw.rect(self.screen, (10, 10, 10), add_rect, 1, border_radius=4)
        add_text = self.font.render("Add", True, TEXT_COLOR)
        self.screen.blit(add_text, (add_rect.centerx - add_text.get_width() // 2, add_rect.centery - add_text.get_height() // 2))

        pygame.draw.rect(self.screen, BTN_COLOR, cancel_rect, border_radius=4)
        pygame.draw.rect(self.screen, (10, 10, 10), cancel_rect, 1, border_radius=4)
        cancel_text = self.font.render("Cancel", True, TEXT_COLOR)
        self.screen.blit(cancel_text, (cancel_rect.centerx - cancel_text.get_width() // 2, cancel_rect.centery - cancel_text.get_height() // 2))

    def draw_menu_dropdown(self):
        if not self.show_menu:
            return

        rect = self.menu_panel_rect()
        pygame.draw.rect(self.screen, DROPDOWN_BG, rect, border_radius=4)
        pygame.draw.rect(self.screen, DROPDOWN_BORDER, rect, 1, border_radius=4)

        labels = ["Save", "Load", "Help"]
        mouse = pygame.mouse.get_pos()

        for i, label in enumerate(labels):
            row = pygame.Rect(rect.x, rect.y + 4 + i * DROPDOWN_ROW_H, rect.width, DROPDOWN_ROW_H)
            if row.collidepoint(mouse):
                pygame.draw.rect(self.screen, DROPDOWN_HOVER, row)
            txt = self.font.render(label, True, TEXT_COLOR)
            self.screen.blit(txt, (row.x + 10, row.y + (row.height - txt.get_height()) // 2))

    def draw_help(self):
        if not self.show_help:
            return

        w = min(720, self.viewport_w - 60)
        h = min(460, self.viewport_h - 60)
        panel = pygame.Rect((self.viewport_w - w) // 2, (self.viewport_h - h) // 2, w, h)

        pygame.draw.rect(self.screen, HELP_BG, panel, border_radius=8)
        pygame.draw.rect(self.screen, HELP_BORDER, panel, 1, border_radius=8)

        title = self.font.render("Controls", True, TEXT_COLOR)
        self.screen.blit(title, (panel.x + 16, panel.y + 12))

        content_top = panel.y + 40
        content_h = panel.bottom - 16 - content_top
        line_h = 22
        total_content_h = len(HELP_LINES) * line_h
        max_scroll = max(0, total_content_h - content_h)
        self.help_scroll = max(0, min(self.help_scroll, max_scroll))

        clip = self.screen.get_clip()
        self.screen.set_clip(pygame.Rect(panel.x, content_top, panel.width, content_h))

        for i, line in enumerate(HELP_LINES):
            ly = content_top + i * line_h - self.help_scroll
            if ly < content_top - line_h or ly > content_top + content_h:
                continue
            text = self.font_small.render(line, True, MUTED_TEXT)
            self.screen.blit(text, (panel.x + 16, ly))

        self.screen.set_clip(clip)

        if max_scroll > 0:
            track_rect = pygame.Rect(panel.right - 14, content_top, 6, content_h)
            pygame.draw.rect(self.screen, (50, 50, 56), track_rect, border_radius=3)
            thumb_h = max(20, int(content_h * content_h / total_content_h))
            thumb_y = content_top + int((content_h - thumb_h) * (self.help_scroll / max_scroll))
            pygame.draw.rect(self.screen, (110, 110, 120), (track_rect.x, thumb_y, 6, thumb_h), border_radius=3)

    def draw_gear_button(self):
        rect = self.btn_menu.rect
        now = pygame.time.get_ticks()
        active = self.show_menu
        color = BTN_HELP_ACTIVE if active else BTN_COLOR

        if now < self.btn_menu.pressed_until:
            color = FLASH_COLOR

        pygame.draw.rect(self.screen, color, rect, border_radius=4)
        pygame.draw.rect(self.screen, (10, 10, 10), rect, 1, border_radius=4)

        cx, cy = rect.center
        tooth_color = TEXT_COLOR

        for i in range(8):
            angle = i * (np.pi / 4)
            x1 = cx + int(np.cos(angle) * 7)
            y1 = cy + int(np.sin(angle) * 7)
            x2 = cx + int(np.cos(angle) * 10)
            y2 = cy + int(np.sin(angle) * 10)
            pygame.draw.line(self.screen, tooth_color, (x1, y1), (x2, y2), 3)

        pygame.draw.circle(self.screen, tooth_color, (cx, cy), 7)
        pygame.draw.circle(self.screen, color, (cx, cy), 3)

    def draw(self):
        self.screen.fill(BG_COLOR)

        self.draw_grid()
        self.draw_keyboard()
        self.draw_measure_labels()
        self.draw_toolbar()
        self.draw_tracks_dropdown()
        self.draw_drum_parts_dropdown()
        self.draw_instr_dropdown()
        self.draw_menu_dropdown()
        self.draw_track_context_menu()
        self.draw_help()

        hint = "Space: play/pause   Right click: delete   Shift+drag: select   Ctrl+C/V: copy/paste"
        text = self.font_small.render(hint, True, MUTED_TEXT)
        self.screen.blit(text, (KEY_AREA_WIDTH + 4, self.viewport_h - 14))

        if self.status_message and pygame.time.get_ticks() < self.status_until:
            status = self.font_small.render(
                self.status_message, True,
                ERROR_COLOR if "failed" in self.status_message.lower() else MUTED_TEXT,
            )
            self.screen.blit(status, (self.viewport_w - status.get_width() - 10, self.viewport_h - 14))

        self.draw_track_naming()
        self.draw_track_settings()

        pygame.display.flip()

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

if __name__ == "__main__":
    PianoRollApp().run()
"""Layout / musical constants and static data tables.

Colors live in theme.py.
"""

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
MENU_PANEL_W = 150

MASTER_VOLUME_W = 110
MASTER_VOLUME_H = 18
MASTER_VOLUME_X_MARGIN = 62

TIME_SIGNATURES = [
            (2, 4),
            (3, 4),
            (4, 4),
            (5, 4),
            (6, 8),
            (7, 8),
            (9, 8),
            (12, 8),
        ]

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

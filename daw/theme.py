"""Color palette."""

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


def lighten(color, amount):
    """Move an RGB color toward white by `amount` (0..1)."""
    return tuple(int(c + (255 - c) * amount) for c in color)


def mix_color(a, b, amount):
    """Blend color a toward color b by `amount` (0 = a, 1 = b)."""
    return tuple(int(x + (y - x) * amount) for x, y in zip(a, b))


# Drum parts: one distinct color per part, used for notes and the sample panel.
DRUM_PART_COLORS = {
    "Kick": (70, 130, 235),         # blue
    "Snare": (240, 150, 50),        # orange
    "Closed Hat": (235, 210, 70),   # yellow
    "Open Hat": (170, 115, 230),    # purple
    "Crash": (80, 195, 115),        # green
    "Low Tom": (45, 185, 185),      # teal
    "High Tom": (225, 75, 75),      # red
}
DRUM_PART_BORDERS = {name: lighten(color, 0.35) for name, color in DRUM_PART_COLORS.items()}

DRUM_PANEL_BG = (28, 28, 32)
DRUM_ITEM_BG = (40, 40, 46)

# Colors used to tell tracks apart in "View All" mode.
TRACK_COLORS = [
    (90, 170, 230),
    (240, 150, 50),
    (80, 195, 115),
    (225, 75, 75),
    (170, 115, 230),
    (235, 210, 70),
    (45, 185, 185),
    (230, 120, 190),
]

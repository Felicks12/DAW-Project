"""Time-signature picker for the track settings popup.

Clicking the "4/4" box opens a list of signatures drawn ON TOP of the
popup. Picking one sets track.time_signature, which draw_grid already uses
for that track's bar lines.

This mixin must come first in PianoRollApp's bases because it wraps
handle_mouse_down, draw_track_settings and open_track_naming.
"""

import pygame

from .config import *
from .theme import *

TS_ROW_H = 22


class TimeSignatureMixin:
    def ts_box_rect(self):
        # Same rect that draw_track_settings uses for the "4/4" box.
        panel = self.track_settings_panel_rect()
        return pygame.Rect(panel.x + 300, panel.top + 45, 50, 25)

    def ts_row_rect(self, index):
        box = self.ts_box_rect()
        return pygame.Rect(box.x + 2, box.bottom + 4 + index * TS_ROW_H, box.width - 4, TS_ROW_H)

    def _ts_track(self):
        index = self.track_settings_index

        if self.show_track_settings and index is not None and 0 <= index < len(self.tracks):
            return self.tracks[index]

        return None

    def open_track_naming(self):
        # The track settings click handler (mouse_down.py) contains a stray
        # "+ Add track" hit-test copied from the Tracks dropdown. It used to
        # open the New Track dialog behind the settings popup. Ignore it
        # while the settings popup is open.
        if self.show_track_settings:
            return

        super().open_track_naming()

    def handle_mouse_down(self, pos, button):
        track = self._ts_track()

        if track is not None:
            # While the list is open every click is consumed here: a row
            # picks that signature, anything else just closes the list.
            if self.show_time_signature_dropdown:
                if button == 1:
                    for i, signature in enumerate(TIME_SIGNATURES):
                        if self.ts_row_rect(i).collidepoint(pos):
                            track.time_signature = signature
                            break

                self.show_time_signature_dropdown = False
                return

            if button == 1 and self.ts_box_rect().collidepoint(pos):
                self.show_time_signature_dropdown = True
                return

        super().handle_mouse_down(pos, button)

    def draw_track_settings(self):
        super().draw_track_settings()

        track = self._ts_track()

        if track is None:
            self.show_time_signature_dropdown = False
            return

        if not self.show_time_signature_dropdown:
            return

        box = self.ts_box_rect()
        panel = pygame.Rect(box.x, box.bottom + 2, box.width, len(TIME_SIGNATURES) * TS_ROW_H + 6)

        pygame.draw.rect(self.screen, DROPDOWN_BG, panel, border_radius=4)
        pygame.draw.rect(self.screen, DROPDOWN_BORDER, panel, 1, border_radius=4)

        mouse = pygame.mouse.get_pos()

        for i, (numerator, denominator) in enumerate(TIME_SIGNATURES):
            row = self.ts_row_rect(i)

            if (numerator, denominator) == tuple(track.time_signature):
                pygame.draw.rect(self.screen, DROPDOWN_SELECTED, row)
            elif row.collidepoint(mouse):
                pygame.draw.rect(self.screen, DROPDOWN_HOVER, row)

            label = self.font.render(f"{numerator}/{denominator}", True, TEXT_COLOR)
            self.screen.blit(
                label,
                (row.centerx - label.get_width() // 2, row.centery - label.get_height() // 2),
            )

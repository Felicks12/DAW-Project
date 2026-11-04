""""View All": show every track's notes at the same time.

The selected track is drawn normally and stays editable. All other tracks are
drawn as faded, color-coded notes behind it. Clicking a faded note switches
to that track.
"""

import pygame

from .config import *
from .theme import *


class ViewAllMixin:
    def toggle_view_all(self):
        self.view_all_tracks = not self.view_all_tracks

    def track_color(self, index):
        return TRACK_COLORS[index % len(TRACK_COLORS)]

    def _ghost_entries(self, index, track):
        """Yield (note, base_color) for one track."""
        if getattr(track, "is_drum_track", False):
            for part, notes in track.parts.items():
                color = DRUM_PART_COLORS.get(part, NOTE_COLOR)

                for note in notes:
                    yield note, color
        else:
            color = self.track_color(index)

            for note in track.notes:
                yield note, color

    def draw_ghost_notes(self):
        if not self.view_all_tracks:
            return

        for index, track in enumerate(self.tracks):
            if index == self.current_track_index:
                continue

            fade = 0.75 if getattr(track, "muted", False) else 0.55

            for (pitch, start, length), base in self._ghost_entries(index, track):
                x1 = self.step_to_screen_x(start)
                x2 = self.step_to_screen_x(start + length)

                if x2 < KEY_AREA_WIDTH or x1 > self.viewport_w:
                    continue

                y = self.row_to_screen_y(pitch_to_row(pitch))

                if y + ROW_HEIGHT < GRID_Y or y > self.viewport_h:
                    continue

                rect = pygame.Rect(int(x1), int(y + 3), max(2, int(x2 - x1)), ROW_HEIGHT - 6)
                pygame.draw.rect(self.screen, mix_color(base, BG_COLOR, fade), rect, border_radius=2)

    def ghost_note_at(self, pitch, step):
        """Find a note of another track at this cell -> (track_index, part or None)."""
        for index, track in enumerate(self.tracks):
            if index == self.current_track_index:
                continue

            if getattr(track, "is_drum_track", False):
                for part, notes in track.parts.items():
                    for note in notes:
                        if note[0] == pitch and note[1] <= step < note[1] + note[2]:
                            return index, part
            else:
                for note in track.notes:
                    if note[0] == pitch and note[1] <= step < note[1] + note[2]:
                        return index, None

        return None

    def _current_track_has_note(self, pitch, step):
        if getattr(self.track, "is_drum_track", False):
            return self.drum_note_at(pitch, step) is not None

        return self.note_at(pitch, step) is not None

    def draw_view_all_legend(self):
        x = KEY_AREA_WIDTH + 4
        y = self.viewport_h - 14

        label = self.font_small.render("All tracks:", True, MUTED_TEXT)
        self.screen.blit(label, (x, y))
        x += label.get_width() + 8

        for index, track in enumerate(self.tracks):
            current = index == self.current_track_index
            name = self.font_small.render(str(track.name), True, TEXT_COLOR if current else MUTED_TEXT)

            if x + name.get_width() + 20 > self.viewport_w - 200:
                break

            pygame.draw.rect(self.screen, self.track_color(index), (x, y + 2, 8, 8), border_radius=2)
            self.screen.blit(name, (x + 12, y))
            x += name.get_width() + 26

    def handle_mouse_down(self, pos, button):
        if button == 1 and not self.popup_open():
            if self.btn_view_all.contains(pos):
                self.btn_view_all.flash()
                self.toggle_view_all()
                return

            shift = pygame.key.get_mods() & pygame.KMOD_SHIFT

            if self.view_all_tracks and not shift and pos[0] >= KEY_AREA_WIDTH and pos[1] >= GRID_Y:
                row = self.screen_y_to_row(pos[1])

                if 0 <= row < TOTAL_ROWS:
                    pitch = row_to_pitch(row)
                    step = int(self.screen_x_to_step(pos[0]) // 1)

                    if not self._current_track_has_note(pitch, step):
                        hit = self.ghost_note_at(pitch, step)

                        if hit is not None:
                            index, part = hit
                            self.current_track_index = index

                            if part is not None:
                                self.tracks[index].current_part = part

                            self.selected_notes = set()
                            self.update_toolbar_labels()
                            return

        super().handle_mouse_down(pos, button)

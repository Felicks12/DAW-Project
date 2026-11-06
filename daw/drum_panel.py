"""Drum track UI.

When a drum track is selected the piano keys on the left are replaced by a
sample panel (sections: Kick, Snare, Hi-Hats, Cymbals, Toms). Samples can be
clicked (audition + select the part used for new notes) or dragged onto the
grid. All drum parts are shown together in the grid, each in its own color.
"""

import pygame

from .config import *
from .theme import *


def _content_height():
    height = 4

    for _, parts in DRUM_SECTIONS:
        height += DRUM_HEADER_H + len(parts) * DRUM_ITEM_H + 4

    return height


def _fit_text(font, text, max_width):
    if font.size(text)[0] <= max_width:
        return text

    while text and font.size(text + "...")[0] > max_width:
        text = text[:-1]

    return text + "..."


class DrumPanelMixin:

    def is_drum_selected(self):
        return getattr(self.track, "is_drum_track", False)

    def drawable_notes(self):
        """Yield (note, part). Drum tracks yield every part; others part=None."""
        track = self.track

        if getattr(track, "is_drum_track", False):
            for part, notes in track.parts.items():
                for note in list(notes):
                    yield note, part
        else:
            for note in list(self.get_current_notes()):
                yield note, None

    def drum_note_at(self, pitch, step):
        """Find a drum note (any part) covering this pitch/step -> (part, note)."""
        track = self.track
        order = [track.current_part] + [p for p in track.parts if p != track.current_part]

        for part in order:
            for note in track.parts[part]:
                if note[0] == pitch and note[1] <= step < note[1] + note[2]:
                    return part, note

        return None

    def _drum_cell(self, pos):
        """(pitch, step) of the grid cell under pos, or None."""
        if pos[0] < KEY_AREA_WIDTH or pos[1] < GRID_Y:
            return None

        row = self.screen_y_to_row(pos[1])

        if not (0 <= row < TOTAL_ROWS):
            return None

        step = int(self.screen_x_to_step(pos[0]) // 1)
        step = max(0, min(self.total_steps - 1, step))

        return row_to_pitch(row), step

    def drum_panel_rect(self):
        return pygame.Rect(0, GRID_Y, KEY_AREA_WIDTH, self.viewport_h - GRID_Y)

    def in_drum_panel(self, pos):
        return self.drum_panel_rect().collidepoint(pos)

    def drum_panel_max_scroll(self):
        return max(0, _content_height() - self.drum_panel_rect().height)

    def drum_panel_rows(self):
        """[(kind, label, part, rect)] for section headers and sample rows."""
        scroll = max(0, min(self.drum_panel_scroll, self.drum_panel_max_scroll()))
        self.drum_panel_scroll = scroll

        rows = []
        y = GRID_Y + 4 - scroll

        for section, parts in DRUM_SECTIONS:
            rows.append(("header", section, None, pygame.Rect(0, y, KEY_AREA_WIDTH, DRUM_HEADER_H)))
            y += DRUM_HEADER_H

            for part in parts:
                rows.append(("item", part, part, pygame.Rect(0, y, KEY_AREA_WIDTH, DRUM_ITEM_H)))
                y += DRUM_ITEM_H

            y += 4

        return rows

    def drum_panel_part_at(self, pos):
        for kind, _, part, rect in self.drum_panel_rows():
            if kind == "item" and rect.collidepoint(pos):
                return part

        return None

    def draw_keyboard(self):
        if self.is_drum_selected():
            self.draw_drum_panel()
        else:
            super().draw_keyboard()

    def draw_drum_panel(self):
        panel = self.drum_panel_rect()
        pygame.draw.rect(self.screen, DRUM_PANEL_BG, panel)

        clip = self.screen.get_clip()
        self.screen.set_clip(panel)

        mouse = pygame.mouse.get_pos()
        hover_enabled = not self.popup_open()

        for kind, label, part, rect in self.drum_panel_rows():
            if rect.bottom < panel.top or rect.top > panel.bottom:
                continue

            if kind == "header":
                text = self.font_small.render(label.upper(), True, MUTED_TEXT)
                self.screen.blit(text, (rect.x + 8, rect.y + (rect.height - text.get_height()) // 2))
                line_x = rect.x + 8 + text.get_width() + 6
                pygame.draw.line(self.screen, GRID_LINE, (line_x, rect.centery), (rect.right - 8, rect.centery))
                continue

            row = rect.inflate(-10, -4)
            selected = part == self.track.current_part

            if selected:
                background = DROPDOWN_SELECTED
            elif hover_enabled and row.collidepoint(mouse):
                background = DROPDOWN_HOVER
            else:
                background = DRUM_ITEM_BG

            pygame.draw.rect(self.screen, background, row, border_radius=4)

            stripe = pygame.Rect(row.x, row.y, 5, row.height)
            pygame.draw.rect(
                self.screen,
                DRUM_PART_COLORS[part],
                stripe,
                border_top_left_radius=4,
                border_bottom_left_radius=4,
            )

            if selected:
                pygame.draw.rect(self.screen, DRUM_PART_BORDERS[part], row, 1, border_radius=4)

            name = self.font.render(part, True, TEXT_COLOR)
            self.screen.blit(name, (row.x + 12, row.y + 1))

            source = _fit_text(self.font_small, self.track.sample_label(part), row.width - 18)
            tag = self.font_small.render(source, True, MUTED_TEXT)
            self.screen.blit(tag, (row.x + 12, row.bottom - tag.get_height() - 1))

        self.screen.set_clip(clip)
        pygame.draw.line(self.screen, (10, 10, 10), (panel.right - 1, panel.top), (panel.right - 1, panel.bottom))

    def draw_drum_drag(self):
        """Ghost note + label while a sample is being dragged."""
        drag = self.drum_drag

        if drag is None or not drag["moved"]:
            return

        part = drag["part"]
        color = DRUM_PART_COLORS[part]
        x, y = drag["pos"]

        cell = self._drum_cell((x, y))

        if cell is not None:
            pitch, step = cell
            x1 = self.step_to_screen_x(step)
            x2 = self.step_to_screen_x(step + 1)
            row_y = self.row_to_screen_y(pitch_to_row(pitch))

            ghost = pygame.Surface((max(4, int(x2 - x1)), ROW_HEIGHT - 2), pygame.SRCALPHA)
            ghost.fill((color[0], color[1], color[2], 170))
            self.screen.blit(ghost, (int(x1), int(row_y + 1)))

        label = self.font.render(part, True, (20, 20, 20))
        chip = pygame.Rect(x + 12, y + 8, label.get_width() + 14, label.get_height() + 6)
        pygame.draw.rect(self.screen, color, chip, border_radius=4)
        self.screen.blit(label, (chip.x + 7, chip.y + 3))

    def handle_mouse_down(self, pos, button):
        if self.is_drum_selected() and not self.popup_open():
            if self.in_drum_panel(pos):
                if button == 1:
                    part = self.drum_panel_part_at(pos)

                    if part is not None:
                        self.track.current_part = part
                        self.selected_notes = set()
                        self.track.engine.play_drum(part, pitch=60, velocity=100)
                        self.drum_drag = {"part": part, "start": pos, "pos": pos, "moved": False}

                return

            cell = self._drum_cell(pos)

            if cell is not None:
                hit = self.drum_note_at(cell[0], cell[1])

                if hit is not None:
                    part, note = hit

                    # Right click deletes a note of ANY drum part.
                    if button == 3:
                        self.erasing = True
                        self.save_undo_state()
                        self.track.parts[part].discard(note)
                        self.selected_notes.discard(note)
                        return

                    # Clicking a note of another part switches to that part so
                    # it can be selected / moved / resized like any other note.
                    shift = pygame.key.get_mods() & pygame.KMOD_SHIFT

                    if button == 1 and part != self.track.current_part and not shift:
                        self.track.current_part = part
                        self.selected_notes = set()

        super().handle_mouse_down(pos, button)

    def handle_mouse_up(self, pos, button):
        drag = self.drum_drag

        if drag is not None and button == 1:
            self.drum_drag = None

            if drag["moved"] and self.is_drum_selected() and not self.popup_open():
                cell = self._drum_cell(pos)

                if cell is not None:
                    self.track.current_part = drag["part"]
                    self.selected_notes = set()
                    self.add_note(cell[0], cell[1])

            return

        super().handle_mouse_up(pos, button)

    def handle_mouse_motion(self, pos):
        drag = self.drum_drag

        if drag is not None:
            drag["pos"] = pos

            if not drag["moved"]:
                dx = abs(pos[0] - drag["start"][0])
                dy = abs(pos[1] - drag["start"][1])

                if dx + dy > 5:
                    drag["moved"] = True

            return

        # Drag-erase across notes of any drum part.
        if self.erasing and self.is_drum_selected() and not self.popup_open():
            cell = self._drum_cell(pos)

            if cell is not None:
                hit = self.drum_note_at(cell[0], cell[1])

                if hit is not None:
                    part, note = hit
                    self.track.parts[part].discard(note)
                    self.selected_notes.discard(note)

            return

        super().handle_mouse_motion(pos)

    def handle_wheel(self, event):
        if self.is_drum_selected() and not self.popup_open():
            if self.in_drum_panel(pygame.mouse.get_pos()):
                scroll = self.drum_panel_scroll - event.y * 30
                self.drum_panel_scroll = max(0, min(scroll, self.drum_panel_max_scroll()))
                return

        super().handle_wheel(event)

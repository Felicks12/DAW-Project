"""Grid, keyboard, ruler, help overlay and the top-level draw() routine."""

import pygame

from .config import *
from .theme import *


class DrawingMixin:
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
            f"Editing: {self.track.name} - {self.track.instrument}: {self.track.sound}",
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

        is_drum = getattr(self.track, "is_drum_track", False)

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

            # The drum panel replaces the piano keys, so label the C rows here.
            if is_drum and pitch % 12 == 0:
                pitch_label = self.font_small.render(f"C{pitch // 12 - 1}", True, (95, 95, 105))
                self.screen.blit(pitch_label, (KEY_AREA_WIDTH + 4, int(y) + 3))

        current_track = self.tracks[self.current_track_index]
        steps_per_measure = self.get_track_steps_per_measure(current_track)

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

            if step % steps_per_measure == 0:
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

        # "View All": faded notes of the other tracks, behind the editable ones.
        self.draw_ghost_notes()

        active_part = self.track.current_part if is_drum else None

        for note, part in self.drawable_notes():
            pitch, start, length = note

            # Notes of a drum part other than the one being edited are shown
            # (in their own color) but are not part of the selection / drags.
            in_active = part is None or part == active_part
            is_selected = in_active and note in self.selected_notes
            is_moving = in_active and bool(self.moving) and note in self.moving["selected_orig"]
            is_resizing = in_active and bool(self.resizing) and note in self.resizing["selected_orig"]

            if is_moving:
                delta_steps = self.moving["current_delta_steps"]
                delta_rows = self.moving["current_delta_rows"]

                pitch = pitch - delta_rows
                start = start + delta_steps

            if is_resizing:
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

            if part is None:
                color = NOTE_COLOR
                border_color = NOTE_BORDER
            else:
                color = DRUM_PART_COLORS[part]
                border_color = DRUM_PART_BORDERS[part]

            border_width = 1

            # Moving / resizing preview
            if is_moving or is_resizing:
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

            # --- Playhead position ---
            current_step = (
                self.playhead_step
                if self.playing
                else self.play_pos_seconds / self.seconds_per_step
            )

            x = self.step_to_screen_x(current_step)

            if KEY_AREA_WIDTH <= x <= self.viewport_w:
                x = int(x)

                # Draw the vertical playhead line during playback,
                # or when the playhead has moved away from the start.
                if self.playing or self.play_pos_seconds > 0:
                    if not (
                            self.playing
                            and self.playhead_visual_time < self.playhead_delay
                    ):
                        pygame.draw.line(
                            self.screen,
                            PLAYHEAD_COLOR,
                            (x, GRID_Y),
                            (x, self.viewport_h),
                            2
                        )

                # Draw the white downward-pointing playhead marker in the ruler.
                marker_y = TOP_BAR_H + 2
                marker_points = [
                    (x - 7, marker_y),
                    (x + 7, marker_y),
                    (x, marker_y + 10),
                ]

                pygame.draw.polygon(
                    self.screen,
                    (255, 255, 255),
                    marker_points
                )
                pygame.draw.polygon(
                    self.screen,
                    (30, 30, 30),
                    marker_points,
                    1
                )

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

    def draw(self):
        self.screen.fill(BG_COLOR)

        self.draw_grid()
        self.draw_keyboard()
        self.draw_measure_labels()

        # Draw the playhead triangle on top of the ruler.
        marker_x = int(self.step_to_screen_x(self.playhead_step))
        marker_y = TOP_BAR_H + 2

        if KEY_AREA_WIDTH <= marker_x <= self.viewport_w:
            marker_points = [
                (marker_x - 7, marker_y),
                (marker_x + 7, marker_y),
                (marker_x, marker_y + 10),
            ]

            pygame.draw.polygon(
                self.screen,
                (255, 255, 255),
                marker_points
            )

            pygame.draw.polygon(
                self.screen,
                (25, 25, 25),
                marker_points,
                1
            )

        self.draw_toolbar()
        self.draw_tracks_dropdown()
        self.draw_instr_dropdown()
        self.draw_menu_dropdown()
        self.draw_track_context_menu()
        self.draw_drum_drag()
        self.draw_help()

        if self.view_all_tracks:
            self.draw_view_all_legend()
        else:
            hint = "Space: play/pause   Right click: delete   Shift+drag: select   Ctrl+C/V: copy/paste   Ctrl+Z: undo"
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

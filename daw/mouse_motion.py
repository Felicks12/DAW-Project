"""Mouse button-up, drag/motion handling and cursor icon."""

import pygame

from .config import *


class MouseMotionMixin:
    def handle_mouse_up(self, pos, button):
        if button == 1:
            self.dragging_master_volume = False
            self.dragging_playhead = False

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

    def handle_mouse_motion(self, pos):
        x, y = pos

        if self.dragging_playhead:
            self.set_playhead_from_mouse(x)
            return

        if self.dragging_master_volume:
            self.update_master_volume_from_mouse(pos)
            return

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

                parts = list(self.tracks[drum_index].parts.keys())

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

            min_start = min(note[1] for note in selected_orig)
            max_end = max(note[1] + note[2] for note in selected_orig)

            if min_start + delta_steps < 0:
                delta_steps = -min_start

            if max_end + delta_steps > self.total_steps:
                delta_steps = self.total_steps - max_end

            min_pitch = min(note[0] for note in selected_orig)
            max_pitch = max(note[0] for note in selected_orig)

            if max_pitch - delta_rows > MAX_NOTE:
                delta_rows = max_pitch - MAX_NOTE

            if min_pitch - delta_rows < MIN_NOTE:
                delta_rows = min_pitch - MIN_NOTE

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

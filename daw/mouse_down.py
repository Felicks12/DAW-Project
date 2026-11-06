"""Mouse button-down handling (popups, dropdowns, toolbar, keyboard, grid)."""

import pygame

from .config import *


class MouseDownMixin:
    def handle_mouse_down(self, pos, button):

        if self.naming_track:
            panel_w = 500
            panel_h = 260
            panel = pygame.Rect((self.viewport_w - panel_w) // 2, (self.viewport_h - panel_h) // 2, panel_w, panel_h)
            input_rect = pygame.Rect(panel.x + 30, panel.y + 62, panel.w - 60, 34)
            # Match the visible track-type buttons in draw_track_naming().
            # The previous hitboxes were vertically offset from the buttons.
            type_y = panel.y + 120
            type_w = (panel.w - 72) // 3
            type_rects = {
                "drum": pygame.Rect(panel.x + 30, type_y, type_w, 38),
                "instrument": pygame.Rect(panel.x + 36 + type_w, type_y, type_w, 38),
                "custom": pygame.Rect(panel.x + 42 + type_w * 2, type_y, type_w, 38),
            }
            add_rect = pygame.Rect(panel.x + 30, panel.bottom - 52, 120, 34)
            cancel_rect = pygame.Rect(panel.right - 150, panel.bottom - 52, 120, 34)

            if input_rect.collidepoint(pos):
                self.track_name_focused = True
                return

            for track_type, type_rect in type_rects.items():
                if type_rect.collidepoint(pos):
                    self.new_track_type = track_type
                    self.track_name_focused = False
                    return

            if add_rect.collidepoint(pos):
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

            add_row = pygame.Rect(
                panel.x,
                panel.y + 4 + len(self.tracks) * DROPDOWN_ROW_H,
                panel.width,
                DROPDOWN_ROW_H
            )

            if add_row.collidepoint(pos) and button == 1:
                self.open_track_naming()
                return

            return

        if self.track_context_menu is not None:
            self.handle_track_context_menu_click(pos)
            return

        if self.show_help:
            help_w = min(700, self.viewport_w - 80)
            help_h = min(500, self.viewport_h - 80)
            help_rect = pygame.Rect((self.viewport_w - help_w) // 2, (self.viewport_h - help_h) // 2, help_w, help_h)

            if not help_rect.collidepoint(pos):
                self.show_help = False

            return

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

        if self.show_tracks_dropdown:
            panel = self.tracks_panel_rect()

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

                add_row = pygame.Rect(
                    panel.x,
                    panel.y + 4 + len(self.tracks) * DROPDOWN_ROW_H,
                    panel.width,
                    DROPDOWN_ROW_H
                )

                if add_row.collidepoint(pos) and button == 1:
                    self.open_track_naming()
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

        if button == 1 and self.master_volume_slider_rect().collidepoint(pos):
            self.dragging_master_volume = True
            self.update_master_volume_from_mouse(pos)
            return

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

        if (
                button == 1
                and TOP_BAR_H <= pos[1] < GRID_Y
                and pos[0] >= KEY_AREA_WIDTH
        ):
            self.dragging_playhead = True
            self.set_playhead_from_mouse(pos[0])
            return

        if pos[1] < GRID_Y:
            return

        if pos[0] < KEY_AREA_WIDTH:
            row = self.screen_y_to_row(pos[1])

            if 0 <= row < TOTAL_ROWS:
                pitch = row_to_pitch(row)

                if button == 1:
                    self.preview_pitch = pitch
                    self.preview_grid_note(pitch)

                return

        if button == 1 and TOP_BAR_H <= pos[1] < GRID_Y:
            if pos[0] >= KEY_AREA_WIDTH:
                self.dragging_playhead = True
                self.set_playhead_from_mouse(pos[0])
                return

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

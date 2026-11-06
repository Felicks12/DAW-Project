"""Event pump, keyboard handling and mouse-wheel handling."""

import pygame

from .config import *


class EventsMixin:
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

    def handle_keydown(self, event):
        key = event.key

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

        if self.track_context_menu is not None:
            if key == pygame.K_ESCAPE:
                self.track_context_menu = None
            return

        if self.show_track_settings:
            if key == pygame.K_ESCAPE:
                self.show_track_settings = False
            return

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

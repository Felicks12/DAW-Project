""""New Track" naming popup and track creation."""

import pygame

from .config import *
from .theme import *
from .tracks import Track, DrumTrack


class TrackNamingMixin:
    def open_track_naming(self):
        self.close_dropdowns()
        self.naming_track = True
        self.track_name_input = ""
        self.track_name_focused = False
        self.new_track_type = "instrument"
        self._stop_preview()

    def get_unique_track_name(self, base_name):
        """Return a track name that does not already exist in the project."""
        base_name = base_name.strip() or "Track"
        existing_names = {str(track.name).casefold() for track in self.tracks}

        if base_name.casefold() not in existing_names:
            return base_name

        suffix = 1
        while f"{base_name} {suffix}".casefold() in existing_names:
            suffix += 1

        return f"{base_name} {suffix}"

    def commit_track_naming(self):
        name = self.track_name_input.strip()
        track_type = self.new_track_type

        if not name:
            if track_type == "drum":
                self.drumNUM += 1
                name = f"Drums {self.drumNUM}"
            elif track_type == "custom":
                self.customNUM += 1
                name = f"Custom {self.customNUM}"
            else:
                self.trackNUM += 1
                name = f"Track {self.trackNUM}"

        if track_type == "drum":
            new_track = DrumTrack(name=name)
        else:
            current_track = self.tracks[self.current_track_index] if self.tracks else None
            if current_track is None or getattr(current_track, "is_drum_track", False):
                waveform = "saw"
                instrument = "Piano"
                sound = "Grand Piano"
            else:
                waveform = getattr(current_track.engine, "waveform_name", "saw")
                instrument = current_track.instrument
                sound = current_track.sound

            new_track = Track(
                name=name,
                waveform=waveform,
                instrument=instrument,
                sound=sound,
                track_type="custom" if track_type == "custom" else "instrument",
            )

        self.tracks.append(new_track)
        if getattr(new_track, "is_drum_track", False) and self.drum_track is None:
            self.drum_track = new_track

        self.current_track_index = len(self.tracks) - 1
        self.selected_notes = set()
        self.naming_track = False
        self.track_name_input = ""
        self.track_name_focused = False
        self.update_toolbar_labels()

        name = self.get_unique_track_name(name)

    def draw_track_naming(self):
        if not self.naming_track:
            return

        overlay = pygame.Surface((self.viewport_w, self.viewport_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 145))
        self.screen.blit(overlay, (0, 0))

        panel_w = 500
        panel_h = 260
        panel = pygame.Rect((self.viewport_w - panel_w) // 2, (self.viewport_h - panel_h) // 2, panel_w, panel_h)

        pygame.draw.rect(self.screen, MODAL_BG, panel, border_radius=8)
        pygame.draw.rect(self.screen, MODAL_BORDER, panel, 1, border_radius=8)

        title = self.font_title.render("New Track", True, TEXT_COLOR)
        self.screen.blit(title, (panel.x + 30, panel.y + 18))

        input_rect = pygame.Rect(panel.x + 30, panel.y + 62, panel.w - 60, 34)
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
            pygame.draw.line(self.screen, TEXT_COLOR, (cursor_x, input_rect.y + 6), (cursor_x, input_rect.bottom - 6), 2)

        type_label = self.font_small.render("Track type", True, MUTED_TEXT)
        self.screen.blit(type_label, (panel.x + 30, panel.y + 102))
        type_y = panel.y + 120
        type_w = (panel.w - 72) // 3
        type_options = [
            ("drum", "Drum Track"),
            ("instrument", "Instrument Track"),
            ("custom", "Custom Track"),
        ]
        mouse_pos = pygame.mouse.get_pos()
        for index, (track_type, label) in enumerate(type_options):
            type_rect = pygame.Rect(panel.x + 30 + index * (type_w + 6), type_y, type_w, 38)
            selected = self.new_track_type == track_type
            if selected:
                color = BTN_ACTIVE
            elif type_rect.collidepoint(mouse_pos):
                color = DROPDOWN_HOVER
            else:
                color = BTN_COLOR
            pygame.draw.rect(self.screen, color, type_rect, border_radius=4)
            pygame.draw.rect(self.screen, NOTE_BORDER if selected else (10, 10, 10), type_rect, 1, border_radius=4)
            option_text = self.font.render(label, True, TEXT_COLOR)
            self.screen.blit(option_text, (type_rect.centerx - option_text.get_width() // 2, type_rect.centery - option_text.get_height() // 2))

        add_rect = pygame.Rect(panel.x + 30, panel.bottom - 52, 120, 34)
        cancel_rect = pygame.Rect(panel.right - 150, panel.bottom - 52, 120, 34)

        add_color = ADD_BUTTON_COLOR
        pygame.draw.rect(self.screen, add_color, add_rect, border_radius=4)
        pygame.draw.rect(self.screen, (10, 10, 10), add_rect, 1, border_radius=4)
        add_text = self.font.render("Add", True, TEXT_COLOR)
        self.screen.blit(add_text, (add_rect.centerx - add_text.get_width() // 2, add_rect.centery - add_text.get_height() // 2))

        pygame.draw.rect(self.screen, BTN_COLOR, cancel_rect, border_radius=4)
        pygame.draw.rect(self.screen, (10, 10, 10), cancel_rect, 1, border_radius=4)
        cancel_text = self.font.render("Cancel", True, TEXT_COLOR)
        self.screen.blit(cancel_text, (cancel_rect.centerx - cancel_text.get_width() // 2, cancel_rect.centery - cancel_text.get_height() // 2))

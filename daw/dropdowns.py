"""Dropdown panels: Tracks, Instrument (+ submenu), drum parts, gear menu."""

import pygame

from .config import *
from .theme import *
from .widgets import draw_arrow


class DropdownsMixin:
    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------

    def tracks_panel_rect(self):
        rows = len(self.tracks) + 1
        h = rows * DROPDOWN_ROW_H + 8
        return pygame.Rect(
            self.btn_tracks.rect.x,
            TOP_BAR_H,
            TRACK_PANEL_W,
            h
        )

    def instr_panel_rect(self):
        h = len(INSTRUMENTS) * DROPDOWN_ROW_H + 8
        return pygame.Rect(self.btn_instr.rect.x, TOP_BAR_H, INSTR_PANEL_W, h)

    def instr_subpanel_rect(self):
        if self.hovered_instrument_category is None:
            return pygame.Rect(0, 0, 0, 0)
        categories = list(INSTRUMENTS)
        idx = categories.index(self.hovered_instrument_category)
        y = TOP_BAR_H + 4 + idx * DROPDOWN_ROW_H
        return pygame.Rect(
            self.instr_panel_rect().right - 2,
            y,
            SUB_INSTR_PANEL_W,
            len(INSTRUMENTS[self.hovered_instrument_category]) * DROPDOWN_ROW_H + 8,
        )

    def menu_panel_rect(self):
        return pygame.Rect(self.viewport_w - 158, TOP_BAR_H, MENU_PANEL_W, DROPDOWN_ROW_H * 3 + 8)

    def close_dropdowns(self):
        self.show_tracks_dropdown = False
        self.show_instr_dropdown = False
        self.hovered_instrument_category = None
        self.hovered_drum_track = None

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw_drum_parts_dropdown(self):
        if self.hovered_drum_track is None:
            return

        # Draw the submenu for the specific drum track being hovered.
        drum_index = self.hovered_drum_track
        if not (0 <= drum_index < len(self.tracks)):
            return
        drum_track = self.tracks[drum_index]
        if not getattr(drum_track, "is_drum_track", False):
            return

        tracks_rect = self.tracks_panel_rect()

        row_y = (
                tracks_rect.y
                + 4
                + drum_index * DROPDOWN_ROW_H
        )

        # Submenu appears immediately to the right.
        panel_x = tracks_rect.right + 2
        panel_y = row_y

        parts = list(drum_track.parts.keys())

        panel_w = 130
        panel_h = len(parts) * DROPDOWN_ROW_H + 8

        # Keep submenu inside the window.
        if panel_x + panel_w > self.viewport_w:
            panel_x = tracks_rect.x - panel_w - 2

        if panel_y + panel_h > self.viewport_h:
            panel_y = self.viewport_h - panel_h - 4

        panel = pygame.Rect(
            panel_x,
            panel_y,
            panel_w,
            panel_h
        )

        pygame.draw.rect(
            self.screen,
            DROPDOWN_BG,
            panel,
            border_radius=4
        )

        pygame.draw.rect(
            self.screen,
            DROPDOWN_BORDER,
            panel,
            1,
            border_radius=4
        )

        mouse_pos = pygame.mouse.get_pos()

        for i, part in enumerate(parts):
            row_rect = pygame.Rect(
                panel.x + 4,
                panel.y + 4 + i * DROPDOWN_ROW_H,
                panel.width - 8,
                DROPDOWN_ROW_H
            )

            if part == drum_track.current_part:
                pygame.draw.rect(
                    self.screen,
                    DROPDOWN_SELECTED,
                    row_rect
                )
            elif row_rect.collidepoint(mouse_pos):
                pygame.draw.rect(
                    self.screen,
                    DROPDOWN_HOVER,
                    row_rect
                )

            label = self.font.render(
                part,
                True,
                TEXT_COLOR
            )

            self.screen.blit(
                label,
                (
                    row_rect.x + 6,
                    row_rect.y
                    + (row_rect.height - label.get_height()) // 2
                )
            )

    def draw_tracks_dropdown(self):
        if not self.show_tracks_dropdown:
            return

        rect = self.tracks_panel_rect()
        pygame.draw.rect(self.screen, DROPDOWN_BG, rect, border_radius=4)
        pygame.draw.rect(self.screen, DROPDOWN_BORDER, rect, 1, border_radius=4)

        mouse_pos = pygame.mouse.get_pos()

        for i, t in enumerate(self.tracks):
            row_rect = pygame.Rect(
                rect.x,
                rect.y + 4 + i * DROPDOWN_ROW_H,
                rect.width,
                DROPDOWN_ROW_H
            )

            if i == self.current_track_index:
                pygame.draw.rect(self.screen, DROPDOWN_SELECTED, row_rect)
            elif row_rect.collidepoint(mouse_pos):
                pygame.draw.rect(self.screen, DROPDOWN_HOVER, row_rect)

            label = self.font.render(t.name, True, TEXT_COLOR)
            self.screen.blit(
                label,
                (
                    row_rect.x + 8,
                    row_rect.y + (row_rect.height - label.get_height()) // 2
                )
            )

            # Drum tracks have a right-facing arrow.
            if getattr(t, "is_drum_track", False):
                arrow_x = row_rect.right - 14
                arrow_y = row_rect.centery

                pygame.draw.polygon(
                    self.screen,
                    MUTED_TEXT,
                    [
                        (arrow_x - 3, arrow_y - 5),
                        (arrow_x + 2, arrow_y),
                        (arrow_x - 3, arrow_y + 5),
                    ]
                )

        add_row = pygame.Rect(
            rect.x,
            rect.y + 4 + len(self.tracks) * DROPDOWN_ROW_H,
            rect.width,
            DROPDOWN_ROW_H
        )

        if add_row.collidepoint(mouse_pos):
            pygame.draw.rect(self.screen, DROPDOWN_HOVER, add_row)

        add_label = self.font.render(
            "+ Add track",
            True,
            (150, 210, 150)
        )

        self.screen.blit(
            add_label,
            (
                add_row.x + 8,
                add_row.y + (add_row.height - add_label.get_height()) // 2
            )
        )

        hint = self.font_small.render(
            "Right-click a track for settings / delete",
            True,
            MUTED_TEXT
        )

        self.screen.blit(
            hint,
            (rect.x + 6, rect.bottom + 2)
        )

    def draw_instr_dropdown(self):
        if not self.show_instr_dropdown:
            return

        rect = self.instr_panel_rect()
        pygame.draw.rect(self.screen, DROPDOWN_BG, rect, border_radius=4)
        pygame.draw.rect(self.screen, DROPDOWN_BORDER, rect, 1, border_radius=4)

        mouse_pos = pygame.mouse.get_pos()
        categories = list(INSTRUMENTS)

        for i, category in enumerate(categories):
            row_rect = pygame.Rect(rect.x, rect.y + 4 + i * DROPDOWN_ROW_H, rect.width, DROPDOWN_ROW_H)
            selected = self.track.instrument == category

            if selected:
                pygame.draw.rect(self.screen, DROPDOWN_SELECTED, row_rect)
            elif row_rect.collidepoint(mouse_pos):
                pygame.draw.rect(self.screen, DROPDOWN_HOVER, row_rect)

            label = self.font.render(category, True, TEXT_COLOR)
            self.screen.blit(label, (row_rect.x + 8, row_rect.y + (row_rect.height - label.get_height()) // 2))
            draw_arrow(self.screen, self.font_small, row_rect.right - 16, row_rect.y + 7, "right")

        if self.hovered_instrument_category is not None:
            self.draw_instr_submenu()

    def draw_instr_submenu(self):
        category = self.hovered_instrument_category
        if category is None:
            return

        rect = self.instr_subpanel_rect()
        pygame.draw.rect(self.screen, DROPDOWN_BG, rect, border_radius=4)
        pygame.draw.rect(self.screen, DROPDOWN_BORDER, rect, 1, border_radius=4)

        mouse_pos = pygame.mouse.get_pos()

        for i, sound in enumerate(INSTRUMENTS[category]):
            row_rect = pygame.Rect(rect.x, rect.y + 4 + i * DROPDOWN_ROW_H, rect.width, DROPDOWN_ROW_H)

            if self.track.sound == sound and self.track.instrument == category:
                pygame.draw.rect(self.screen, DROPDOWN_SELECTED, row_rect)
            elif row_rect.collidepoint(mouse_pos):
                pygame.draw.rect(self.screen, DROPDOWN_HOVER, row_rect)

            label = self.font.render(sound, True, TEXT_COLOR)
            self.screen.blit(label, (row_rect.x + 8, row_rect.y + (row_rect.height - label.get_height()) // 2))

    def draw_menu_dropdown(self):
        if not self.show_menu:
            return

        rect = self.menu_panel_rect()
        pygame.draw.rect(self.screen, DROPDOWN_BG, rect, border_radius=4)
        pygame.draw.rect(self.screen, DROPDOWN_BORDER, rect, 1, border_radius=4)

        labels = ["Save", "Load", "Help"]
        mouse = pygame.mouse.get_pos()

        for i, label in enumerate(labels):
            row = pygame.Rect(rect.x, rect.y + 4 + i * DROPDOWN_ROW_H, rect.width, DROPDOWN_ROW_H)
            if row.collidepoint(mouse):
                pygame.draw.rect(self.screen, DROPDOWN_HOVER, row)
            txt = self.font.render(label, True, TEXT_COLOR)
            self.screen.blit(txt, (row.x + 10, row.y + (row.height - txt.get_height()) // 2))

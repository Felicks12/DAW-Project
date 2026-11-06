"""Dropdown panels: Tracks (drag to reorder), Instrument (+ submenu), gear menu."""

import pygame

from .config import *
from .theme import *
from .widgets import draw_arrow


class DropdownsMixin:

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
        self.track_reorder = None

    def draw_tracks_dropdown(self):
        if not self.show_tracks_dropdown:
            return

        rect = self.tracks_panel_rect()
        pygame.draw.rect(self.screen, DROPDOWN_BG, rect, border_radius=4)
        pygame.draw.rect(self.screen, DROPDOWN_BORDER, rect, 1, border_radius=4)

        reorder = self.track_reorder if (self.track_reorder and self.track_reorder["active"]) else None
        show_grip = len(self.tracks) > 1

        for i, t in enumerate(self.tracks):
            row_rect = pygame.Rect(
                rect.x,
                rect.y + 4 + i * DROPDOWN_ROW_H,
                rect.width,
                DROPDOWN_ROW_H
            )

            if reorder is not None and reorder["index"] == i:
                held = row_rect.inflate(-4, -2)
                pygame.draw.rect(self.screen, DROPDOWN_SELECTED, held, border_radius=3)
                pygame.draw.rect(self.screen, NOTE_BORDER, held, 1, border_radius=3)
            elif i == self.current_track_index:
                pygame.draw.rect(self.screen, DROPDOWN_SELECTED, row_rect)
            elif self.hover_ok(row_rect, LAYER_TRACKS):
                pygame.draw.rect(self.screen, DROPDOWN_HOVER, row_rect)

            label_x = row_rect.x + 8

            if show_grip:
                for k in range(3):
                    gy = row_rect.centery - 3 + k * 3
                    pygame.draw.line(self.screen, MUTED_TEXT, (row_rect.x + 7, gy), (row_rect.x + 13, gy), 1)
                label_x = row_rect.x + 22

            label = self.font.render(t.name, True, TEXT_COLOR)
            self.screen.blit(
                label,
                (
                    label_x,
                    row_rect.y + (row_rect.height - label.get_height()) // 2
                )
            )

        add_row = pygame.Rect(
            rect.x,
            rect.y + 4 + len(self.tracks) * DROPDOWN_ROW_H,
            rect.width,
            DROPDOWN_ROW_H
        )

        if self.hover_ok(add_row, LAYER_TRACKS):
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
            "Drag to reorder - right-click for more",
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

        categories = list(INSTRUMENTS)

        for i, category in enumerate(categories):
            row_rect = pygame.Rect(rect.x, rect.y + 4 + i * DROPDOWN_ROW_H, rect.width, DROPDOWN_ROW_H)
            selected = self.track.instrument == category

            if selected:
                pygame.draw.rect(self.screen, DROPDOWN_SELECTED, row_rect)
            elif self.hover_ok(row_rect, LAYER_INSTR):
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

        for i, sound in enumerate(INSTRUMENTS[category]):
            row_rect = pygame.Rect(rect.x, rect.y + 4 + i * DROPDOWN_ROW_H, rect.width, DROPDOWN_ROW_H)

            if self.track.sound == sound and self.track.instrument == category:
                pygame.draw.rect(self.screen, DROPDOWN_SELECTED, row_rect)
            elif self.hover_ok(row_rect, LAYER_INSTR_SUB):
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

        for i, label in enumerate(labels):
            row = pygame.Rect(rect.x, rect.y + 4 + i * DROPDOWN_ROW_H, rect.width, DROPDOWN_ROW_H)
            if self.hover_ok(row, LAYER_MENU):
                pygame.draw.rect(self.screen, DROPDOWN_HOVER, row)
            txt = self.font.render(label, True, TEXT_COLOR)
            self.screen.blit(txt, (row.x + 10, row.y + (row.height - txt.get_height()) // 2))

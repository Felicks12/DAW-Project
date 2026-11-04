"""Top toolbar: transport buttons, BPM box, master volume, gear button."""

import numpy as np
import pygame

from .config import *
from .theme import *
from .widgets import Button


class ToolbarMixin:
    def master_volume_rect(self):
        return pygame.Rect(
            self.viewport_w - 175,
            13,
            MASTER_VOLUME_W,
            MASTER_VOLUME_H
        )

    def master_volume_slider_rect(self):
        rect = self.master_volume_rect()

        return pygame.Rect(
            rect.x + 42,
            rect.y + 5,
            rect.width - 42,
            8
        )

    def update_master_volume_from_mouse(self, pos):
        slider = self.master_volume_slider_rect()

        x = max(
            slider.left,
            min(slider.right - 1, pos[0])
        )

        self.master_volume = (
                (x - slider.left) / (slider.width - 1)
        )

        self.master_volume = max(
            0.0,
            min(1.0, self.master_volume)
        )

    def draw_master_volume(self):
        rect = self.master_volume_rect()

        # Label
        label = self.font_small.render(
            "Master",
            True,
            MUTED_TEXT
        )

        self.screen.blit(
            label,
            (
                rect.x,
                rect.y + 3
            )
        )

        slider = self.master_volume_slider_rect()

        pygame.draw.rect(
            self.screen,
            (55, 55, 60),
            slider,
            border_radius=4
        )

        fill = pygame.Rect(
            slider.x,
            slider.y,
            int(slider.width * self.master_volume),
            slider.height
        )

        pygame.draw.rect(
            self.screen,
            (90, 160, 220),
            fill,
            border_radius=4
        )

        handle_x = int(
            slider.x +
            slider.width * self.master_volume
        )

        pygame.draw.circle(
            self.screen,
            TEXT_COLOR,
            (handle_x, slider.centery),
            6
        )

        percent = self.font_small.render(
            f"{int(self.master_volume * 100)}%",
            True,
            MUTED_TEXT
        )

        self.screen.blit(
            percent,
            (
                rect.right - percent.get_width(),
                rect.bottom + 3
            )
        )

    def build_toolbar(self):
        x = 8
        y = 10
        h = TOP_BAR_H - 20
        self.btn_play = Button((x, y, 58, h), "Play"); x += 64
        self.btn_stop = Button((x, y, 58, h), "Stop"); x += 64
        self.btn_bpm_down = Button((x, y, 24, h), "-"); x += 28
        self.bpm_box = pygame.Rect(x, y, 72, h); x += 76
        self.btn_bpm_up = Button((x, y, 24, h), "+"); x += 30
        self.btn_tracks = Button((x, y, 78, h), "Tracks", dropdown=True); x += 84
        self.btn_instr = Button((x, y, 98, h), "Piano", dropdown=True); x += 104
        self.btn_view_all = Button((x, y, 74, h), "View All"); x += 80
        self.btn_menu = Button((self.windowed_size[0] - 48, y, 40, h), "")

    def reposition_toolbar(self):
        self.btn_menu.rect.x = self.viewport_w - 48

    def update_toolbar_labels(self):
        self.btn_play.label = "Pause" if self.playing else "Play"
        self.btn_instr.label = self.track.instrument
        self.reposition_toolbar()

    def draw_toolbar(self):
        pygame.draw.rect(self.screen, TOOLBAR_COLOR, (0, 0, self.viewport_w, TOP_BAR_H))

        self.btn_play.draw(self.screen, self.font, active=self.playing)
        self.btn_stop.draw(self.screen, self.font)
        self.btn_bpm_down.draw(self.screen, self.font)
        self.btn_bpm_up.draw(self.screen, self.font)

        self.btn_tracks.draw(self.screen, self.font, active=self.show_tracks_dropdown, active_color=BTN_HELP_ACTIVE)
        self.btn_instr.draw(self.screen, self.font, active=self.show_instr_dropdown, active_color=BTN_HELP_ACTIVE)
        self.btn_view_all.draw(self.screen, self.font, active=self.view_all_tracks, active_color=BTN_HELP_ACTIVE)
        self.draw_gear_button()

        self.draw_master_volume()

        box_color = INPUT_BOX_EDITING if self.editing_bpm else INPUT_BOX_COLOR
        pygame.draw.rect(self.screen, box_color, self.bpm_box, border_radius=4)
        pygame.draw.rect(self.screen, (10, 10, 10), self.bpm_box, 1, border_radius=4)

        label = self.bpm_input_str if self.editing_bpm else f"{self.bpm}"
        num_text = self.font.render(label, True, TEXT_COLOR)
        suffix = self.font_small.render("BPM", True, MUTED_TEXT)

        self.screen.blit(num_text, (self.bpm_box.x + 6, self.bpm_box.y + (self.bpm_box.height - num_text.get_height()) // 2))
        self.screen.blit(suffix, (self.bpm_box.right - suffix.get_width() - 6, self.bpm_box.y + (self.bpm_box.height - suffix.get_height()) // 2))

        if self.editing_bpm and (pygame.time.get_ticks() // 500) % 2 == 0:
            caret_x = self.bpm_box.x + 6 + num_text.get_width()
            pygame.draw.line(self.screen, TEXT_COLOR, (caret_x, self.bpm_box.y + 5), (caret_x, self.bpm_box.bottom - 5), 2)

    def draw_gear_button(self):
        rect = self.btn_menu.rect
        now = pygame.time.get_ticks()
        active = self.show_menu
        color = BTN_HELP_ACTIVE if active else BTN_COLOR

        if now < self.btn_menu.pressed_until:
            color = FLASH_COLOR

        pygame.draw.rect(self.screen, color, rect, border_radius=4)
        pygame.draw.rect(self.screen, (10, 10, 10), rect, 1, border_radius=4)

        cx, cy = rect.center
        tooth_color = TEXT_COLOR

        for i in range(8):
            angle = i * (np.pi / 4)
            x1 = cx + int(np.cos(angle) * 7)
            y1 = cy + int(np.sin(angle) * 7)
            x2 = cx + int(np.cos(angle) * 10)
            y2 = cy + int(np.sin(angle) * 10)
            pygame.draw.line(self.screen, tooth_color, (x1, y1), (x2, y2), 3)

        pygame.draw.circle(self.screen, tooth_color, (cx, cy), 7)
        pygame.draw.circle(self.screen, color, (cx, cy), 3)

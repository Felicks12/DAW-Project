"""Coordinate conversion, zoom and fullscreen."""

import pygame

from .config import *


class ViewportMixin:
    def screen_x_to_step(self, x):
        return (x - KEY_AREA_WIDTH + self.scroll_x) / self.step_width

    def step_to_screen_x(self, step):
        return KEY_AREA_WIDTH + step * self.step_width - self.scroll_x

    def screen_y_to_row(self, y):
        return int((y - GRID_Y + self.scroll_y) // ROW_HEIGHT)

    def row_to_screen_y(self, row):
        return GRID_Y + row * ROW_HEIGHT - self.scroll_y

    def current_snap_steps(self):
        # Always snap to a 16th note. The grid may become visually compressed
        # at low zoom, but musical placement remains 16th-note accurate.
        return 1

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.windowed_size = self.screen.get_size()
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)

    def zoom(self, direction):
        if direction == 0:
            return

        mouse_x, _ = pygame.mouse.get_pos()
        step_under_mouse = self.screen_x_to_step(mouse_x)
        factor = 1.15 if direction > 0 else (1 / 1.15)

        self.step_width = max(MIN_STEP_WIDTH, min(MAX_STEP_WIDTH, self.step_width * factor))

        self.scroll_x = step_under_mouse * self.step_width - (mouse_x - KEY_AREA_WIDTH)
        self.scroll_x = max(0, min(self.scroll_x, self.max_scroll_x))

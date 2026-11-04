"""Popup stacking: which menu is on top, hover blocking and cursor.

When menus overlap, rows underneath the top-most menu must not react to the
mouse (no hover highlight, no hover-opened submenus, no resize cursor).
"""

import pygame

from .config import *


class OverlayMixin:
    def modal_open(self):
        return bool(self.naming_track or self.show_track_settings or self.show_help)

    def popup_open(self):
        return bool(
            self.modal_open()
            or self.show_menu
            or self.show_tracks_dropdown
            or self.show_instr_dropdown
            or self.track_context_menu is not None
        )

    def overlay_layer_rects(self):
        """[(layer, rect)] for every visible popup menu."""
        layers = []

        if self.show_tracks_dropdown:
            layers.append((LAYER_TRACKS, self.tracks_panel_rect()))

        if self.show_instr_dropdown:
            layers.append((LAYER_INSTR, self.instr_panel_rect()))

            if self.hovered_instrument_category is not None:
                layers.append((LAYER_INSTR_SUB, self.instr_subpanel_rect()))

        if self.show_menu:
            layers.append((LAYER_MENU, self.menu_panel_rect()))

        if self.track_context_menu is not None:
            layers.append((LAYER_CONTEXT, self.track_context_menu_rect()))

        return layers

    def hover_ok(self, rect, layer):
        """True if the mouse is over `rect` and nothing above `layer` covers it."""
        pos = pygame.mouse.get_pos()

        if not rect.collidepoint(pos) or self.modal_open():
            return False

        for other_layer, other_rect in self.overlay_layer_rects():
            if other_layer > layer and other_rect.collidepoint(pos):
                return False

        return True

    def handle_mouse_motion(self, pos):
        # A slider being dragged inside the settings popup must keep working.
        if self.dragging_slider is None:
            # Menus / popups on top swallow hover changes underneath them.
            if self.modal_open() or self.track_context_menu is not None:
                return

            # The instrument submenu overlaps its parent list; the submenu wins.
            if (
                    self.show_instr_dropdown
                    and self.hovered_instrument_category is not None
                    and self.instr_subpanel_rect().collidepoint(pos)
            ):
                return

        super().handle_mouse_motion(pos)

        # Drum parts are chosen in the drum sample panel now; the old
        # "Drums" fly-out submenu in the Tracks list no longer exists.
        self.hovered_drum_track = None

    def update_cursor(self):
        pos = pygame.mouse.get_pos()

        covered = (
            self.show_menu
            or self.show_help
            or any(rect.collidepoint(pos) for _, rect in self.overlay_layer_rects())
        )

        if covered and self.resizing is None and self.moving is None:
            if self.cursor_state != "arrow":
                self.cursor_state = "arrow"
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
            return

        super().update_cursor()

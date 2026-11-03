"""Track right-click context menu and the per-track settings (EQ) popup."""

import pygame

from .config import *
from .theme import *


class TrackMenuMixin:
    # ------------------------------------------------------------------
    # Track right-click context menu (Mute / Solo / Settings / Delete)
    # ------------------------------------------------------------------

    def track_context_menu_rect(self):
        if self.track_context_menu is None:
            return pygame.Rect(0, 0, 0, 0)

        x, y = self.track_context_menu["pos"]
        w = CONTEXT_MENU_W
        h = DROPDOWN_ROW_H * 4 + 8

        x = min(x, self.viewport_w - w - 4)
        y = min(y, self.viewport_h - h - 4)

        return pygame.Rect(x, y, w, h)

    def draw_track_context_menu(self):
        if self.track_context_menu is None:
            return

        rect = self.track_context_menu_rect()

        pygame.draw.rect(
            self.screen,
            DROPDOWN_BG,
            rect,
            border_radius=4
        )

        pygame.draw.rect(
            self.screen,
            DROPDOWN_BORDER,
            rect,
            1,
            border_radius=4
        )

        mouse_pos = pygame.mouse.get_pos()
        idx = self.track_context_menu["index"]

        if idx >= len(self.tracks):
            self.track_context_menu = None
            return

        track = self.tracks[idx]

        rows = [
            ("Mute Track", track.muted),
            ("Solo Track", self.isolated_track_index == idx),
            ("Track Settings", False),
            ("Delete Track", False),
        ]

        for i, (label, active) in enumerate(rows):

            row = pygame.Rect(
                rect.x + 4,
                rect.y + 4 + i * DROPDOWN_ROW_H,
                rect.width - 8,
                DROPDOWN_ROW_H
            )

            if row.collidepoint(mouse_pos):
                pygame.draw.rect(
                    self.screen,
                    DROPDOWN_HOVER,
                    row
                )

            if active:
                color = (110, 190, 120)
                label = "" + label
            elif label == "Delete Track":
                color = (210, 120, 120)
            else:
                color = TEXT_COLOR

            text = self.font.render(
                label,
                True,
                color
            )

            self.screen.blit(
                text,
                (
                    row.x + 6,
                    row.y + (
                            row.height -
                            text.get_height()
                    ) // 2
                )
            )

    def handle_track_context_menu_click(self, pos):
        rect = self.track_context_menu_rect()

        if self.track_context_menu is None:
            return

        idx = self.track_context_menu["index"]

        if idx >= len(self.tracks):
            self.track_context_menu = None
            return

        if not rect.collidepoint(pos):
            self.track_context_menu = None
            return

        track = self.tracks[idx]

        rows = {
            "mute": pygame.Rect(
                rect.x + 4,
                rect.y + 4,
                rect.width - 8,
                DROPDOWN_ROW_H
            ),

            "solo": pygame.Rect(
                rect.x + 4,
                rect.y + 4 + DROPDOWN_ROW_H,
                rect.width - 8,
                DROPDOWN_ROW_H
            ),

            "settings": pygame.Rect(
                rect.x + 4,
                rect.y + 4 + DROPDOWN_ROW_H * 2,
                rect.width - 8,
                DROPDOWN_ROW_H
            ),

            "delete": pygame.Rect(
                rect.x + 4,
                rect.y + 4 + DROPDOWN_ROW_H * 3,
                rect.width - 8,
                DROPDOWN_ROW_H
            ),
        }

        if rows["mute"].collidepoint(pos):
            # Mute and Isolate are mutually exclusive. If isolation is active,
            # clicking Mute exits isolation before changing the mute state.
            if self.isolated_track_index is not None:
                self.isolated_track_index = None

            track.muted = not track.muted

            if track.muted:
                track.engine.all_notes_off()
                if hasattr(track, "sounding"):
                    track.sounding.clear()

            self.track_context_menu = None
            return

        if rows["solo"].collidepoint(pos):
            # Isolate is exclusive: this track is unmuted and every other
            # track is automatically muted. Only this track is isolated.
            if self.isolated_track_index == idx:
                # Turn isolation off.
                self.isolated_track_index = None

                # Unmute every track.
                for t in self.tracks:
                    t.muted = False
                    t.engine.all_notes_off()
                    if hasattr(t, "sounding"):
                        t.sounding.clear()

            else:
                # Isolate this track.
                self.isolated_track_index = idx

                # Unmute the isolated track and mute everything else.
                for track_index, t in enumerate(self.tracks):
                    t.muted = (track_index != idx)

                    if t.muted:
                        t.engine.all_notes_off()
                        if hasattr(t, "sounding"):
                            t.sounding.clear()

                for track_index, t in enumerate(self.tracks):
                    if track_index == idx:
                        # A track cannot be both isolated and muted.
                        t.muted = False
                    else:
                        # Isolating this track automatically mutes every other track.
                        t.muted = True
                        t.engine.all_notes_off()
                        if hasattr(t, "sounding"):
                            t.sounding.clear()

            self.track_context_menu = None
            return

        if rows["settings"].collidepoint(pos):
            self.track_settings_index = idx
            self.show_track_settings = True
            self.track_context_menu = None
            return

        if (
                rows["delete"].collidepoint(pos)
                and len(self.tracks) > 1
        ):
            track.engine.all_notes_off()

            del self.tracks[idx]

            if self.current_track_index >= len(self.tracks):
                self.current_track_index = len(self.tracks) - 1
            elif self.current_track_index > idx:
                self.current_track_index -= 1

            self.selected_notes = set()
            self.track_context_menu = None

            self.update_toolbar_labels()
            return

        self.track_context_menu = None

    def get_track_steps_per_measure(self, track):
        numerator, denominator = track.time_signature

        if denominator == 4:
            return numerator * STEPS_PER_BEAT

        if denominator == 8:
            return numerator * 2

        return STEPS_PER_MEASURE

    # ------------------------------------------------------------------
    # Track settings popup (Bass / Mid / Treble)
    # ------------------------------------------------------------------

    def track_settings_panel_rect(self):
        w, h = 380, 380
        return pygame.Rect((self.viewport_w - w) // 2, (self.viewport_h - h) // 2, w, h)

    def track_settings_slider_rects(self):
        panel = self.track_settings_panel_rect()
        slider_h = 180
        slider_top = panel.y + 78
        xs = [panel.x + 80, panel.x + 190, panel.x + 300]
        return {band: pygame.Rect(x - 10, slider_top, 20, slider_h) for band, x in zip(EQ_BANDS, xs)}

    def update_slider_from_mouse(self, pos):
        d = self.dragging_slider
        if d is None:
            return
        rect = self.track_settings_slider_rects()[d["band"]]
        y = max(rect.top, min(rect.bottom, pos[1]))
        frac = 1.0 - (y - rect.top) / rect.height
        gain = max(0.0, min(2.0, frac * 2.0))
        setattr(self.tracks[d["index"]].eq, f"{d['band']}_gain", gain)

    def draw_track_settings(self):
        if not self.show_track_settings:
            return
        if self.track_settings_index is None or self.track_settings_index >= len(self.tracks):
            self.show_track_settings = False
            return

        overlay = pygame.Surface((self.viewport_w, self.viewport_h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 130))
        self.screen.blit(overlay, (0, 0))

        track = self.tracks[self.track_settings_index]
        panel = self.track_settings_panel_rect()
        pygame.draw.rect(self.screen, MODAL_BG, panel, border_radius=8)
        pygame.draw.rect(self.screen, MODAL_BORDER, panel, 1, border_radius=8)

        title = self.font_title.render(f"{track.name} — Settings", True, TEXT_COLOR)
        self.screen.blit(title, (panel.x + 18, panel.y + 14))

        close_rect = pygame.Rect(panel.right - 30, panel.y + 8, 22, 22)
        pygame.draw.rect(self.screen, BTN_COLOR, close_rect, border_radius=4)
        self.screen.blit(self.font.render("x", True, TEXT_COLOR), (close_rect.x + 7, close_rect.y + 4))

        if track.eq.clipping:
            clip_label = self.font_small.render("CLIP", True, METER_HOT_COLOR)
            self.screen.blit(clip_label, (panel.right - 70, panel.y + 12))

        sliders = self.track_settings_slider_rects()
        levels = {
            "bass": track.eq.last_bass_level,
            "mid": track.eq.last_mid_level,
            "treble": track.eq.last_treble_level,
        }

        for band in EQ_BANDS:
            rect = sliders[band]
            gain = getattr(track.eq, f"{band}_gain")

            # slider track: lower half (0.0-1.0, cut-to-unity) neutral,
            # upper half (1.0-2.0, boost) tinted red as a "redline" warning
            unity_y = rect.y + rect.height // 2
            lower_rect = pygame.Rect(rect.x, unity_y, rect.width, rect.bottom - unity_y)
            upper_rect = pygame.Rect(rect.x, rect.y, rect.width, unity_y - rect.y)
            pygame.draw.rect(self.screen, SLIDER_TRACK_COLOR, lower_rect)
            pygame.draw.rect(self.screen, SLIDER_REDLINE_COLOR, upper_rect)
            pygame.draw.rect(self.screen, (10, 10, 10), rect, 1)
            pygame.draw.line(self.screen, MUTED_TEXT, (rect.x - 4, unity_y), (rect.right + 4, unity_y), 1)

            # handle
            frac = gain / 2.0
            handle_y = int(rect.y + rect.height * (1.0 - frac))
            handle_color = SLIDER_HANDLE_HOT if gain > 1.5 else SLIDER_HANDLE_COLOR
            handle_rect = pygame.Rect(rect.x - 6, handle_y - 5, rect.width + 12, 10)
            pygame.draw.rect(self.screen, handle_color, handle_rect, border_radius=3)
            pygame.draw.rect(self.screen, (10, 10, 10), handle_rect, 1, border_radius=3)

            # live level meter beside the fader
            meter_rect = pygame.Rect(rect.right + 10, rect.y, 8, rect.height)
            pygame.draw.rect(self.screen, METER_BG, meter_rect)
            level = min(1.0, levels[band] * 4.0)  # scale RMS up so it's visible
            fill_h = int(meter_rect.height * level)
            fill_rect = pygame.Rect(meter_rect.x, meter_rect.bottom - fill_h, meter_rect.width, fill_h)
            meter_color = METER_HOT_COLOR if level > 0.85 else METER_OK_COLOR
            pygame.draw.rect(self.screen, meter_color, fill_rect)
            pygame.draw.rect(self.screen, (10, 10, 10), meter_rect, 1)

            # label + percentage
            label = self.font.render(band.capitalize(), True, TEXT_COLOR)
            self.screen.blit(label, (rect.centerx - label.get_width() // 2, rect.bottom + 10))
            pct = self.font_small.render(f"{int(gain * 100)}%", True, MUTED_TEXT)
            self.screen.blit(pct, (rect.centerx - pct.get_width() // 2, rect.bottom + 28))

        # Time signature
        ts_label = self.font.render("Time Signature", True, TEXT_COLOR)
        self.screen.blit(
            ts_label,
            (panel.x + 18, panel.top + 50)
        )

        ts_rect = pygame.Rect(
            panel.x + 300,
            panel.top + 45,
            50,
            25
        )

        pygame.draw.rect(
            self.screen,
            BTN_COLOR,
            ts_rect,
            border_radius=4
        )

        pygame.draw.rect(
            self.screen,
            (10, 10, 10),
            ts_rect,
            1,
            border_radius=4
        )

        numerator, denominator = track.time_signature

        ts_text = self.font.render(
            f"{numerator}/{denominator}",
            True,
            TEXT_COLOR
        )

        self.screen.blit(
            ts_text,
            (
                ts_rect.centerx - ts_text.get_width() // 2,
                ts_rect.centery - ts_text.get_height() // 2
            )
        )

        hint = self.font_small.render("Drag a slider — the red zone above center boosts (watch for CLIP).", True, MUTED_TEXT)
        self.screen.blit(hint, (panel.x + 18, panel.bottom - 26))

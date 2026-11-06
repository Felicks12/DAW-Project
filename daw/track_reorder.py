"""Rearrange tracks by dragging them in the Tracks dropdown."""

from .config import *


class TrackReorderMixin:
    def _reorder_row_at(self, pos):
        """Index of the track row under pos in the Tracks dropdown, or None."""
        if not self.show_tracks_dropdown:
            return None

        rect = self.tracks_panel_rect()

        if not rect.collidepoint(pos):
            return None

        index = (pos[1] - rect.y - 4) // DROPDOWN_ROW_H

        if 0 <= index < len(self.tracks):
            return index

        return None

    def move_track(self, src, dst):
        """Move a track in the list, keeping every index that points at tracks valid."""
        count = len(self.tracks)

        if src == dst or not (0 <= src < count) or not (0 <= dst < count):
            return

        current = self.tracks[self.current_track_index]

        isolated = None
        if self.isolated_track_index is not None and self.isolated_track_index < count:
            isolated = self.tracks[self.isolated_track_index]

        settings = None
        if self.track_settings_index is not None and self.track_settings_index < count:
            settings = self.tracks[self.track_settings_index]

        track = self.tracks.pop(src)
        self.tracks.insert(dst, track)

        self.current_track_index = self.tracks.index(current)

        if isolated is not None:
            self.isolated_track_index = self.tracks.index(isolated)

        if settings is not None:
            self.track_settings_index = self.tracks.index(settings)

        self.hovered_drum_track = None

    def _select_track_from_dropdown(self, index):
        if not (0 <= index < len(self.tracks)):
            return

        self.current_track_index = index
        self.selected_notes = set()
        self.show_tracks_dropdown = False
        self.hovered_instrument_category = None
        self.hovered_drum_track = None
        self.update_toolbar_labels()

    def handle_mouse_down(self, pos, button):
        if button == 1 and not self.modal_open() and self.track_context_menu is None:
            index = self._reorder_row_at(pos)

            if index is not None:
                self.track_reorder = {"index": index, "start": pos, "active": False}
                return

        super().handle_mouse_down(pos, button)

    def handle_mouse_motion(self, pos):
        reorder = self.track_reorder

        if reorder is not None:
            if not reorder["active"] and abs(pos[1] - reorder["start"][1]) >= 6:
                reorder["active"] = True

            if reorder["active"]:
                rect = self.tracks_panel_rect()
                target = (pos[1] - rect.y - 4) // DROPDOWN_ROW_H
                target = max(0, min(len(self.tracks) - 1, target))

                if target != reorder["index"]:
                    self.move_track(reorder["index"], target)
                    reorder["index"] = target

            return

        super().handle_mouse_motion(pos)

    def handle_mouse_up(self, pos, button):
        reorder = self.track_reorder

        if reorder is not None and button == 1:
            self.track_reorder = None

            if not reorder["active"]:
                self._select_track_from_dropdown(reorder["index"])

            return

        super().handle_mouse_up(pos, button)

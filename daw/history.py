"""Undo / redo (Ctrl+Z, Ctrl+Y / Ctrl+Shift+Z).

A snapshot is a list of (track, data) pairs. Snapshots refer to the track
objects themselves, so deleting, adding or reordering tracks (or loading a
new project) can never restore notes into the wrong track.
"""

import pygame


class HistoryMixin:
    def _snapshot(self):
        snap = []

        for track in self.tracks:
            if getattr(track, "is_drum_track", False):
                data = {"parts": {name: set(notes) for name, notes in track.parts.items()}}
            else:
                data = {"notes": set(track.notes)}

            snap.append((track, data))

        return snap

    @staticmethod
    def _same_snapshot(a, b):
        return len(a) == len(b) and all(
            x[0] is y[0] and x[1] == y[1] for x, y in zip(a, b)
        )

    def _restore(self, snap):
        for track, data in snap:
            if track not in self.tracks:
                continue

            if "parts" in data:
                for name, notes in data["parts"].items():
                    track.parts[name] = set(notes)
            else:
                track.notes = set(data["notes"])

            track.engine.all_notes_off()

            if hasattr(track, "sounding"):
                track.sounding.clear()

        self.selected_notes = set()

    def save_undo_state(self):
        """Call BEFORE changing notes."""
        snap = self._snapshot()

        if self.undo_stack and self._same_snapshot(self.undo_stack[-1], snap):
            return

        self.undo_stack.append(snap)

        if len(self.undo_stack) > self.max_undo_history:
            self.undo_stack.pop(0)

        self.redo_stack.clear()

    def undo(self):
        while self.undo_stack:
            snap = self.undo_stack.pop()
            live = [(t, d) for t, d in snap if t in self.tracks]

            # Snapshot of tracks that no longer exist (e.g. before a load).
            if not live:
                continue

            self.redo_stack.append(self._snapshot())
            self._restore(live)
            return

    def redo(self):
        while self.redo_stack:
            snap = self.redo_stack.pop()
            live = [(t, d) for t, d in snap if t in self.tracks]

            if not live:
                continue

            self.undo_stack.append(self._snapshot())
            self._restore(live)
            return

    def handle_keydown(self, event):
        mods = pygame.key.get_mods()
        free = not (self.popup_open() or self.editing_bpm)

        if free and (mods & pygame.KMOD_CTRL):
            redo_key = event.key == pygame.K_y or (
                event.key == pygame.K_z and (mods & pygame.KMOD_SHIFT)
            )

            if redo_key:
                self.redo()
                return

        super().handle_keydown(event)

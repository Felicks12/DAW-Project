"""Note audition (preview sounds when clicking the keyboard / grid)."""

import pygame


class PreviewMixin:
    def _stop_preview(self):
        if self.preview_pitch is not None:
            self.engine.note_off(self.preview_pitch)
            self.preview_pitch = None

        if self.grid_preview_pitch is not None:
            self.engine.note_off(self.grid_preview_pitch)
            self.grid_preview_pitch = None

    def preview_grid_note(self, pitch, duration_ms=260):
        # ----------------------------------------------------------
        # DRUM TRACK
        # ----------------------------------------------------------
        if getattr(self.track, "is_drum_track", False):
            self.track.engine.play_drum(
                self.track.current_part,
                pitch=pitch,
                velocity=100
            )
            return

        # ----------------------------------------------------------
        # NORMAL PIANO / SYNTH TRACK
        # ----------------------------------------------------------

        if self.grid_preview_pitch == pitch:
            self.grid_preview_release_at = (
                    pygame.time.get_ticks() + duration_ms
            )
            return

        if self.grid_preview_pitch is not None:
            self.engine.note_off(
                self.grid_preview_pitch
            )

        self.engine.note_on(
            pitch,
            velocity=100
        )

        self.grid_preview_pitch = pitch

        self.grid_preview_release_at = (
                pygame.time.get_ticks() + duration_ms
        )

    def update_previews(self):
        if self.grid_preview_pitch is not None and pygame.time.get_ticks() >= self.grid_preview_release_at:
            self.engine.note_off(self.grid_preview_pitch)
            self.grid_preview_pitch = None

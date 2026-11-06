"""Transport: play / pause / stop, playhead position and the playback clock."""

import time

from .config import *


class PlaybackMixin:
    def set_playhead_from_mouse(self, mouse_x):
        step = self.screen_x_to_step(mouse_x)
        step = max(0.0, min(step, self.total_steps))

        self.playhead_step = step
        self.play_pos_seconds = step * self.seconds_per_step
        self.playhead_visual_time = self.play_pos_seconds

        # If playback is running, move its clock to the new position too.
        if self.playing:
            self.playback_start_time = (
                    time.perf_counter() - self.play_pos_seconds
            )

            # Stop notes that were sounding at the old position.
            for track in self.tracks:
                track.engine.all_notes_off()

                if hasattr(track, "sounding"):
                    track.sounding.clear()

            # Allow playback to trigger notes at the new step.
            self.last_playback_step = int(step) - 1

    def toggle_play(self):
        self.playing = not self.playing

        if self.playing:
            # Start from the current playhead position.
            start_seconds = self.playhead_step * self.seconds_per_step

            self.playback_start_time = (
                    time.perf_counter()
                    + self.playhead_delay
                    - start_seconds
            )

            self.last_playback_step = int(self.playhead_step) - 1
            self.play_pos_seconds = start_seconds
            self.playhead_visual_time = 0.0

        else:
            for t in self.tracks:
                t.engine.all_notes_off()

                if hasattr(t, "sounding"):
                    t.sounding.clear()

                if getattr(t, "is_drum_track", False):
                    t.playback_time = 0.0

    def stop_playback(self):
        self.playing = False
        self.play_pos_seconds = 0.0
        self.playhead_visual_time = 0.0
        self.playhead_step = 0.0

        for t in self.tracks:
            t.engine.all_notes_off()

            if hasattr(t, "sounding"):
                t.sounding.clear()

            if getattr(t, "is_drum_track", False):
                t.playback_time = 0.0

        self.last_playback_step = -1

    def update_playback(self, dt):
        if not self.playing:
            return

        step_len = self.seconds_per_step

        now = time.perf_counter()

        playback_time = (
                now - self.playback_start_time
        )

        # Still inside the startup delay.
        if playback_time < 0:
            self.play_pos_seconds = 0.0
            self.playhead_visual_time = 0.0
            self.playhead_step = 0.0
            return

        self.play_pos_seconds = playback_time

        audio_time = playback_time + self.audio_lead

        cur_step = int(
            audio_time / step_len
        )

        if playback_time >= self.total_steps * step_len:
            self.playback_start_time = (
                now
            )

            self.play_pos_seconds = 0.0
            self.playhead_visual_time = 0.0

            cur_step = 0
            self.last_playback_step = -1

            for t in self.tracks:
                t.engine.all_notes_off()

                if hasattr(t, "sounding"):
                    t.sounding.clear()

        if cur_step != self.last_playback_step:

            first_step = self.last_playback_step + 1

            if self.last_playback_step == -1:
                first_step = 0

            for step in range(
                    first_step,
                    cur_step + 1
            ):

                for t in self.tracks:

                    if getattr(
                            t,
                            "is_drum_track",
                            False
                    ):
                        continue

                    # Stop notes that ended on or before this step.
                    ended = [
                        k
                        for k, end in t.sounding.items()
                        if end <= step
                    ]

                    for k in ended:
                        t.engine.note_off(k[0])
                        del t.sounding[k]

                    # Start notes on this step.
                    for note in t.notes:
                        pitch, start, length = note

                        if start == step:
                            t.engine.note_on(
                                pitch,
                                velocity=100
                            )

                            t.sounding[note] = (
                                    start + length
                            )

                for t in self.tracks:

                    if not getattr(
                            t,
                            "is_drum_track",
                            False
                    ):
                        continue

                    for name, notes in t.parts.items():

                        for note in notes:
                            pitch, start, length = note

                            if start == step:
                                t.engine.play_drum(
                                    name,
                                    pitch=pitch,
                                    velocity=100
                                )

            self.last_playback_step = cur_step

        self.playhead_step = (
                self.play_pos_seconds / step_len
        )

        playhead_x = self.step_to_screen_x(self.playhead_step)

        if (
                playhead_x < KEY_AREA_WIDTH
                or playhead_x > self.viewport_w - 150
        ):
            target_scroll = int(
                self.playhead_step * self.step_width - 100
            )

            self.scroll_x = max(
                0,
                min(target_scroll, self.max_scroll_x)
            )

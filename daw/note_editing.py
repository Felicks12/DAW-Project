"""Note data: add / move / resize / delete, selection, clipboard, undo."""

from .config import *


class NoteEditingMixin:
    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------

    def save_undo_state(self):
        state = []

        for t in self.tracks:
            if getattr(t, "is_drum_track", False):
                state.append({
                    "type": "drum",
                    "parts": {
                        name: set(notes)
                        for name, notes in t.parts.items()
                    }
                })
            else:
                state.append({
                    "type": "instrument",
                    "notes": set(t.notes)
                })

        self.undo_stack.append(state)

        if len(self.undo_stack) > self.max_undo_history:
            self.undo_stack.pop(0)

    def undo(self):
        if not self.undo_stack:
            return

        state = self.undo_stack.pop()

        for t, notes in zip(self.tracks, state):
            t.notes.clear()
            t.notes.update(notes)

        self.selected_notes = set()

        for t in self.tracks:
            t.engine.all_notes_off()
            t.sounding.clear()

    # ------------------------------------------------------------------
    # Commit drag operations
    # ------------------------------------------------------------------

    def commit_move(self):
        m = self.moving

        if not m["valid"]:
            return

        selected_orig = m["selected_orig"]
        delta_steps = m.get("current_delta_steps", 0)
        delta_rows = m.get("current_delta_rows", 0)

        if delta_steps == 0 and delta_rows == 0:
            return

        # Save undo state before actually changing the notes.
        self.save_undo_state()

        selected_set = set(selected_orig)

        # Remove all original selected notes.
        for note in selected_orig:
            self.get_current_notes().discard(note)

        # Add all moved notes.
        new_selected = set()

        for pitch, start, length in selected_orig:
            new_note = (
                pitch - delta_rows,
                start + delta_steps,
                length
            )

            self.get_current_notes().add(new_note)
            new_selected.add(new_note)

        # Keep the moved notes selected.
        self.selected_notes = new_selected

    def commit_resize(self):
        r = self.resizing

        if not r["valid"]:
            # Restore the original notes if the resize was invalid.
            return

        selected_orig = r["selected_orig"]
        current_notes = r["current_notes"]

        # Nothing changed
        if current_notes == selected_orig:
            return

        # Remove all original notes
        for note in selected_orig:
            self.get_current_notes().discard(note)
            self.selected_notes.discard(note)

        # Add the resized notes
        for note in current_notes:
            self.get_current_notes().add(note)
            self.selected_notes.add(note)

    # ------------------------------------------------------------------
    # Marquee (rubber-band) selection
    # ------------------------------------------------------------------

    def finish_marquee(self):
        if self.marquee is None:
            return

        x0, y0 = self.marquee["start"]
        x1, y1 = self.marquee["current"]
        left, right = sorted((x0, x1))
        top, bottom = sorted((y0, y1))

        step_a = self.screen_x_to_step(left)
        step_b = self.screen_x_to_step(right)
        row_a = self.screen_y_to_row(top)
        row_b = self.screen_y_to_row(bottom)
        pitch_hi = row_to_pitch(row_a)
        pitch_lo = row_to_pitch(row_b)

        selected = set()
        for n in self.get_current_notes():
            npitch, nstart, nlen = n
            if pitch_lo <= npitch <= pitch_hi and nstart < step_b and nstart + nlen > step_a:
                selected.add(n)

        self.selected_notes = selected
        self.marquee = None

    # ------------------------------------------------------------------
    # Copy / paste
    # ------------------------------------------------------------------

    def copy_selected_notes(self):
        if not self.selected_notes:
            return
        min_start = min(n[1] for n in self.selected_notes)
        self.clipboard = sorted((n[0], n[1] - min_start, n[2]) for n in self.selected_notes)
        self.clipboard_end = max(n[1] + n[2] for n in self.selected_notes)

    def paste_notes(self):
        if not self.clipboard:
            return
        anchor = self.clipboard_end
        pasted = set()
        for pitch, rel_start, length in self.clipboard:
            new_start = anchor + rel_start
            if new_start + length > self.total_steps:
                continue
            if self.overlaps(pitch, new_start, length):
                continue
            note = (pitch, new_start, length)
            self.get_current_notes().add(note)
            pasted.add(note)

        if pasted:
            self.selected_notes = pasted
            self.clipboard_end = max(n[1] + n[2] for n in pasted)

    # ------------------------------------------------------------------
    # Note data
    # ------------------------------------------------------------------

    def get_current_notes(self):
        track = self.tracks[self.current_track_index]

        if getattr(track, "is_drum_track", False):
            return track.parts[track.current_part]

        return track.notes

    def hit_test_note(self, pitch, x):
        """
        Single source of truth for "what's under the cursor at this pitch
        row and x": a note's body, its left/right resize edge, or nothing.

        Both the cursor icon (update_cursor) and the actual click handler
        use this, so the resize arrow and the resize hitbox can never
        drift apart the way they could when each had its own hit-test.
        The edge zone is intentionally allowed to extend EDGE_GRAB_PX
        outside the note's visual bounds, not just inside — otherwise a
        cursor that shows the resize arrow just past the edge would click
        through to "add a new note" instead.
        """
        for n in self.get_current_notes():
            npitch, nstart, nlen = n
            if npitch != pitch:
                continue

            left_x = self.step_to_screen_x(nstart)
            right_x = self.step_to_screen_x(nstart + nlen)

            if left_x - EDGE_GRAB_PX <= x <= right_x + EDGE_GRAB_PX:
                if abs(x - left_x) <= EDGE_GRAB_PX:
                    return n, "left"
                if abs(x - right_x) <= EDGE_GRAB_PX:
                    return n, "right"
                if left_x < x < right_x:
                    return n, "body"

        return None, None

    def erase_note_at(self, pos):
        x, y = pos

        if y < GRID_Y or x < KEY_AREA_WIDTH:
            return

        row = self.screen_y_to_row(y)

        if not (0 <= row < TOTAL_ROWS):
            return

        pitch = row_to_pitch(row)
        step = int(self.screen_x_to_step(x))

        note = self.note_at(pitch, step)

        if note is not None:
            self.get_current_notes().discard(note)
            self.selected_notes.discard(note)

    def note_at(self, pitch, step):
        for n in self.get_current_notes():
            npitch, nstart, nlen = n
            if npitch == pitch and nstart <= step < nstart + nlen:
                return n
        return None

    def overlaps(self, pitch, start, length, exclude=None):
        for n in self.get_current_notes():
            if exclude is not None:
                if isinstance(exclude, set):
                    if n in exclude:
                        continue
                elif n == exclude:
                    continue

            npitch, nstart, nlen = n

            if npitch != pitch:
                continue

            if start < nstart + nlen and start + length > nstart:
                return True

        return False

    def add_note(self, pitch, step, audition=True):
        """
        Add a normal piano/synth note or a pitched drum note.

        Drum notes are stored in the currently selected drum part.
        Their MIDI pitch controls the drum sample's pitch.
        """

        step = max(0, min(step, self.total_steps - 1))

        # ----------------------------------------------------------
        # DRUM TRACK
        # ----------------------------------------------------------
        if getattr(self.track, "is_drum_track", False):

            part = self.track.current_part

            if part not in self.track.parts:
                return

            notes = self.track.parts[part]

            # Prevent two notes on the exact same pitch/step.
            for note in notes:
                npitch, nstart, nlen = note

                if npitch == pitch and nstart == step:
                    return

            self.save_undo_state()

            notes.add(
                (pitch, step, 1)
            )

            if audition:
                self.preview_grid_note(pitch)

            return

        # ----------------------------------------------------------
        # NORMAL PIANO / SYNTH TRACK
        # ----------------------------------------------------------

        max_length = min(
            DEFAULT_NOTE_LEN_STEPS,
            self.total_steps - step
        )

        for n in self.get_current_notes():
            npitch, nstart, nlen = n

            if npitch != pitch:
                continue

            if nstart <= step < nstart + nlen:
                return

            if nstart > step:
                max_length = min(
                    max_length,
                    nstart - step
                )

        length = max(1, max_length)

        if length <= 0:
            return

        self.save_undo_state()

        self.get_current_notes().add(
            (pitch, step, length)
        )

        if audition:
            self.preview_grid_note(pitch)

    def add_measure(self):
        if self.num_measures < MAX_MEASURES:
            self.num_measures += 1

    def remove_measure(self):
        if self.num_measures > MIN_MEASURES:
            new_total = (self.num_measures - 1) * STEPS_PER_MEASURE

            for t in self.tracks:
                t.notes = {n for n in t.notes if n[1] < new_total}

            self.selected_notes = {n for n in self.selected_notes if n[1] < new_total}
            self.num_measures -= 1
            self.scroll_x = min(self.scroll_x, self.max_scroll_x)

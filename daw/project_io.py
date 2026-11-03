"""Project save / load (.pysynth JSON files)."""

import json
import os
import tkinter as tk
from tkinter import filedialog

from .config import *
from .tracks import Track, DrumTrack


class ProjectIOMixin:
    @staticmethod
    def _file_dialog_root():
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        return root

    def save_project(self):
        root = self._file_dialog_root()
        initial = os.path.basename(self.current_file) if self.current_file else "MySynthProject.pysynth"
        path = filedialog.asksaveasfilename(
            parent=root,
            title="Save pysynth project",
            defaultextension=".pysynth",
            initialfile=initial,
            filetypes=[("pysynth project", "*.pysynth"), ("JSON", "*.json"), ("All files", "*.*")],
        )
        root.destroy()

        if not path:
            return

        data = {
            "format": "pysynth",
            "version": 1,
            "bpm": self.bpm,
            "num_measures": self.num_measures,
            "tracks": [],
        }

        for track in self.tracks:
            track_data = {
                "id": track.id,
                "name": track.name,
                "track_type": getattr(track, "track_type", "drum" if getattr(track, "is_drum_track", False) else "instrument"),
                "instrument": track.instrument,
                "sound": track.sound,
                "waveform": track.engine.waveform_name,
            }

            if getattr(track, "is_drum_track", False):
                track_data["drum_parts"] = {
                    part_name: [list(note) for note in sorted(notes)]
                    for part_name, notes in track.parts.items()
                }
            else:
                track_data["eq"] = {
                    "bass": track.eq.bass_gain,
                    "mid": track.eq.mid_gain,
                    "treble": track.eq.treble_gain,
                }
                track_data["notes"] = [list(n) for n in sorted(track.notes)]

            data["tracks"].append(track_data)

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            self.current_file = path
            self.set_status(f"Saved: {os.path.basename(path)}")
        except OSError as exc:
            self.set_status(f"Save failed: {exc}", error=True)

    def load_project(self):
        root = self._file_dialog_root()
        path = filedialog.askopenfilename(
            parent=root,
            title="Load pysynth project",
            filetypes=[("pysynth project", "*.pysynth"), ("JSON", "*.json"), ("All files", "*.*")],
        )
        root.destroy()

        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("format") != "pysynth":
                raise ValueError("Not a pysynth project file.")

            loaded_tracks = []
            for td in data.get("tracks", []):
                track_type = td.get("track_type", "instrument")

                if track_type == "drum":
                    track = DrumTrack(name=td.get("name") or "Drums")
                    saved_parts = td.get("drum_parts", {})
                    for part_name in track.parts:
                        track.parts[part_name] = {
                            (int(n[0]), int(n[1]), int(n[2]))
                            for n in saved_parts.get(part_name, [])
                            if len(n) == 3
                        }
                else:
                    track = Track(
                        name=td.get("name"),
                        waveform=td.get("waveform", "saw"),
                        instrument=td.get("instrument", "Piano"),
                        sound=td.get("sound", "Grand Piano"),
                        track_id=td.get("id"),
                        track_type="custom" if track_type == "custom" else "instrument",
                    )
                    track.notes = {
                        (int(n[0]), int(n[1]), int(n[2]))
                        for n in td.get("notes", [])
                        if len(n) == 3
                    }
                    eq_data = td.get("eq", {})
                    track.eq.bass_gain = float(eq_data.get("bass", 1.0))
                    track.eq.mid_gain = float(eq_data.get("mid", 1.0))
                    track.eq.treble_gain = float(eq_data.get("treble", 1.0))

                loaded_tracks.append(track)

            if not loaded_tracks:
                loaded_tracks = [Track(waveform="saw")]

            self.tracks = loaded_tracks
            self.drum_track = next(
                (track for track in self.tracks if getattr(track, "is_drum_track", False)),
                None,
            )
            self.current_track_index = 0
            self.selected_notes = set()
            self.bpm = max(20, min(300, int(data.get("bpm", 120))))
            self.num_measures = max(
                MIN_MEASURES,
                min(MAX_MEASURES, int(data.get("num_measures", INITIAL_MEASURES))),
            )

            self.current_file = path
            self.play_pos_seconds = 0.0
            for t in self.tracks:
                t.engine.all_notes_off()
                t.sounding.clear()

            self.set_status(f"Loaded: {os.path.basename(path)}")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self.set_status(f"Load failed: {exc}", error=True)

"""Resource path helper that works from source and from a PyInstaller bundle."""

import os
import sys

# The project root is the folder that contains piano_roll.py, Samples/ and
# MusicApp.ico (one level above this package).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative):
    base = getattr(sys, "_MEIPASS", PROJECT_ROOT)
    return os.path.join(base, relative)

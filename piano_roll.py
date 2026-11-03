"""Entry point for the piano-roll app.

The implementation lives in the daw/ package (see daw/app.py).
Kept as a thin launcher so `python piano_roll.py` and piano_roll.spec
(PyInstaller) keep working unchanged.
"""

from daw.app import PianoRollApp

if __name__ == "__main__":
    PianoRollApp().run()

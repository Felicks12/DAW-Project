"""
main.py

Run this to start the synth. It will:
  1. Try to find a connected MIDI input device and let you play it live.
  2. If no MIDI device is found, fall back to a QWERTY "keyboard as piano"
     mode using your computer keyboard.

Usage:
    python main.py                  # auto-detect MIDI, else QWERTY fallback
    python main.py --list-midi      # list available MIDI input ports
    python main.py --midi "port name"   # force a specific MIDI port
    python main.py --qwerty         # force QWERTY mode even if MIDI exists
    python main.py --waveform saw   # sine | square | saw | triangle
"""

import argparse
import sys
import time

import numpy as np
import sounddevice as sd

from synth_engine import SynthEngine, SAMPLE_RATE, WAVEFORMS

BLOCK_SIZE = 256  # smaller = lower latency, higher CPU load


def run_audio_stream(engine: SynthEngine):
    def callback(outdata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        samples = engine.render(frames)
        outdata[:, 0] = samples

    stream = sd.OutputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        channels=1,
        dtype="float32",
        callback=callback,
    )
    stream.start()
    return stream


def run_midi_mode(engine: SynthEngine, port_name=None):
    try:
        import mido
    except ImportError:
        print("mido/python-rtmidi not installed — skipping MIDI detection.")
        return False

    available = mido.get_input_names()
    if not available:
        print("No MIDI input ports found.")
        return False

    if port_name is None:
        port_name = available[0]
    elif port_name not in available:
        print(f"Port '{port_name}' not found. Available ports: {available}")
        return False

    print(f"Listening on MIDI port: {port_name}")
    print("Play your MIDI controller. Ctrl+C to quit.\n")

    with mido.open_input(port_name) as inport:
        try:
            for msg in inport:
                if msg.type == "note_on" and msg.velocity > 0:
                    engine.note_on(msg.note, msg.velocity)
                elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                    engine.note_off(msg.note)
        except KeyboardInterrupt:
            pass
    return True


def run_qwerty_mode(engine: SynthEngine):
    from pynput import keyboard

    # Map a row of QWERTY keys to a chromatic scale starting at C4 (MIDI 60)
    key_to_note = {
        "a": 60, "w": 61, "s": 62, "e": 63, "d": 64, "f": 65,
        "t": 66, "g": 67, "y": 68, "h": 69, "u": 70, "j": 71,
        "k": 72, "o": 73, "l": 74, "p": 75, ";": 76,
    }

    print("QWERTY keyboard mode.")
    print("Keys a,w,s,e,d,f,t,g,y,h,u,j,k,o,l,p,; play a chromatic scale from C4.")
    print("Esc to quit.\n")

    pressed = set()

    def on_press(key):
        try:
            k = key.char
        except AttributeError:
            if key == keyboard.Key.esc:
                return False
            return
        if k in key_to_note and k not in pressed:
            pressed.add(k)
            engine.note_on(key_to_note[k], velocity=100)

    def on_release(key):
        try:
            k = key.char
        except AttributeError:
            return
        if k in key_to_note and k in pressed:
            pressed.discard(k)
            engine.note_off(key_to_note[k])

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


def main():
    parser = argparse.ArgumentParser(description="Minimal polyphonic Python synth")
    parser.add_argument("--list-midi", action="store_true", help="List MIDI input ports and exit")
    parser.add_argument("--midi", type=str, default=None, help="Force a specific MIDI port name")
    parser.add_argument("--qwerty", action="store_true", help="Force QWERTY mode")
    parser.add_argument(
        "--waveform", type=str, default="saw", choices=list(WAVEFORMS.keys()),
        help="Oscillator waveform (default: saw)",
    )
    parser.add_argument("--attack", type=float, default=0.01)
    parser.add_argument("--decay", type=float, default=0.15)
    parser.add_argument("--sustain", type=float, default=0.6)
    parser.add_argument("--release", type=float, default=0.3)
    args = parser.parse_args()

    if args.list_midi:
        import mido
        ports = mido.get_input_names()
        if not ports:
            print("No MIDI input ports found.")
        else:
            print("Available MIDI input ports:")
            for p in ports:
                print(f"  - {p}")
        return

    engine = SynthEngine(
        waveform=args.waveform,
        adsr_params=dict(
            attack=args.attack, decay=args.decay,
            sustain=args.sustain, release=args.release,
        ),
    )

    stream = run_audio_stream(engine)
    print(f"Audio stream started ({SAMPLE_RATE} Hz, waveform={args.waveform}).")

    try:
        if args.qwerty:
            run_qwerty_mode(engine)
        else:
            ok = run_midi_mode(engine, args.midi)
            if not ok:
                print("Falling back to QWERTY mode.\n")
                run_qwerty_mode(engine)
    finally:
        stream.stop()
        stream.close()


if __name__ == "__main__":
    main()
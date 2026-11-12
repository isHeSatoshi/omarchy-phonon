#!/usr/bin/env python3
"""Local-only bridge to Phonon's native StatusNotifierItem and menu."""

import json
import math
import os
from pathlib import Path
import subprocess
import sys

MODES = ("minimal", "casual", "formal", "prompt")
MAX_HISTORY_BYTES = 65536
MAX_TEXT = 4000


def run(*args, input=None):
    return subprocess.run(
        args, input=input, capture_output=True, text=True, check=True, timeout=3
    ).stdout.strip()


def data_root():
    explicit = os.environ.get("PHONON_WIN_HOME")
    if explicit:
        return Path(explicit).absolute()
    base = Path(os.environ.get("XDG_DATA_HOME", ""))
    if not base.is_absolute():
        base = Path.home() / ".local/share"
    return base / "phonon"


def small_text(path):
    try:
        with path.open("r", encoding="utf-8") as stream:
            return stream.read(MAX_HISTORY_BYTES)
    except (OSError, UnicodeError):
        return ""


def preferences(root):
    try:
        settings = json.loads(small_text(root / "settings.json"))
    except ValueError:
        settings = {}
    if not isinstance(settings, dict):
        settings = {}
    if "writing_style" in settings:
        mode = settings["writing_style"]
    else:
        mode = small_text(root / "writing_mode.txt").strip().lower()
    if not isinstance(mode, str) or mode.strip().lower() not in MODES:
        mode = "minimal"
    else:
        mode = mode.strip().lower()
    if "local_history" in settings:
        history = settings["local_history"] is True
    else:
        history = small_text(root / "history.txt").strip().lower() in (
            "on", "true", "1", "yes"
        )
    return mode, history


def last_dictation(root, enabled):
    # Never open the history log when the user has not opted in.
    if not enabled:
        return "", 0
    try:
        with (root / "history.jsonl").open("rb") as stream:
            start = max(0, stream.seek(0, 2) - MAX_HISTORY_BYTES)
            stream.seek(start)
            if start:
                stream.readline(MAX_HISTORY_BYTES)
            lines = stream.read(MAX_HISTORY_BYTES).splitlines()
    except OSError:
        return "", 0
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except (ValueError, UnicodeError):
            continue
        if not isinstance(entry, dict):
            continue
        text = entry.get("final")
        if not isinstance(text, str) or not text.strip():
            continue
        duration = entry.get("duration_s", 0)
        if not isinstance(duration, (int, float)) or not math.isfinite(duration):
            duration = 0
        return text[:MAX_TEXT], round(max(0, duration), 1)
    return "", 0


def find_service():
    for line in run("busctl", "--user", "list", "--no-pager", "--no-legend").splitlines():
        fields = line.split()
        if (fields and fields[0].startswith("org.kde.StatusNotifierItem-")
                and any("phonon" in field.lower() for field in fields[1:])):
            return fields[0]
    return None


def dbus_json(*args):
    return json.loads(run("busctl", "--user", "--json=short", *args))["data"]


def tooltip(service):
    data = dbus_json("get-property", service, "/StatusNotifierItem",
                     "org.kde.StatusNotifierItem", "ToolTip")
    return data[-1][:512] if isinstance(data, list) and isinstance(data[-1], str) else ""


def menu_entries(layout, depth=0):
    if depth > 8 or not isinstance(layout, list) or len(layout) != 3:
        return
    item, props, children = layout
    if type(item) is int and isinstance(props, dict):
        yield item, props
    if isinstance(children, list):
        for child in children[:256]:
            if isinstance(child, dict):
                yield from menu_entries(child.get("data"), depth + 1)


def choose_mode(service, mode):
    if mode not in MODES:
        raise ValueError("Unknown writing mode")
    layout = dbus_json("call", service, "/MenuBar", "com.canonical.dbusmenu",
                       "GetLayout", "iias", "0", "3", "0")[1]
    label = "Minimal (default)" if mode == "minimal" else mode.title()
    for item, props in menu_entries(layout):
        if props.get("label", {}).get("data") == label:
            # Let Phonon persist the preference, supporting old and new formats.
            run("busctl", "--user", "call", service, "/MenuBar",
                "com.canonical.dbusmenu", "Event", "isvu",
                str(item), "clicked", "i", "0", "0")
            return
    raise ValueError("Phonon did not expose that writing mode")


def microphone():
    name, muted, volume = "Default microphone", False, 0
    try:
        text = run("wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@")
        muted = "[MUTED]" in text
        volume = round(float(text.split()[1]) * 100)
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        pass
    try:
        default = run("pactl", "get-default-source")
        sources = json.loads(run("pactl", "-f", "json", "list", "sources"))
        source = next((s for s in sources if s.get("name") == default), {})
        description = source.get("description")
        if isinstance(description, str):
            name = description[:160]
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        pass
    return name, muted, max(0, min(200, volume))


def get_status(root=None):
    root = data_root() if root is None else root
    mode, history = preferences(root)
    text, duration = last_dictation(root, history)
    name, muted, volume = microphone()
    return dict(mode=mode, history_enabled=history, last_text=text,
                last_duration=duration, mic_name=name,
                mic_muted=muted, mic_volume=volume)


def action(args):
    command = args[0] if args else "status"
    if command == "status":
        return get_status()
    if command == "copy_last":
        _, history = preferences(data_root())
        text, _ = last_dictation(data_root(), history)
        if text:
            # Dictation never appears in another process's command line.
            run("wl-copy", input=text)
    elif command == "open_dir":
        run("xdg-open", str(data_root()))
    elif command == "unmute":
        run("wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "0")
    elif command in ("toggle", "set_mode"):
        if command == "set_mode" and (len(args) != 2 or args[1] not in MODES):
            raise ValueError("Unknown writing mode")
        service = find_service()
        if not service:
            raise ValueError("Start Phonon before using dictation controls")
        if command == "set_mode":
            choose_mode(service, args[1])
        elif not tooltip(service).lower().startswith("transcribing"):
            run("busctl", "--user", "call", service, "/StatusNotifierItem",
                "org.kde.StatusNotifierItem", "Activate", "ii", "0", "0")
    else:
        raise ValueError("Unknown action")
    return {"ok": True}


if __name__ == "__main__":
    try:
        print(json.dumps(action(sys.argv[1:]), allow_nan=False))
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        print(json.dumps({"error": "Phonon action unavailable. Check Phonon and the required tools."}))
        sys.exit(1)

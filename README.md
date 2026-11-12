# Phonon for Omarchy

A small, unofficial [Omarchy Quattro](https://omarchy.org/) tray panel for
[Phonon](https://github.com/Infatoshi/phonon), the local dictation app.

- Live listening, transcription, and ready status from Phonon's D-Bus tray item.
- Start/stop controls and Phonon's four native writing modes.
- Default microphone name and an explicit unmute button.
- Last saved dictation and copy, **only when local history is already enabled**.
- Omarchy colors, sizing, and language fallback.

This is a tray panel, not a speech engine. Install Phonon separately. The
native floating dictation indicator is a separate upstream contribution, not a
second bar icon bundled here.

## Requirements

- Omarchy Quattro with its Quickshell plugin API (`qs.Ui`, `qs.Commons`).
- Phonon's Linux tray app running on the same user's D-Bus session.
- Python 3 (standard library only) and `busctl` from systemd.
- PipeWire/WirePlumber `wpctl` and PulseAudio-compatible `pactl` for mic details.
- `wl-copy` from `wl-clipboard` for the explicit copy button.
- `xdg-open` from `xdg-utils` for the data-folder button.

No Python packages, API keys, remote services, custom systemd unit, or helper
installed into `~/.local/bin` are required. Unsupported mic details degrade
gracefully; the tray can still show Phonon's state.

## Install

Review this repository, then run:

```sh
omarchy plugin add https://github.com/isHeSatoshi/omarchy-phonon --enable
```

The default placement is the right side of the bar. Choose another placement
in Omarchy's bar settings. If you want to hide Phonon's original tray item,
do that explicitly in Omarchy's tray settings; installation does not hide it.

Click the plugin to open controls. Right-click to toggle dictation.
Phonon's stock Linux dictation key is Right Ctrl; a key you selected in Phonon
continues to work unchanged.

## Defaults and privacy

Installation does **not** start/stop services, install keyboard hooks, bind
Caps Lock or Right Alt, change clipboard rules, enable history, change models,
select a GPU, or rewrite Phonon or Omarchy configuration.

Live state comes from the native tray. While the panel is open, a short-lived
local helper reads mic information, writing mode, and optional history every
1.5 seconds. It does not poll history while the panel is closed, capture audio,
make network requests, or send dictation anywhere. The history preview is
bounded to the last 64 KiB of the log and 4,000 displayed characters.
Copy places that preview on the clipboard only when clicked, using stdin,
not a process argument.

Writing-mode changes go through Phonon's own D-Bus menu, so Phonon owns
validation and persistence. Merely opening the panel writes no settings.
Both modern `settings.json` and the older `history.txt`/`writing_mode.txt`
read formats are supported.

Data paths follow Phonon: `PHONON_WIN_HOME` when set, otherwise
`$XDG_DATA_HOME/phonon` or `~/.local/share/phonon`. Set overrides in the desktop
environment as well as Phonon's environment if you use a custom data directory.

Plugins run unsandboxed in the shell. Review the code before enabling any
plugin. All displayed external text is plain text.

## Update, disable, and remove

```sh
omarchy plugin update io.github.ishesatoshi.phonon
omarchy plugin disable io.github.ishesatoshi.phonon
omarchy plugin remove io.github.ishesatoshi.phonon
```

Removal removes only the plugin. It does not uninstall Phonon, delete models,
clear history, or alter shortcuts.

## Development

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile status.py
omarchy plugin validate /absolute/path/to/omarchy-phonon
```

The tests use temporary data and mocked commands, never your saved dictations.
English strings live in `i18n/en.json`; Omarchy's language fallback allows
additional translations without a shell restart.

## License

MIT, see [LICENSE](LICENSE). Phonon is a separate project under its own license.
The plugin resolves Phonon's installed icon at runtime, with a text fallback;
no upstream artwork, audio, model weights, or personal data is redistributed.
This plugin is not endorsed by the Phonon or Omarchy maintainers.

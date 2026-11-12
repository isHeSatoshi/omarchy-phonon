import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("status", ROOT / "status.py")
status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status)


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, value):
        (self.root / name).write_text(value)

    def test_stock_defaults_do_not_create_files(self):
        self.assertEqual(status.preferences(self.root), ("minimal", False))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_history_off_does_not_open_the_log(self):
        with patch.object(Path, "open", side_effect=AssertionError("read private data")):
            self.assertEqual(status.last_dictation(self.root, False), ("", 0))

    def test_modern_preferences_override_legacy(self):
        self.write("history.txt", "on")
        self.write("writing_mode.txt", "formal")
        self.write("settings.json", '{"local_history":false,"writing_style":"casual"}')
        self.assertEqual(status.preferences(self.root), ("casual", False))

    def test_legacy_preferences_remain_supported(self):
        self.write("history.txt", "on")
        self.write("writing_mode.txt", "formal")
        self.assertEqual(status.preferences(self.root), ("formal", True))

    def test_invalid_settings_types_fail_closed(self):
        for value in ("[]", '"unexpected"', '{"local_history":"true","writing_style":[]}'):
            self.write("settings.json", value)
            self.assertEqual(status.preferences(self.root), ("minimal", False))

    def test_untrusted_dictation_is_bounded_and_not_interpreted(self):
        text = '<img src="https://example.invalid/tracker">' + "x" * 5000
        self.write("history.jsonl", json.dumps({"final": text, "duration_s": float("nan")}) + "\nbroken")
        result, duration = status.last_dictation(self.root, True)
        self.assertEqual(result, text[:4000])
        self.assertEqual(duration, 0)

    def test_large_history_uses_latest_complete_entry(self):
        self.write("history.jsonl", json.dumps({"final": "x" * 70000}) + "\n"
                   + json.dumps({"final": "latest", "duration_s": 2.5}) + "\n")
        self.assertEqual(status.last_dictation(self.root, True), ("latest", 2.5))

    def test_invalid_history_records_are_skipped(self):
        self.write("history.jsonl", '[]\nnull\n{"final":19}\n{"final":"ok"}')
        self.assertEqual(status.last_dictation(self.root, True), ("ok", 0))

    def test_data_paths_follow_upstream(self):
        with patch.dict(os.environ, {"PHONON_WIN_HOME": str(self.root)}, clear=True):
            self.assertEqual(status.data_root(), self.root)
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(self.root)}, clear=True):
            self.assertEqual(status.data_root(), self.root / "phonon")
        with patch.dict(os.environ, {"XDG_DATA_HOME": "relative"}, clear=True):
            self.assertEqual(status.data_root(), Path.home() / ".local/share/phonon")

    def test_mode_changes_use_native_menu(self):
        layout = [1, [0, {}, [{"data": [42, {"label": {"data": "Formal"}}, []]}]]]
        with patch.object(status, "dbus_json", return_value=layout), patch.object(status, "run") as run:
            status.choose_mode("test.service", "formal")
        self.assertIn("Event", run.call_args.args)
        self.assertIn("42", run.call_args.args)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_invalid_mode_never_reaches_dbus(self):
        with patch.object(status, "run") as run:
            with self.assertRaises(ValueError):
                status.action(["set_mode", "formal; arbitrary-command"])
            run.assert_not_called()

    def test_transcribing_toggle_is_ignored(self):
        with patch.object(status, "find_service", return_value="test.service"), \
                patch.object(status, "tooltip", return_value="transcribing"), \
                patch.object(status, "run") as run:
            status.action(["toggle"])
            run.assert_not_called()

    def test_clipboard_text_uses_stdin_not_argv(self):
        self.write("history.txt", "on")
        self.write("history.jsonl", '{"final":"synthetic fixture"}')
        with patch.object(status, "data_root", return_value=self.root), patch.object(status, "run") as run:
            status.action(["copy_last"])
        run.assert_called_once_with("wl-copy", input="synthetic fixture")

    def test_all_text_widgets_are_plain_and_no_personal_shortcuts_are_shipped(self):
        qml = (ROOT / "Panel.qml").read_text()
        import re
        for body in re.findall(r"\bText\s*\{([^{}]*)\}", qml, re.S):
            self.assertIn("textFormat: Text.PlainText", body)
        self.assertNotIn("Caps Lock", qml)
        self.assertNotIn("Right Alt", qml)
        self.assertNotIn("/home/", qml)
        self.assertNotIn("~/.local/bin", (ROOT / "status.py").read_text())


if __name__ == "__main__":
    unittest.main()

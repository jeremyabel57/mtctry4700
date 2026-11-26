import ctypes
import runpy
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import call, patch

import main
import wincanvas
import winmain


class DependencyInstallationTests(unittest.TestCase):
	def test_install_dependencies_uses_current_interpreter(self):
		with patch("main.subprocess.run") as run:
			main.install_dependencies()
		requirements = Path(main.__file__).resolve().with_name("requirements.txt")
		run.assert_called_once_with(
			[sys.executable, "-m", "pip", "install", "-r", str(requirements)], check=True
		)

	def test_main_setup_creates_three_tabs(self):
		with patch.object(main, "loop", []):
			with patch("main.MainWindow") as window_class:
				window = main.main_setup()
				window_class.assert_called_once_with()
				self.assertEqual(window.add_tab.call_args_list, [
					call("Tab 1", canvas_width=640, canvas_height=480, mode=wincanvas.ViewportMode.MIN),
					call("Tab 2", canvas_width=640, canvas_height=480),
					call("Tab 3", canvas_width=640, canvas_height=480)])
				viewport = window.add_tab.return_value
				viewport.add_webview.assert_called_once_with(
					width=viewport.canvas_width, height=viewport.canvas_height, url="http://google.com")
				window.select_tab.assert_called_once_with(0)
				window.set_visible.assert_called_once_with(True)
				self.assertEqual(main.loop, [window.loop])

	def test_main_setup_closes_window_if_tab_creation_fails(self):
		with patch.object(main, "loop", []):
			with patch("main.MainWindow") as window_class:
				window_class.return_value.add_tab.side_effect = RuntimeError("tab failed")
				with self.assertRaisesRegex(RuntimeError, "tab failed"):
					main.main_setup()
				window_class.return_value.close.assert_called_once_with()
				self.assertEqual(main.loop, [])

	def test_main_setup_closes_window_if_webview_creation_fails(self):
		with patch.object(main, "loop", []):
			with patch("main.MainWindow") as window_class:
				window = window_class.return_value
				window.add_tab.return_value.add_webview.side_effect = RuntimeError("webview failed")
				with self.assertRaisesRegex(RuntimeError, "webview failed"):
					main.main_setup()
				window.close.assert_called_once_with()
				self.assertEqual(main.loop, [])

	def test_main_setup_opens_three_viewports(self):
		with patch.object(main, "loop", []):
			window = main.main_setup()
			try:
				self.assertEqual(len(window.viewports), 3)
				self.assertEqual([viewport.original_canvas_size for viewport in window.viewports],
					[(640, 480)] * 3)
				viewport = window.viewports[0]
				self.assertEqual(viewport.mode, wincanvas.ViewportMode.MIN)
				self.assertEqual(viewport._canvas_size(320, 240), (640, 480))
				self.assertEqual(viewport._canvas_size(800, 600), (800, 600))
				self.assertEqual(len(viewport.controls), 1)
				browser = viewport.controls[0]["webview"]
				canvas_rect = wincanvas.wintypes.RECT()
				host_rect = wincanvas.wintypes.RECT()
				for width, height, zoom in ((800, 600, 1.0), (2200, 1500, 0.5), (500, 400, 1.5)):
					viewport.resize(width, height)
					viewport.zoom = zoom
					self.assertTrue(wincanvas.user32.GetClientRect(viewport.canvas, ctypes.byref(canvas_rect)))
					self.assertTrue(wincanvas.user32.GetWindowRect(browser.host_hwnd, ctypes.byref(host_rect)))
					origin = wincanvas.wintypes.POINT(host_rect.left, host_rect.top)
					self.assertTrue(wincanvas.user32.ScreenToClient(viewport.canvas, ctypes.byref(origin)))
					self.assertEqual((origin.x, origin.y), (0, 0))
					self.assertEqual((host_rect.right - host_rect.left, host_rect.bottom - host_rect.top),
						(canvas_rect.right, canvas_rect.bottom))
				self.assertEqual(winmain.user32.SendMessageW(window.tab_hwnd, winmain.TCM_GETCURSEL, 0, 0), 0)
				for index, viewport in enumerate(window.viewports):
					self.assertEqual(bool(winmain.user32.IsWindowVisible(viewport.hwnd)), index == 0)
					label = ctypes.create_unicode_buffer(32)
					item = winmain.TCITEM()
					item.mask = winmain.TCIF_TEXT
					item.pszText = ctypes.cast(label, ctypes.c_wchar_p)
					item.cchTextMax = len(label)
					self.assertTrue(winmain.user32.SendMessageW(window.tab_hwnd, winmain.TCM_FIRST + 60,
						index, ctypes.addressof(item)))
					self.assertEqual(label.value, f"Tab {index + 1}")
				self.assertTrue(window.loop())
			finally:
				window.close()
			self.assertFalse(main.loop[0]())

	def test_startup_installs_before_creating_window(self):
		operations = []
		with patch("subprocess.run", side_effect=lambda *args, **kwargs: operations.append("install")):
			with patch("winmain.MainWindow") as window:
				window.side_effect = lambda: operations.append("window") or window.return_value
				window.return_value.loop.return_value = False
				runpy.run_path(main.__file__, run_name="__main__")
		self.assertEqual(operations, ["install", "window"])

	def test_startup_stops_if_installation_fails(self):
		error = subprocess.CalledProcessError(1, "pip")
		with patch("subprocess.run", side_effect=error):
			with patch("winmain.MainWindow") as window:
				with self.assertRaises(subprocess.CalledProcessError):
					runpy.run_path(main.__file__, run_name="__main__")
				window.assert_not_called()


if __name__ == "__main__":
	unittest.main()
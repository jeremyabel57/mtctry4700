import ctypes
import time
import unittest
from ctypes import wintypes
from unittest.mock import patch

import wincanvas
import winmain


user32 = winmain.user32
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL


class MainWindowTests(unittest.TestCase):
	def bounds(self, parent, hwnd):
		rect = wintypes.RECT()
		self.assertTrue(user32.GetWindowRect(hwnd, ctypes.byref(rect)))
		point = wintypes.POINT(rect.left, rect.top)
		self.assertTrue(user32.ScreenToClient(parent, ctypes.byref(point)))
		return point.x, point.y, rect.right - rect.left, rect.bottom - rect.top

	def tab_content_bounds(self, window):
		rect = wintypes.RECT()
		self.assertTrue(user32.GetClientRect(window.tab_hwnd, ctypes.byref(rect)))
		user32.SendMessageW(window.tab_hwnd, winmain.TCM_ADJUSTRECT, 0, ctypes.addressof(rect))
		return rect.left, rect.top, max(0, rect.right - rect.left), max(0, rect.bottom - rect.top)

	def test_tab_selection_and_resize(self):
		window = winmain.MainWindow(width=700, height=500)
		try:
			first = window.add_tab("First")
			second = window.add_tab("Second")
			self.assertEqual(user32.GetParent(first.hwnd), window.tab_hwnd)
			self.assertEqual(user32.GetParent(second.hwnd), window.tab_hwnd)
			window.set_visible(True)
			self.assertFalse(user32.IsWindowVisible(first.hwnd))
			self.assertTrue(user32.IsWindowVisible(second.hwnd))
			self.assertEqual(self.bounds(window.tab_hwnd, second.hwnd), self.tab_content_bounds(window))

			user32.SendMessageW(window.tab_hwnd, winmain.TCM_SETCURSEL, 0, 0)
			notification = winmain.NMHDR(window.tab_hwnd, 0, ctypes.c_uint(winmain.TCN_SELCHANGE).value)
			user32.SendMessageW(window.hwnd, winmain.WM_NOTIFY, 0, ctypes.addressof(notification))
			self.assertTrue(user32.IsWindowVisible(first.hwnd))
			self.assertFalse(user32.IsWindowVisible(second.hwnd))
			self.assertEqual(self.bounds(window.tab_hwnd, first.hwnd), self.tab_content_bounds(window))
			self.assertTrue(user32.MoveWindow(window.hwnd, 100, 100, 900, 600, True))
			self.assertEqual(self.bounds(window.tab_hwnd, first.hwnd), self.tab_content_bounds(window))
			window.select_tab(1)
			self.assertEqual(self.bounds(window.tab_hwnd, second.hwnd), self.tab_content_bounds(window))
			self.assertTrue(user32.IsWindowVisible(second.hwnd))
			self.assertFalse(user32.IsWindowVisible(first.hwnd))

			client = wintypes.RECT()
			self.assertTrue(user32.GetClientRect(window.hwnd, ctypes.byref(client)))
			tab = self.bounds(window.hwnd, window.tab_hwnd)
			status = self.bounds(window.hwnd, window.status_hwnd)
			self.assertEqual(tab, (0, 0, client.right, status[1]))
			self.assertEqual((status[0], status[2], status[1] + status[3]), (0, client.right, client.bottom))
			window.set_status("Ready")
			status_text = ctypes.create_unicode_buffer(32)
			user32.SendMessageW(window.status_hwnd, 0x040D, 0, ctypes.addressof(status_text))
			self.assertEqual(status_text.value, "Ready")
			with self.assertRaises(IndexError):
				window.select_tab(2)
		finally:
			window.close()
		self.assertFalse(user32.IsWindow(first.hwnd))
		self.assertFalse(user32.IsWindow(second.hwnd))
		self.assertFalse(window.loop())

	def test_viewport_wheel_messages_in_main_loop(self):
		window = winmain.MainWindow(width=400, height=300)
		try:
			viewport = window.add_tab("Scroll", canvas_width=1200, canvas_height=1000)
			button = viewport.add_control("BUTTON", "Test", x=100, y=100)
			window.set_visible(True)
			wparam = ((-120 & 0xFFFF) << 16)
			self.assertTrue(user32.PostMessageW(button, wincanvas.WM_MOUSEWHEEL, wparam, 0))
			self.assertTrue(window.loop())
			self.assertEqual(viewport._scroll_info(wincanvas.SB_VERT).nPos, 20)
		finally:
			window.close()

	def test_embedded_webview_wheel_in_main_loop(self):
		window = winmain.MainWindow(width=500, height=400)
		try:
			viewport = window.add_tab("Browser")
			browser = viewport.add_webview(x=20, y=20, width=250, height=180)
			window.set_visible(True)
			deadline = time.monotonic() + 15
			while not browser.ready and time.monotonic() < deadline:
				self.assertTrue(window.loop())
			self.assertTrue(browser.ready)
			wparam = (120 << 16) | wincanvas.MK_CONTROL
			self.assertTrue(user32.PostMessageW(browser.hwnd, wincanvas.WM_MOUSEWHEEL, wparam, 0))
			self.assertTrue(window.loop())
			self.assertEqual(viewport.zoom, 1.05)
		finally:
			window.close()

	def test_failed_tab_creation_is_rolled_back(self):
		window = winmain.MainWindow()
		try:
			with patch("winmain.Viewport", side_effect=ValueError("invalid viewport")):
				with self.assertRaisesRegex(ValueError, "invalid viewport"):
					window.add_tab("Invalid")
			self.assertEqual(window.viewports, [])
			self.assertEqual(user32.SendMessageW(window.tab_hwnd, winmain.TCM_FIRST + 4, 0, 0), 0)
		finally:
			window.close()

	def test_close_message_closes_child_viewports(self):
		window = winmain.MainWindow()
		first = window.add_tab("First")
		second = window.add_tab("Second")
		self.assertTrue(user32.PostMessageW(window.hwnd, 0x0010, 0, 0))
		self.assertFalse(window.loop())
		self.assertFalse(user32.IsWindow(first.hwnd))
		self.assertFalse(user32.IsWindow(second.hwnd))
		window.close()

	def test_quit_message_is_preserved(self):
		window = winmain.MainWindow()
		child = window.add_tab("Tab")
		user32.PostQuitMessage(37)
		try:
			self.assertFalse(window.loop())
			self.assertFalse(user32.IsWindow(child.hwnd))
		finally:
			message = wintypes.MSG()
			self.assertTrue(user32.PeekMessageW(ctypes.byref(message), None,
				winmain.WM_QUIT, winmain.WM_QUIT, winmain.PM_REMOVE))
		self.assertEqual((message.message, message.wParam), (winmain.WM_QUIT, 37))


if __name__ == "__main__":
	unittest.main()
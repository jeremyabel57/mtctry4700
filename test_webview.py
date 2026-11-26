import ctypes
import json
import threading
import time
import unittest
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from webview import WebView, WebViewControl
import wincanvas as win


user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ScreenToClient.restype = wintypes.BOOL


class PageHandler(BaseHTTPRequestHandler):
	def do_GET(self):
		body = f"<html><title>{self.path}</title><body>WebView test</body></html>".encode("utf-8")
		try:
			self.send_response(200)
			self.send_header("Content-Type", "text/html; charset=utf-8")
			self.send_header("Content-Length", str(len(body)))
			self.end_headers()
			self.wfile.write(body)
			if self.path in self.server.seen:
				self.server.seen[self.path].set()
		except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
			pass

	def log_message(self, format, *args):
		pass


class WebViewTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.server = ThreadingHTTPServer(("127.0.0.1", 0), PageHandler)
		cls.server.seen = {"/first": threading.Event(), "/second": threading.Event()}
		cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
		cls.server_thread.start()
		cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

	@classmethod
	def tearDownClass(cls):
		cls.server.shutdown()
		cls.server.server_close()
		cls.server_thread.join()

	def setUp(self):
		self.server.seen["/first"].clear()
		self.server.seen["/second"].clear()

	def pump_until(self, viewport, predicate):
		deadline = time.monotonic() + 15
		while not predicate() and time.monotonic() < deadline:
			self.assertTrue(viewport.loop())
		self.assertTrue(predicate(), "Timed out waiting for embedded WebView2")

	def bounds(self, parent, hwnd):
		rect = wintypes.RECT()
		self.assertTrue(user32.GetWindowRect(hwnd, ctypes.byref(rect)))
		point = wintypes.POINT(rect.left, rect.top)
		self.assertTrue(user32.ScreenToClient(parent, ctypes.byref(point)))
		return point.x, point.y, rect.right - rect.left, rect.bottom - rect.top

	def test_embedded_navigation_layout_and_delete(self):
		viewport = win.Viewport(width=500, height=400, canvas_width=1200, canvas_height=1000)
		try:
			browser = viewport.add_webview(x=40, y=50, width=300, height=180, url=self.base_url + "/first")
			browser.set_url(self.base_url + "/second")
			viewport.set_visible(True)
			self.pump_until(viewport, lambda: browser.loaded and self.server.seen["/second"].is_set())
			self.assertEqual(user32.GetParent(browser.hwnd), browser.host_hwnd)
			self.assertEqual(user32.GetParent(browser.host_hwnd), viewport.canvas)
			self.assertTrue(user32.IsWindowVisible(browser.hwnd))
			script = browser._control.ExecuteScriptAsync("document.title")
			self.pump_until(viewport, lambda: script.IsCompleted)
			self.assertEqual(json.loads(str(script.Result)), "/second")
			browser.set_url(self.base_url + "/first")
			self.assertFalse(browser.loaded)
			self.pump_until(viewport, lambda: browser.loaded and self.server.seen["/first"].is_set())
			script = browser._control.ExecuteScriptAsync("document.title")
			self.pump_until(viewport, lambda: script.IsCompleted)
			self.assertEqual(json.loads(str(script.Result)), "/first")
			self.assertEqual(viewport.controls[0]["webview"], browser)
			viewport.zoom = 1.5
			self.assertEqual(self.bounds(viewport.canvas, browser.host_hwnd), (60, 75, 450, 270))
			self.assertEqual(self.bounds(browser.host_hwnd, browser.hwnd), (0, 0, 450, 270))
			self.assertAlmostEqual(browser._control.ZoomFactor, 1.5)
			browser.resize(600, 300)
			self.assertEqual(self.bounds(viewport.canvas, browser.host_hwnd), (60, 75, 600, 300))
			self.assertEqual(self.bounds(browser.host_hwnd, browser.hwnd), (0, 0, 600, 300))
			self.assertEqual((viewport.controls[0]["width"], viewport.controls[0]["height"]), (400, 200))
			viewport.zoom = 1.0
			self.assertEqual(self.bounds(viewport.canvas, browser.host_hwnd), (40, 50, 400, 200))
			user32.SendMessageW(viewport.hwnd, win.WM_HSCROLL, win.SB_LINEDOWN, 0)
			user32.SendMessageW(viewport.hwnd, win.WM_VSCROLL, win.SB_LINEDOWN, 0)
			self.assertEqual(self.bounds(viewport.hwnd, viewport.canvas)[:2], (-20, -20))
			browser.set_visible(False)
			self.assertFalse(user32.IsWindowVisible(browser.hwnd))
			browser.set_visible(True)
			self.assertTrue(user32.IsWindowVisible(browser.hwnd))
			viewport.delete_control(browser)
			self.assertFalse(user32.IsWindow(browser.hwnd))
			self.assertFalse(user32.IsWindow(browser.host_hwnd))
			self.assertEqual(viewport.controls, [])
			self.assertFalse(browser.loop())
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_embedded_multiple_views_and_viewport_close(self):
		viewport = win.Viewport()
		first = viewport.add_webview(width=200, height=120)
		second = viewport.add_webview(x=220, width=200, height=120)
		try:
			viewport.set_visible(True)
			self.pump_until(viewport, lambda: first.ready and second.ready)
			first.close()
			self.assertEqual([entry["webview"] for entry in viewport.controls], [second])
			self.assertFalse(user32.IsWindow(first.host_hwnd))
			self.assertTrue(user32.IsWindow(second.hwnd))
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()
		self.assertTrue(second._closed)
		self.assertFalse(user32.IsWindow(second.hwnd))

	def test_embedded_close_before_initialization(self):
		viewport = win.Viewport()
		try:
			browser = viewport.add_webview(width=200, height=120)
			browser.close()
			self.assertEqual(viewport.controls, [])
			self.assertFalse(user32.IsWindow(browser.hwnd))
			self.assertTrue(viewport.loop())
			with self.assertRaises(RuntimeError):
				browser.set_url(self.base_url + "/first")
			replacement = viewport.add_webview(width=200, height=120, url=self.base_url + "/first")
			self.pump_until(viewport, lambda: replacement.loaded and self.server.seen["/first"].is_set())
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_embedded_creation_failure_cleans_canvas(self):
		viewport = win.Viewport()
		try:
			with patch("webview._webview2_types", side_effect=RuntimeError("WebView2 unavailable")):
				with self.assertRaisesRegex(RuntimeError, "WebView2 unavailable"):
					viewport.add_webview(width=200, height=120)
			self.assertEqual(viewport.controls, [])
			self.assertEqual(viewport._fonts, {})
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_embedded_initialization_error_can_be_removed(self):
		viewport = win.Viewport()
		try:
			browser = viewport.add_webview(width=200, height=120)
			browser._error = "simulated initialization failure"
			with self.assertRaisesRegex(RuntimeError, "simulated initialization failure"):
				viewport.loop()
			viewport.delete_control(browser)
			self.assertEqual(viewport.controls, [])
			self.assertFalse(user32.IsWindow(browser.hwnd))
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_embedded_min_mode_and_parent_validation(self):
		with self.assertRaises(ValueError):
			WebViewControl(0)
		viewport = win.Viewport(width=700, height=500, canvas_width=400, canvas_height=300,
			mode=win.ViewportMode.MIN)
		try:
			failures = []
			def create_on_wrong_thread():
				try:
					WebViewControl(viewport.canvas)
				except Exception as error:
					failures.append(error)
			thread = threading.Thread(target=create_on_wrong_thread)
			thread.start()
			thread.join(timeout=5)
			self.assertFalse(thread.is_alive())
			self.assertEqual(len(failures), 1)
			self.assertIsInstance(failures[0], RuntimeError)
			browser = viewport.add_webview(x=40, y=30, width=200, height=120)
			viewport.set_visible(True)
			self.pump_until(viewport, lambda: browser.ready)
			scale_x, scale_y = viewport._control_scales(viewport.zoom)
			self.assertEqual(self.bounds(viewport.canvas, browser.host_hwnd), (
				round(40 * scale_x), round(30 * scale_y), round(200 * scale_x), round(120 * scale_y)))
			viewport.mode = win.ViewportMode.FREE
			self.assertEqual(self.bounds(viewport.canvas, browser.host_hwnd), (40, 30, 200, 120))
			self.assertEqual(self.bounds(browser.host_hwnd, browser.hwnd), (0, 0, 200, 120))
			viewport.mode = win.ViewportMode.MIN
			self.assertEqual(self.bounds(viewport.canvas, browser.host_hwnd), (
				round(40 * scale_x), round(30 * scale_y), round(200 * scale_x), round(120 * scale_y)))
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_webview_control_with_native_parent(self):
		viewport = win.Viewport(width=500, height=400)
		try:
			host = viewport.add_control("STATIC", x=20, y=30, width=250, height=150)
			browser = WebViewControl(host, width=250, height=150, url=self.base_url + "/first")
			try:
				viewport.set_visible(True)
				self.pump_until(viewport, lambda: browser.loaded and self.server.seen["/first"].is_set())
				self.assertEqual(user32.GetParent(browser.hwnd), host)
				self.assertEqual(self.bounds(host, browser.hwnd), (0, 0, 250, 150))
				browser.resize(200, 100)
				self.assertEqual(self.bounds(host, browser.hwnd), (0, 0, 200, 100))
			finally:
				browser.close()
			self.assertFalse(user32.IsWindow(browser.hwnd))
			viewport.delete_control(host)
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_navigation_visibility_and_resize(self):
		with WebView(title="WebView Test", width=420, height=300, url=self.base_url + "/first") as browser:
			self.assertTrue(browser.loop())
			self.assertTrue(user32.IsWindow(browser.hwnd))
			self.assertFalse(user32.IsWindowVisible(browser.hwnd))
			self.assertTrue(self.server.seen["/first"].wait(15))
			browser.resize(500, 320)
			rect = wintypes.RECT()
			self.assertTrue(user32.GetWindowRect(browser.hwnd, ctypes.byref(rect)))
			self.assertEqual(browser._request("size"), [500, 320])
			self.assertGreater(rect.right - rect.left, 0)
			self.assertGreater(rect.bottom - rect.top, 0)
			browser.set_visible(True)
			self.assertTrue(user32.IsWindowVisible(browser.hwnd))
			browser.set_url(self.base_url + "/second")
			self.assertTrue(self.server.seen["/second"].wait(15))
			self.assertEqual(browser._request("current_url"), self.base_url + "/second")
			browser.set_visible(False)
			self.assertFalse(user32.IsWindowVisible(browser.hwnd))
		self.assertFalse(browser.loop())
		self.assertFalse(user32.IsWindow(browser.hwnd))
		browser.close()

	def test_multiple_windows_and_user_close(self):
		first = WebView(title="First WebView")
		second = None
		try:
			second = WebView(title="Second WebView")
			self.assertNotEqual(first.hwnd, second.hwnd)
			self.assertTrue(first.loop())
			self.assertTrue(second.loop())
			self.assertTrue(user32.PostMessageW(first.hwnd, 0x0010, 0, 0))
			first._process.wait(timeout=15)
			self.assertFalse(first.loop())
			self.assertTrue(second.loop())
			second.set_visible(True)
			self.assertTrue(user32.IsWindowVisible(second.hwnd))
		finally:
			first.close()
			if second is not None:
				second.close()

	def test_invalid_arguments_and_closed_window(self):
		with self.assertRaises(ValueError):
			WebView(width=0)
		with self.assertRaises(ValueError):
			WebView(url="")
		browser = WebView()
		try:
			with self.assertRaises(ValueError):
				browser.resize(0, 100)
			with self.assertRaises(ValueError):
				browser.set_url("")
			with self.assertRaises(RuntimeError):
				browser._request("invalid")
			self.assertTrue(browser.loop())
		finally:
			browser.close()
		with self.assertRaises(RuntimeError):
			browser.set_visible(True)


if __name__ == "__main__":
	unittest.main()
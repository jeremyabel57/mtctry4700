import copy
import ctypes
import struct
import unittest
import zlib
from ctypes import wintypes
from unittest.mock import patch

import wincanvas as win


user32 = win.user32
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = win.LRESULT
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ScreenToClient.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetDlgCtrlID.argtypes = [wintypes.HWND]
user32.GetDlgCtrlID.restype = ctypes.c_int
win.gdi32.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID]
win.gdi32.GetObjectW.restype = ctypes.c_int
win.gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
win.gdi32.CreateCompatibleDC.restype = wintypes.HDC
win.gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
win.gdi32.SelectObject.restype = wintypes.HANDLE
win.gdi32.GetPixel.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
win.gdi32.GetPixel.restype = wintypes.DWORD
win.gdi32.DeleteDC.argtypes = [wintypes.HDC]
win.gdi32.DeleteDC.restype = wintypes.BOOL


class ViewportTests(unittest.TestCase):
	def test_child_viewport_parent_resize_and_close(self):
		outer = win.Viewport(width=700, height=500)
		child = None
		try:
			child = win.Viewport(parent=outer.canvas, width=300, height=200)
			self.assertEqual(user32.GetParent(child.hwnd), outer.canvas)
			self.assertFalse(user32.IsWindowVisible(child.hwnd))
			child.resize(250, 150, x=20, y=30)
			self.assertEqual(self.control_bounds(outer.canvas, child.hwnd), (20, 30, 250, 150))
			child.resize(200, 100)
			self.assertEqual(self.control_bounds(outer.canvas, child.hwnd), (20, 30, 200, 100))
			child.set_visible(True)
			self.assertFalse(user32.IsWindowVisible(child.hwnd))
			outer.set_visible(True)
			self.assertTrue(user32.IsWindowVisible(child.hwnd))
			child.close()
			self.assertFalse(user32.IsWindow(child.hwnd))
			self.assertFalse(child.loop())
			child.close()
		finally:
			if child is not None:
				child.close()
			outer.close()

	def test_min_layout_scales_on_resize_and_mode_change(self):
		viewport = win.Viewport(width=700, height=500, canvas_width=400, canvas_height=300)
		try:
			button = viewport.add_control("BUTTON", "Test", 40, 30, 80, 60, font_size=16)
			picture = viewport.add_control("STATIC", "", 150, 100, 100, 50)
			viewport.set_picture(picture, self.picture_data())
			combo = viewport.add_control("COMBOBOX", "", 30, 180, 180, 90, style=2)
			originals = copy.deepcopy(viewport.controls)
			viewport.set_visible(True)
			outer = wintypes.RECT()
			client = wintypes.RECT()
			self.assertTrue(user32.GetWindowRect(viewport.hwnd, ctypes.byref(outer)))
			self.assertTrue(user32.GetClientRect(viewport.hwnd, ctypes.byref(client)))
			frame_width = outer.right - outer.left - (client.right - client.left)
			frame_height = outer.bottom - outer.top - (client.bottom - client.top)
			viewport.mode = win.ViewportMode.MIN

			def check_layout(scale_x, scale_y):
				self.assertEqual(viewport.controls[:3], originals)
				for entry in originals[:2]:
					self.assertEqual(self.control_bounds(viewport.canvas, entry["hwnd"]), (
						round(entry["x"] * scale_x), round(entry["y"] * scale_y),
						max(1, round(entry["width"] * scale_x)), max(1, round(entry["height"] * scale_y)),
					))
				child = originals[2]["child"]
				self.assertEqual(self.control_bounds(combo, child["hwnd"]), (
					round(child["x"] * scale_x), round(child["y"] * scale_y),
					max(1, round(child["width"] * scale_x)), max(1, round(child["height"] * scale_y)),
				))
				dc = user32.GetDC(viewport.hwnd)
				self.assertTrue(dc)
				try:
					dpi = win.gdi32.GetDeviceCaps(dc, 90)
				finally:
					user32.ReleaseDC(viewport.hwnd, dc)
				self.assertEqual(self.font_height(viewport._fonts[button]),
					-max(1, round(16 * min(scale_x, scale_y) * dpi / 72)))
				bitmap_info = ctypes.create_string_buffer(128)
				self.assertTrue(win.gdi32.GetObjectW(viewport._bitmaps[picture][1],
					ctypes.sizeof(bitmap_info), bitmap_info))
				self.assertEqual((ctypes.c_long.from_buffer(bitmap_info, 4).value,
					ctypes.c_long.from_buffer(bitmap_info, 8).value),
					(max(1, round(100 * scale_x)), max(1, round(50 * scale_y))))

			self.assertTrue(user32.MoveWindow(viewport.hwnd, 100, 100, 800 + frame_width, 450 + frame_height, True))
			check_layout(2.0, 1.5)
			viewport.zoom = 0.5
			check_layout(2.0, 1.5)
			viewport.zoom = 2.5
			check_layout(2.5, 2.5)
			viewport.zoom = 1.0
			self.assertTrue(user32.MoveWindow(viewport.hwnd, 100, 100, 200 + frame_width, 600 + frame_height, True))
			check_layout(1.0, 2.0)
			added = viewport.add_control("STATIC", "", 200, 100, 40, 30)
			viewport.set_picture(added, self.picture_data())
			self.assertEqual(self.control_bounds(viewport.canvas, added), (200, 200, 40, 60))
			bitmap_info = ctypes.create_string_buffer(128)
			self.assertTrue(win.gdi32.GetObjectW(viewport._bitmaps[added][1],
				ctypes.sizeof(bitmap_info), bitmap_info))
			self.assertEqual((ctypes.c_long.from_buffer(bitmap_info, 4).value,
				ctypes.c_long.from_buffer(bitmap_info, 8).value), (40, 60))
			added_combo = viewport.add_control("COMBOBOX", "", 30, 180, 180, 90, style=2)
			added_child = viewport.controls[-1]["child"]
			self.assertEqual({key: added_child[key] for key in ("x", "y", "width", "height")},
				{key: originals[2]["child"][key] for key in ("x", "y", "width", "height")})
			self.assertEqual(self.control_bounds(added_combo, added_child["hwnd"]), (
				added_child["x"], round(added_child["y"] * 2),
				added_child["width"], round(added_child["height"] * 2),
			))
			viewport.mode = win.ViewportMode.FREE
			check_layout(1.0, 1.0)
			self.assertEqual(self.control_bounds(viewport.canvas, added), (200, 100, 40, 30))
			viewport.mode = win.ViewportMode.MIN
			check_layout(1.0, 2.0)
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_min_zoom_scales_controls_to_canvas(self):
		viewport = win.Viewport(width=700, height=500, canvas_width=400, canvas_height=300,
			mode=win.ViewportMode.MIN)
		try:
			button = viewport.add_control("BUTTON", "Test", 40, 30, 80, 60, font_size=16)
			original = copy.deepcopy(viewport.controls)
			viewport.zoom = 0.5
			canvas = self.control_bounds(viewport.hwnd, viewport.canvas)
			scale_x, scale_y = canvas[2] / 400, canvas[3] / 300
			self.assertEqual(self.control_bounds(viewport.canvas, button),
				(round(40 * scale_x), round(30 * scale_y), round(80 * scale_x), round(60 * scale_y)))
			self.assertEqual(viewport.controls, original)
			viewport.zoom = 2.0
			self.assertEqual(self.control_bounds(viewport.canvas, button), (80, 60, 160, 120))
			self.assertEqual(viewport.controls, original)
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_fit_viewport_mode(self):
		viewport = win.Viewport(width=700, height=500, canvas_width=400, canvas_height=300,
			mode=win.ViewportMode.MIN)
		try:
			viewport.set_visible(True)
			button = viewport.add_control("BUTTON", "Test", 10, 15, 60, 30)
			outer = wintypes.RECT()
			client = wintypes.RECT()
			self.assertTrue(user32.GetWindowRect(viewport.hwnd, ctypes.byref(outer)))
			self.assertTrue(user32.GetClientRect(viewport.hwnd, ctypes.byref(client)))
			frame_width = outer.right - outer.left - (client.right - client.left)
			frame_height = outer.bottom - outer.top - (client.bottom - client.top)
			for width, height in ((700, 500), (250, 150), (700, 150), (250, 500), (400, 300)):
				self.assertTrue(user32.MoveWindow(viewport.hwnd, 100, 100,
					width + frame_width, height + frame_height, True))
				expected_width, expected_height = max(400, width), max(300, height)
				self.assertEqual(self.control_bounds(viewport.hwnd, viewport.canvas),
					(0, 0, expected_width, expected_height))
				for bar, canvas_size, viewport_size in ((win.SB_HORZ, expected_width, width),
						(win.SB_VERT, expected_height, height)):
					info = viewport._scroll_info(bar)
					self.assertEqual(info.nPage, canvas_size)
					self.assertEqual(info.nMax - info.nPage + 1, canvas_size - viewport_size)
				user32.SendMessageW(viewport.hwnd, win.WM_HSCROLL, win.SB_BOTTOM, 0)
				user32.SendMessageW(viewport.hwnd, win.WM_VSCROLL, win.SB_BOTTOM, 0)
				self.assertEqual(self.control_bounds(viewport.hwnd, viewport.canvas),
					(width - expected_width, height - expected_height, expected_width, expected_height))
				user32.SendMessageW(viewport.hwnd, win.WM_HSCROLL, win.SB_TOP, 0)
				user32.SendMessageW(viewport.hwnd, win.WM_VSCROLL, win.SB_TOP, 0)
			self.assertEqual(self.control_bounds(viewport.canvas, button), (10, 15, 60, 30))
			viewport.zoom = 2.0
			self.assertEqual(self.control_bounds(viewport.hwnd, viewport.canvas), (0, 0, 800, 600))
			self.assertEqual((viewport.canvas_width, viewport.canvas_height), (400, 300))
			self.assertEqual(viewport.original_canvas_size, (400, 300))
			viewport.zoom = 0.5
			self.assertEqual(self.control_bounds(viewport.hwnd, viewport.canvas), (0, 0, 400, 300))
			viewport.mode = win.ViewportMode.FREE
			self.assertEqual(self.control_bounds(viewport.hwnd, viewport.canvas), (0, 0, 200, 150))
			viewport.mode = 1
			self.assertEqual(self.control_bounds(viewport.hwnd, viewport.canvas), (0, 0, 400, 300))
			with self.assertRaises(ValueError):
				viewport.mode = 2
			self.assertEqual(viewport.mode, win.ViewportMode.MIN)
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()
		with self.assertRaises(RuntimeError):
			viewport.mode = win.ViewportMode.FREE

	def test_viewport_mode_defaults_and_validation(self):
		with self.assertRaises(ValueError):
			win.Viewport(mode=2)
		viewport = win.Viewport(width=700, height=500, canvas_width=200, canvas_height=100)
		try:
			self.assertEqual(viewport.mode, win.ViewportMode.FREE)
			viewport.set_visible(True)
			user32.SendMessageW(viewport.hwnd, win.WM_HSCROLL, win.SB_BOTTOM, 0)
			user32.SendMessageW(viewport.hwnd, win.WM_VSCROLL, win.SB_BOTTOM, 0)
			viewport.mode = win.ViewportMode.MIN
			rect = wintypes.RECT()
			self.assertTrue(user32.GetClientRect(viewport.hwnd, ctypes.byref(rect)))
			self.assertEqual(self.control_bounds(viewport.hwnd, viewport.canvas),
				(0, 0, rect.right - rect.left, rect.bottom - rect.top))
			self.assertEqual(viewport._scroll_info(win.SB_HORZ).nPos, 0)
			self.assertEqual(viewport._scroll_info(win.SB_VERT).nPos, 0)
			viewport.mode = 0
			self.assertEqual(self.control_bounds(viewport.hwnd, viewport.canvas), (0, 0, 200, 100))
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_combo_edit_child_zoom(self):
		viewport = win.Viewport()
		try:
			viewport.add_control("COMBOBOX", "", 20, 20, 180, 90, style=1)
			dropdown = viewport.add_control("COMBOBOX", "", 20, 130, 180, 90, style=2)
			viewport.add_control("COMBOBOX", "", 20, 240, 180, 90, style=3)
			originals = copy.deepcopy(viewport.controls)
			self.assertIn("child", originals[0])
			self.assertIn("child", originals[1])
			self.assertNotIn("child", originals[2])
			for zoom in (2.0, 0.5, 1.0, 1.5, 10.0, 1.0):
				viewport.zoom = zoom
				self.assertEqual(viewport.controls, originals)
				for entry in originals[:2]:
					child = entry["child"]
					self.assertEqual(user32.GetParent(child["hwnd"]), entry["hwnd"])
					expected = (round(child["x"] * zoom), round(child["y"] * zoom),
						max(1, round(child["width"] * zoom)), max(1, round(child["height"] * zoom)))
					self.assertEqual(self.control_bounds(entry["hwnd"], child["hwnd"]), expected)
					client = wintypes.RECT()
					self.assertTrue(user32.GetClientRect(entry["hwnd"], ctypes.byref(client)))
					self.assertLessEqual(expected[1] + expected[3], client.bottom - client.top)
					font = ctypes.c_void_p(user32.SendMessageW(child["hwnd"], 0x0031, 0, 0)).value
					self.assertEqual(font, viewport._fonts[entry["hwnd"]])
			viewport.zoom = 2.0
			child = originals[1]["child"]
			before = self.control_bounds(dropdown, child["hwnd"])
			label = ctypes.create_unicode_buffer("Choice")
			self.assertEqual(user32.SendMessageW(dropdown, 0x0143, 0, ctypes.cast(label, ctypes.c_void_p).value), 0)
			user32.SendMessageW(dropdown, 0x014F, 1, 0)
			user32.SendMessageW(dropdown, 0x014F, 0, 0)
			self.assertEqual(self.control_bounds(dropdown, child["hwnd"]), before)
			viewport.delete_control(dropdown)
			self.assertFalse(user32.IsWindow(child["hwnd"]))
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_combo_added_while_zoomed(self):
		viewport = win.Viewport()
		try:
			viewport.add_control("COMBOBOX", "", 20, 20, 180, 90, style=2)
			original = copy.deepcopy(viewport.controls[0]["child"])
			viewport.zoom = 1.5
			combo = viewport.add_control("COMBOBOX", "", 300, 20, 180, 90, style=2)
			child = viewport.controls[-1]["child"]
			self.assertEqual({key: child[key] for key in ("x", "y", "width", "height")},
				{key: original[key] for key in ("x", "y", "width", "height")})
			self.assertEqual(self.control_bounds(combo, child["hwnd"]),
				(round(child["x"] * 1.5), round(child["y"] * 1.5),
					max(1, round(child["width"] * 1.5)), max(1, round(child["height"] * 1.5))))
			viewport.zoom = 1.0
			self.assertEqual(self.control_bounds(combo, child["hwnd"]),
				(child["x"], child["y"], child["width"], child["height"]))
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_combo_child_lookup_failure_cleans_up(self):
		viewport = win.Viewport()
		try:
			with patch.object(user32, "GetComboBoxInfo", return_value=0):
				with self.assertRaises(OSError):
					viewport.add_control("COMBOBOX", style=2)
			self.assertEqual(viewport.controls, [])
			self.assertEqual(viewport._fonts, {})
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_scroll_smaller_canvas_within_viewport(self):
		viewport = win.Viewport(width=700, height=500, canvas_width=200, canvas_height=100)
		try:
			button = viewport.add_control("BUTTON", "Test", 10, 15, 60, 30)
			viewport.set_visible(True)
			rect = wintypes.RECT()
			self.assertTrue(user32.GetClientRect(viewport.hwnd, ctypes.byref(rect)))
			width, height = rect.right - rect.left, rect.bottom - rect.top
			self.assertGreater(width, 200)
			self.assertGreater(height, 100)
			self.assertEqual(viewport._scroll_info(win.SB_HORZ).nPage, 200)
			self.assertEqual(viewport._scroll_info(win.SB_VERT).nPage, 100)
			user32.SendMessageW(viewport.hwnd, win.WM_HSCROLL, win.SB_BOTTOM, 0)
			user32.SendMessageW(viewport.hwnd, win.WM_VSCROLL, win.SB_BOTTOM, 0)
			self.assertEqual(self.control_bounds(viewport.hwnd, viewport.canvas),
				(width - 200, height - 100, 200, 100))
			self.assertEqual(self.control_position(viewport, button), (width - 190, height - 85))
			user32.SendMessageW(viewport.hwnd, win.WM_HSCROLL, win.SB_TOP, 0)
			user32.SendMessageW(viewport.hwnd, win.WM_VSCROLL, win.SB_TOP, 0)
			self.assertEqual(self.control_bounds(viewport.hwnd, viewport.canvas), (0, 0, 200, 100))
			self.post_wheel(button, -120, control=False, shift=True)
			self.post_wheel(button, -120, control=False)
			self.assertTrue(viewport.loop())
			self.assertEqual(self.control_bounds(viewport.hwnd, viewport.canvas), (20, 20, 200, 100))
			viewport.zoom = 2.0
			self.assertEqual(viewport._scroll_info(win.SB_HORZ).nPage, 400)
			self.assertEqual(viewport._scroll_info(win.SB_VERT).nPage, 200)
			user32.SendMessageW(viewport.hwnd, win.WM_HSCROLL, win.SB_BOTTOM, 0)
			user32.SendMessageW(viewport.hwnd, win.WM_VSCROLL, win.SB_BOTTOM, 0)
			self.assertEqual(self.control_bounds(viewport.hwnd, viewport.canvas),
				(width - 400, height - 200, 400, 200))
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_scrollbars_remain_stable_at_exact_fit(self):
		viewport = win.Viewport(width=700, height=700, canvas_width=400, canvas_height=600)
		try:
			viewport.set_visible(True)
			outer = wintypes.RECT()
			client = wintypes.RECT()
			self.assertTrue(user32.GetWindowRect(viewport.hwnd, ctypes.byref(outer)))
			self.assertTrue(user32.GetClientRect(viewport.hwnd, ctypes.byref(client)))
			frame_width = outer.right - outer.left - (client.right - client.left)
			frame_height = outer.bottom - outer.top - (client.bottom - client.top)
			for width, height in ((400, 600), (400, 590), (390, 600), (400, 600), (410, 600)):
				self.assertTrue(user32.MoveWindow(viewport.hwnd, 100, 100,
					width + frame_width, height + frame_height, True))
				self.assertTrue(user32.GetClientRect(viewport.hwnd, ctypes.byref(client)))
				self.assertEqual((client.right - client.left, client.bottom - client.top), (width, height))
				self.assertEqual(viewport._scroll_info(win.SB_HORZ).nMax - 400 + 1, abs(width - 400))
				self.assertEqual(viewport._scroll_info(win.SB_VERT).nMax - 600 + 1, abs(height - 600))
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_scroll_mixed_sizes_and_resize(self):
		viewport = win.Viewport(width=700, height=400, canvas_width=400, canvas_height=600)
		try:
			viewport.set_visible(True)
			for window_width, window_height in ((700, 400), (300, 700), (700, 700), (300, 400)):
				self.assertTrue(user32.MoveWindow(viewport.hwnd, 100, 100, window_width, window_height, True))
				rect = wintypes.RECT()
				self.assertTrue(user32.GetClientRect(viewport.hwnd, ctypes.byref(rect)))
				width, height = rect.right - rect.left, rect.bottom - rect.top
				for bar, canvas_size, viewport_size in (
					(win.SB_HORZ, 400, width), (win.SB_VERT, 600, height)
				):
					info = viewport._scroll_info(bar)
					self.assertEqual(info.nPage, canvas_size)
					self.assertEqual(info.nMax, canvas_size + abs(viewport_size - canvas_size) - 1)
				user32.SendMessageW(viewport.hwnd, win.WM_HSCROLL, win.SB_BOTTOM, 0)
				user32.SendMessageW(viewport.hwnd, win.WM_VSCROLL, win.SB_BOTTOM, 0)
				self.assertEqual(self.control_bounds(viewport.hwnd, viewport.canvas),
					(width - 400, height - 600, 400, 600))
			viewport.zoom = 0.5
			rect = wintypes.RECT()
			self.assertTrue(user32.GetClientRect(viewport.hwnd, ctypes.byref(rect)))
			user32.SendMessageW(viewport.hwnd, win.WM_HSCROLL, win.SB_BOTTOM, 0)
			user32.SendMessageW(viewport.hwnd, win.WM_VSCROLL, win.SB_BOTTOM, 0)
			self.assertEqual(self.control_bounds(viewport.hwnd, viewport.canvas),
				(rect.right - rect.left - 200, rect.bottom - rect.top - 300, 200, 300))
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_delete_control_releases_resources(self):
		viewport = win.Viewport()
		try:
			button = viewport.add_control("BUTTON", "Keep", 20, 30, 100, 40)
			picture = viewport.add_control("STATIC", "", 140, 30, 80, 40)
			viewport.set_picture(picture, self.picture_data())
			picture_font = viewport._fonts[picture]
			picture_bitmaps = viewport._bitmaps[picture]
			viewport.delete_control(picture)
			self.assertFalse(user32.IsWindow(picture))
			self.assertEqual([item["hwnd"] for item in viewport.controls], [button])
			self.assertNotIn(picture, viewport._fonts)
			self.assertNotIn(picture, viewport._bitmaps)
			info = ctypes.create_string_buffer(128)
			for handle in {picture_font, *picture_bitmaps}:
				if handle:
					self.assertFalse(win.gdi32.GetObjectW(handle, ctypes.sizeof(info), info))
			viewport.zoom = 1.5
			self.assertEqual(self.control_bounds(viewport.canvas, button), (30, 45, 150, 60))
			button_font = viewport._fonts[button]
			viewport.delete_control(button)
			self.assertFalse(user32.IsWindow(button))
			self.assertFalse(win.gdi32.GetObjectW(button_font, ctypes.sizeof(info), info))
			self.assertEqual(viewport.controls, [])
			with self.assertRaises(ValueError):
				viewport.delete_control(button)
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()
		with self.assertRaises(RuntimeError):
			viewport.delete_control(button)

	def test_delete_control_failure_preserves_state(self):
		viewport = win.Viewport()
		other = win.Viewport()
		try:
			control = viewport.add_control("STATIC")
			foreign = other.add_control("STATIC")
			viewport.set_picture(control, self.picture_data())
			original = dict(viewport.controls[0])
			font = viewport._fonts[control]
			bitmaps = viewport._bitmaps[control]
			with self.assertRaises(ValueError):
				viewport.delete_control(foreign)
			with patch.object(user32, "DestroyWindow", return_value=0):
				with self.assertRaises(OSError):
					viewport.delete_control(control)
			self.assertTrue(user32.IsWindow(control))
			self.assertEqual(viewport.controls, [original])
			self.assertEqual(viewport._fonts[control], font)
			self.assertEqual(viewport._bitmaps[control], bitmaps)
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()
			user32.DestroyWindow(other.hwnd)
			other.loop()

	def test_picture_data_and_zoom(self):
		viewport = win.Viewport(width=320, height=240, canvas_width=800, canvas_height=600)
		try:
			picture = viewport.add_control("STATIC", "", 20, 30, 40, 20)
			original_data = self.picture_data()
			mutable_data = bytearray(original_data)
			viewport.set_picture(picture, mutable_data)
			mutable_data[0] = 0
			original_entry = dict(viewport.controls[0])
			self.assertEqual(original_entry["picture_data"], original_data)
			original_pixels = None
			for zoom in (1.0, 0.05, 0.5, 1.5, 1.0):
				viewport.zoom = zoom
				width = max(1, round(40 * zoom))
				height = max(1, round(20 * zoom))
				self.assertEqual(viewport.controls[0], original_entry)
				self.assertEqual(self.control_bounds(viewport.canvas, picture),
					(round(20 * zoom), round(30 * zoom), width, height))
				bitmap = ctypes.c_void_p(user32.SendMessageW(picture, win.STM_GETIMAGE, 0, 0)).value
				self.assertTrue(bitmap)
				if zoom == 1.0:
					pixels = (self.bitmap_pixel(bitmap, 5, 10), self.bitmap_pixel(bitmap, 35, 10))
					self.assertGreater(pixels[0] & 255, (pixels[0] >> 16) & 255)
					self.assertLess(pixels[1] & 255, (pixels[1] >> 16) & 255)
					self.assertEqual((pixels[0] >> 8) & 255, 0)
					if original_pixels is None:
						original_pixels = pixels
					else:
						self.assertEqual(pixels, original_pixels)
			with self.assertRaises(ValueError):
				viewport.set_picture(picture, b"invalid")
			self.assertEqual(viewport.controls[0], original_entry)
			old_bitmaps = viewport._bitmaps[picture]
			viewport.set_picture(picture, self.picture_data(reverse=True))
			self.assertEqual(viewport.controls[0]["picture_data"], self.picture_data(reverse=True))
			bitmap_info = ctypes.create_string_buffer(128)
			for bitmap in set(old_bitmaps):
				self.assertFalse(win.gdi32.GetObjectW(bitmap, ctypes.sizeof(bitmap_info), bitmap_info))
			last_bitmaps = viewport._bitmaps[picture]
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()
		self.assertEqual(viewport._bitmaps, {})
		for bitmap in set(last_bitmaps):
			self.assertFalse(win.gdi32.GetObjectW(bitmap, ctypes.sizeof(bitmap_info), bitmap_info))

	def test_picture_input_validation(self):
		viewport = win.Viewport()
		other = win.Viewport()
		try:
			button = viewport.add_control("BUTTON")
			picture = viewport.add_control("STATIC")
			foreign = other.add_control("STATIC")
			with self.assertRaises(ValueError):
				viewport.set_picture(button, self.picture_data())
			with self.assertRaises(ValueError):
				viewport.set_picture(foreign, self.picture_data())
			with self.assertRaises(ValueError):
				viewport.set_picture(picture, b"")
			with self.assertRaises(TypeError):
				viewport.set_picture(picture, "not bytes")
			self.assertNotIn("picture_data", viewport.controls[1])
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()
			user32.DestroyWindow(other.hwnd)
			other.loop()
		with self.assertRaises(RuntimeError):
			viewport.set_picture(picture, self.picture_data())

	def test_bitmap_and_transparent_picture(self):
		viewport = win.Viewport()
		try:
			bitmap_control = viewport.add_control("STATIC", "", 10, 10, 40, 20)
			transparent_control = viewport.add_control("STATIC", "", 60, 10, 40, 20)
			bitmap_data = (b"BM" + struct.pack("<IHHI", 62, 0, 0, 54)
				+ struct.pack("<IiiHHIIiiII", 40, 2, 1, 1, 24, 0, 8, 2835, 2835, 0, 0)
				+ b"\x00\x00\xff\xff\x00\x00\x00\x00")
			viewport.set_picture(bitmap_control, bitmap_data)
			viewport.set_picture(transparent_control, self.picture_data(transparent=True))
			for zoom in (1.0, 2.0):
				viewport.zoom = zoom
				bitmap = viewport._bitmaps[bitmap_control][1]
				transparent = viewport._bitmaps[transparent_control][1]
				left = self.bitmap_pixel(bitmap, round(5 * zoom), round(10 * zoom))
				right = self.bitmap_pixel(bitmap, round(35 * zoom), round(10 * zoom))
				self.assertGreater(left & 255, (left >> 16) & 255)
				self.assertLess(right & 255, (right >> 16) & 255)
				self.assertEqual(self.bitmap_pixel(transparent, 1, 1), 0xFFFFFF)
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def picture_data(self, reverse=False, transparent=False):
		def chunk(kind, data):
			return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
		if transparent:
			return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
				+ chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\x00")) + chunk(b"IEND", b""))
		pixels = b"\x00\x00\xff\xff\x00\x00" if reverse else b"\xff\x00\x00\x00\x00\xff"
		return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 1, 8, 2, 0, 0, 0))
			+ chunk(b"IDAT", zlib.compress(b"\x00" + pixels)) + chunk(b"IEND", b""))

	def bitmap_pixel(self, bitmap, x, y):
		dc = win.gdi32.CreateCompatibleDC(None)
		self.assertTrue(dc)
		previous = win.gdi32.SelectObject(dc, bitmap)
		self.assertTrue(previous)
		try:
			return win.gdi32.GetPixel(dc, x, y)
		finally:
			win.gdi32.SelectObject(dc, previous)
			win.gdi32.DeleteDC(dc)

	def test_wheel_scrolls_vertically(self):
		viewport = win.Viewport(width=320, height=240, canvas_width=800, canvas_height=600)
		try:
			button = viewport.add_control("BUTTON", "Scroll", 100, 80)
			self.post_wheel(button, -60, control=False)
			self.assertTrue(viewport.loop())
			self.assertEqual(viewport._scroll_info(win.SB_VERT).nPos, 0)
			self.post_wheel(button, -60, control=False, shift=True)
			self.assertTrue(viewport.loop())
			self.assertEqual(viewport._scroll_info(win.SB_HORZ).nPos, 0)
			self.post_wheel(button, -60, control=False)
			self.assertTrue(viewport.loop())
			self.assertEqual(viewport._scroll_info(win.SB_VERT).nPos, 20)
			self.assertEqual(self.control_position(viewport, button), (100, 60))
			self.assertEqual(viewport._scroll_info(win.SB_HORZ).nPos, 0)
			self.post_wheel(viewport.hwnd, -240, control=False)
			self.assertTrue(viewport.loop())
			self.assertEqual(viewport._scroll_info(win.SB_VERT).nPos, 60)
			user32.SendMessageW(viewport.hwnd, win.WM_MOUSEWHEEL, 120 << 16, 0)
			self.assertEqual(viewport._scroll_info(win.SB_VERT).nPos, 40)
			self.post_wheel(button, 1200, control=False)
			self.assertTrue(viewport.loop())
			self.assertEqual(viewport._scroll_info(win.SB_VERT).nPos, 0)
			self.post_wheel(button, -12000, control=False)
			self.assertTrue(viewport.loop())
			info = viewport._scroll_info(win.SB_VERT)
			self.assertEqual(info.nPos, info.nMax - info.nPage + 1)
			self.assertEqual(viewport.zoom, 1.0)
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_shift_wheel_scrolls_horizontally(self):
		viewport = win.Viewport(width=320, height=240, canvas_width=800, canvas_height=600)
		try:
			button = viewport.add_control("BUTTON", "Scroll", 100, 80)
			self.post_wheel(button, -60, control=False, shift=True)
			self.assertTrue(viewport.loop())
			self.assertEqual(viewport._scroll_info(win.SB_HORZ).nPos, 0)
			self.post_wheel(button, -60, control=False, shift=True)
			self.assertTrue(viewport.loop())
			self.assertEqual(viewport._scroll_info(win.SB_HORZ).nPos, 20)
			self.assertEqual(self.control_position(viewport, button), (80, 80))
			self.assertEqual(viewport._scroll_info(win.SB_VERT).nPos, 0)
			self.post_wheel(viewport.hwnd, -240, control=False, shift=True)
			self.assertTrue(viewport.loop())
			self.assertEqual(viewport._scroll_info(win.SB_HORZ).nPos, 60)
			user32.SendMessageW(viewport.hwnd, win.WM_MOUSEWHEEL, (120 << 16) | win.MK_SHIFT, 0)
			self.assertEqual(viewport._scroll_info(win.SB_HORZ).nPos, 40)
			self.post_wheel(button, 120, control=True, shift=True)
			self.assertTrue(viewport.loop())
			self.assertEqual(viewport.zoom, 1.05)
			self.assertEqual(viewport._scroll_info(win.SB_HORZ).nPos, 40)
			self.post_wheel(button, 1200, control=False, shift=True)
			self.assertTrue(viewport.loop())
			self.assertEqual(viewport._scroll_info(win.SB_HORZ).nPos, 0)
			self.post_wheel(button, -12000, control=False, shift=True)
			self.assertTrue(viewport.loop())
			info = viewport._scroll_info(win.SB_HORZ)
			self.assertEqual(info.nPos, info.nMax - info.nPage + 1)
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def test_control_wheel_zoom(self):
		viewport = win.Viewport(width=320, height=240, canvas_width=800, canvas_height=600)
		try:
			button = viewport.add_control("BUTTON", "Zoom", 100, 80, 200, 40, font_size=20)
			original = dict(viewport.controls[0])
			original_font = viewport._fonts[button]
			original_font_height = self.font_height(original_font)
			self.post_wheel(button, 60)
			self.assertTrue(viewport.loop())
			self.assertEqual(viewport.zoom, 1.0)
			self.post_wheel(button, 60)
			self.assertTrue(viewport.loop())
			self.assertEqual(viewport.zoom, 1.05)
			self.assertEqual(viewport.controls[0], original)
			self.assertEqual(self.control_bounds(viewport.canvas, button), (105, 84, 210, 42))
			canvas = wintypes.RECT()
			self.assertTrue(user32.GetWindowRect(viewport.canvas, ctypes.byref(canvas)))
			self.assertEqual((canvas.right - canvas.left, canvas.bottom - canvas.top), (840, 630))
			self.assertGreater(abs(self.font_height(viewport._fonts[button])), abs(original_font_height))
			self.assertEqual(ctypes.c_void_p(user32.SendMessageW(button, 0x0031, 0, 0)).value,
				viewport._fonts[button])
			logfont = ctypes.create_string_buffer(92)
			self.assertFalse(win.gdi32.GetObjectW(original_font, ctypes.sizeof(logfont), logfont))
			self.assertEqual(viewport._scroll_info(win.SB_HORZ).nPage, 840)
			self.assertEqual(viewport._scroll_info(win.SB_VERT).nPage, 630)

			edit = viewport.add_control("EDIT", "Text", 200, 100, 100, 20, font_size=16)
			self.assertEqual(self.control_bounds(viewport.canvas, edit), (210, 105, 105, 21))
			self.assertEqual(viewport.controls[1]["font_size"], 16)
			self.post_wheel(button, 120, control=False)
			self.assertTrue(viewport.loop())
			self.assertEqual(viewport.zoom, 1.05)
			self.post_wheel(button, -120)
			self.assertTrue(viewport.loop())
			self.assertEqual(viewport.zoom, 1.0)
			self.assertEqual(viewport.controls[0], original)
			self.assertEqual(self.control_bounds(viewport.canvas, button), (100, 80, 200, 40))
			self.assertEqual(self.font_height(viewport._fonts[button]), original_font_height)
			viewport.zoom = 1.5
			self.assertEqual(self.control_bounds(viewport.canvas, button), (150, 120, 300, 60))
			self.assertEqual(viewport.controls[0], original)
			with self.assertRaises(ValueError):
				viewport.zoom = 0
			self.assertEqual(viewport.zoom, 1.5)
			last_font = viewport._fonts[button]
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()
		self.assertEqual(viewport._fonts, {})
		self.assertFalse(win.gdi32.GetObjectW(last_font, ctypes.sizeof(logfont), logfont))

	def test_zoom_clamps_scroll_position(self):
		viewport = win.Viewport(width=320, height=240, canvas_width=800, canvas_height=600)
		try:
			user32.SendMessageW(viewport.hwnd, win.WM_HSCROLL, win.SB_BOTTOM, 0)
			user32.SendMessageW(viewport.hwnd, win.WM_VSCROLL, win.SB_BOTTOM, 0)
			self.post_wheel(viewport.hwnd, -1200)
			self.assertTrue(viewport.loop())
			self.assertEqual(viewport.zoom, 0.5)
			rect = wintypes.RECT()
			self.assertTrue(user32.GetClientRect(viewport.hwnd, ctypes.byref(rect)))
			for bar, canvas_size, viewport_size in ((win.SB_HORZ, 400, rect.right - rect.left),
					(win.SB_VERT, 300, rect.bottom - rect.top)):
				info = viewport._scroll_info(bar)
				self.assertEqual(info.nPage, canvas_size)
				self.assertEqual(info.nMax, canvas_size + abs(viewport_size - canvas_size) - 1)
				self.assertLessEqual(info.nPos, max(0, info.nMax - info.nPage + 1))
			self.post_wheel(viewport.hwnd, -12000)
			self.assertTrue(viewport.loop())
			self.assertEqual(viewport.zoom, 0.05)
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def post_wheel(self, hwnd, delta, control=True, shift=False):
		wparam = ((delta & 0xFFFF) << 16) | (win.MK_CONTROL if control else 0) | (win.MK_SHIFT if shift else 0)
		self.assertTrue(user32.PostMessageW(hwnd, win.WM_MOUSEWHEEL, wparam, 0))

	def control_bounds(self, parent, hwnd):
		rect = wintypes.RECT()
		self.assertTrue(user32.GetWindowRect(hwnd, ctypes.byref(rect)))
		point = wintypes.POINT(rect.left, rect.top)
		self.assertTrue(user32.ScreenToClient(parent, ctypes.byref(point)))
		return point.x, point.y, rect.right - rect.left, rect.bottom - rect.top

	def font_height(self, font):
		logfont = ctypes.create_string_buffer(92)
		self.assertTrue(win.gdi32.GetObjectW(font, ctypes.sizeof(logfont), logfont))
		return ctypes.c_long.from_buffer(logfont).value

	def test_visibility_is_explicit(self):
		viewport = win.Viewport()
		try:
			button = viewport.add_control("BUTTON", "Click")
			self.assertFalse(user32.IsWindowVisible(viewport.hwnd))
			self.assertFalse(user32.IsWindowVisible(button))
			self.assertTrue(viewport.loop())
			self.assertFalse(user32.IsWindowVisible(viewport.hwnd))
			viewport.set_visible(True)
			self.assertTrue(user32.IsWindowVisible(viewport.hwnd))
			self.assertTrue(user32.IsWindowVisible(button))
			viewport.set_visible(False)
			self.assertFalse(user32.IsWindowVisible(viewport.hwnd))
			self.assertFalse(user32.IsWindowVisible(button))
			self.assertTrue(viewport.loop())
			self.assertFalse(user32.IsWindowVisible(viewport.hwnd))
			viewport.set_visible()
			self.assertTrue(user32.IsWindowVisible(viewport.hwnd))
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()
		with self.assertRaises(RuntimeError):
			viewport.set_visible(True)

	def test_add_control(self):
		viewport = win.Viewport(width=320, height=240, canvas_width=800, canvas_height=600)
		try:
			button = viewport.add_control("BUTTON", "Click", 50, 60, 100, 30, control_id=42)
			edit = viewport.add_control("EDIT", "Text", 150, 100, 120, 25)
			self.assertEqual(user32.GetParent(button), viewport.canvas)
			self.assertEqual(user32.GetParent(edit), viewport.canvas)
			self.assertEqual(user32.GetDlgCtrlID(button), 42)
			self.assertTrue(viewport.loop())
			before = self.control_position(viewport, button)
			self.assertEqual(before, (50, 60))
			user32.SendMessageW(viewport.hwnd, win.WM_HSCROLL, win.SB_LINEDOWN, 0)
			user32.SendMessageW(viewport.hwnd, win.WM_VSCROLL, win.SB_LINEDOWN, 0)
			self.assertEqual(self.control_position(viewport, button), (30, 40))
			with self.assertRaises(ValueError):
				viewport.add_control("BUTTON", width=0)
			with self.assertRaises(OSError):
				viewport.add_control("MissingControlClass")
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()
		self.assertFalse(user32.IsWindow(button))
		with self.assertRaises(RuntimeError):
			viewport.add_control("BUTTON")

	def control_position(self, viewport, control):
		rect = wintypes.RECT()
		self.assertTrue(user32.GetWindowRect(control, ctypes.byref(rect)))
		point = wintypes.POINT(rect.left, rect.top)
		self.assertTrue(user32.ScreenToClient(viewport.hwnd, ctypes.byref(point)))
		return point.x, point.y

	def test_run_returns_and_dispatches_posted_messages(self):
		viewport = win.Viewport(width=320, height=240, canvas_width=800, canvas_height=600)
		try:
			self.assertTrue(viewport.run())
			self.assertTrue(viewport.run())
			self.assertTrue(user32.PostMessageW(viewport.hwnd, win.WM_HSCROLL, win.SB_LINEDOWN, 0))
			self.assertTrue(viewport.run())
			self.assertEqual(self.canvas_position(viewport), (-20, 0))
		finally:
			user32.PostMessageW(viewport.hwnd, 0x0010, 0, 0)
			win.main_loop(viewport.run, interval=0)
		self.assertFalse(viewport.run())

	def test_main_loop_calls_hook_until_viewport_closes(self):
		viewport = win.Viewport()
		calls = []

		def hook():
			calls.append(len(calls))
			if len(calls) == 3:
				user32.PostMessageW(viewport.hwnd, 0x0010, 0, 0)
			return viewport.run()

		win.main_loop(hook, interval=0)
		self.assertEqual(len(calls), 3)
		self.assertFalse(viewport.run())

	def test_run_limits_work_per_call(self):
		viewport = win.Viewport()
		try:
			self.assertTrue(viewport.run())
			for _ in range(250):
				self.assertTrue(user32.PostMessageW(viewport.hwnd, 0, 0, 0))
			self.assertTrue(user32.PostMessageW(viewport.hwnd, 0x0010, 0, 0))
			self.assertTrue(viewport.run())
		finally:
			win.main_loop(viewport.run, interval=0)
		self.assertFalse(viewport.run())

	def test_quit_message_is_preserved_for_outer_loop(self):
		viewport = win.Viewport()
		self.assertTrue(viewport.run())
		user32.PostQuitMessage(37)
		try:
			self.assertFalse(viewport.run())
		finally:
			message = wintypes.MSG()
			self.assertTrue(user32.PeekMessageW(ctypes.byref(message), None, win.WM_QUIT, win.WM_QUIT, win.PM_REMOVE))
		self.assertEqual((message.message, message.wParam), (win.WM_QUIT, 37))

	def test_scrolling_and_resizing(self):
		viewport = win.Viewport(width=320, height=240, canvas_width=800, canvas_height=600)
		try:
			viewport.set_visible(True)
			self.assertEqual(user32.GetParent(viewport.canvas), viewport.hwnd)
			self.assertEqual(self.canvas_position(viewport), (0, 0))

			user32.SendMessageW(viewport.hwnd, win.WM_HSCROLL, win.SB_LINEDOWN, 0)
			user32.SendMessageW(viewport.hwnd, win.WM_VSCROLL, win.SB_PAGEDOWN, 0)
			vertical = viewport._scroll_info(win.SB_VERT)
			self.assertEqual(self.canvas_position(viewport),
				(-20, -min(vertical.nPage, vertical.nMax - vertical.nPage + 1)))

			user32.SendMessageW(viewport.hwnd, win.WM_HSCROLL, win.SB_BOTTOM, 0)
			user32.SendMessageW(viewport.hwnd, win.WM_VSCROLL, win.SB_BOTTOM, 0)
			horizontal = viewport._scroll_info(win.SB_HORZ)
			vertical = viewport._scroll_info(win.SB_VERT)
			self.assertEqual(self.canvas_position(viewport), (
				-(horizontal.nMax - horizontal.nPage + 1),
				-(vertical.nMax - vertical.nPage + 1),
			))

			self.assertTrue(user32.MoveWindow(viewport.hwnd, 100, 100, 1000, 800, True))
			self.assertEqual(self.canvas_position(viewport), tuple(
				viewport._scroll_info(bar).nPos for bar in (win.SB_HORZ, win.SB_VERT)))
			self.assertTrue(user32.MoveWindow(viewport.hwnd, 100, 100, 320, 240, True))
			self.assertEqual(self.canvas_position(viewport), tuple(
				-viewport._scroll_info(bar).nPos for bar in (win.SB_HORZ, win.SB_VERT)))
			self.assertEqual(viewport._scroll_info(win.SB_HORZ).nPage, 800)
			self.assertEqual(viewport._scroll_info(win.SB_VERT).nPage, 600)
		finally:
			user32.DestroyWindow(viewport.hwnd)
			viewport.loop()

	def canvas_position(self, viewport):
		rect = wintypes.RECT()
		self.assertTrue(user32.GetWindowRect(viewport.canvas, ctypes.byref(rect)))
		point = wintypes.POINT(rect.left, rect.top)
		self.assertTrue(user32.ScreenToClient(viewport.hwnd, ctypes.byref(point)))
		return point.x, point.y

	def test_canvas_dimensions_must_be_positive(self):
		with self.assertRaises(ValueError):
			win.Viewport(canvas_width=0)
		with self.assertRaises(ValueError):
			win.Viewport(canvas_height=0)


if __name__ == "__main__":
	unittest.main()
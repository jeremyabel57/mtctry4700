import ctypes
import threading
from ctypes import wintypes
from uuid import uuid4

from wincanvas import (
	WNDCLASS, WNDPROC, Viewport, ViewportMode,
	WM_MOUSEWHEEL,
	WS_CHILD, WS_CLIPSIBLINGS, WS_OVERLAPPEDWINDOW, WS_VISIBLE,
	kernel32, user32,
)


class INITCOMMONCONTROLSEX(ctypes.Structure):
	_fields_ = [("dwSize", wintypes.DWORD), ("dwICC", wintypes.DWORD)]


class TCITEM(ctypes.Structure):
	_fields_ = [
		("mask", wintypes.UINT),
		("dwState", wintypes.DWORD),
		("dwStateMask", wintypes.DWORD),
		("pszText", wintypes.LPWSTR),
		("cchTextMax", ctypes.c_int),
		("iImage", ctypes.c_int),
		("lParam", wintypes.LPARAM),
	]


class NMHDR(ctypes.Structure):
	_fields_ = [("hwndFrom", wintypes.HWND), ("idFrom", ctypes.c_size_t), ("code", wintypes.UINT)]


ICC_BAR_CLASSES = 0x00000004
ICC_TAB_CLASSES = 0x00000008
WS_CLIPCHILDREN = 0x02000000
SBARS_SIZEGRIP = 0x0100
WM_DESTROY = 0x0002
WM_SIZE = 0x0005
WM_QUIT = 0x0012
WM_NOTIFY = 0x004E
PM_REMOVE = 0x0001
TCIF_TEXT = 0x0001
TCM_FIRST = 0x1300
TCM_GETCURSEL = TCM_FIRST + 11
TCM_SETCURSEL = TCM_FIRST + 12
TCM_DELETEITEM = TCM_FIRST + 8
TCM_ADJUSTRECT = TCM_FIRST + 40
TCM_INSERTITEMW = TCM_FIRST + 62
TCN_SELCHANGE = -551
SB_SETTEXTW = 0x040B


comctl32 = ctypes.WinDLL("comctl32", use_last_error=True)
comctl32.InitCommonControlsEx.argtypes = [ctypes.POINTER(INITCOMMONCONTROLSEX)]
comctl32.InitCommonControlsEx.restype = wintypes.BOOL


class MainWindow:
	"""A resizable native window containing tabbed viewports and a status bar."""

	def __init__(self, title="Tabbed Viewports", width=1000, height=700):
		if width <= 0 or height <= 0:
			raise ValueError("Window dimensions must be positive")
		self._thread = threading.get_ident()
		self._closed = False
		self._finished = False
		self.tab_hwnd = None
		self.status_hwnd = None
		self.viewports = []
		self.instance = kernel32.GetModuleHandleW(None)
		if not self.instance:
			raise ctypes.WinError(ctypes.get_last_error())
		common = INITCOMMONCONTROLSEX(ctypes.sizeof(INITCOMMONCONTROLSEX), ICC_TAB_CLASSES | ICC_BAR_CLASSES)
		if not comctl32.InitCommonControlsEx(ctypes.byref(common)):
			raise ctypes.WinError(ctypes.get_last_error())
		self.class_name = f"TabbedViewports_{uuid4().hex}"
		self._wndproc = WNDPROC(self._window_proc)
		window_class = WNDCLASS()
		window_class.lpfnWndProc = self._wndproc
		window_class.hInstance = self.instance
		window_class.hCursor = user32.LoadCursorW(None, ctypes.cast(32512, wintypes.LPCWSTR))
		window_class.hbrBackground = wintypes.HBRUSH(6)
		window_class.lpszClassName = self.class_name
		if not user32.RegisterClassW(ctypes.byref(window_class)):
			raise ctypes.WinError(ctypes.get_last_error())
		self.hwnd = user32.CreateWindowExW(
			0, self.class_name, title, WS_OVERLAPPEDWINDOW | WS_CLIPCHILDREN,
			-2147483648, -2147483648, width, height, None, None, self.instance, None,
		)
		if not self.hwnd:
			error = ctypes.get_last_error()
			user32.UnregisterClassW(self.class_name, self.instance)
			raise ctypes.WinError(error)
		try:
			self.tab_hwnd = user32.CreateWindowExW(
				0, "SysTabControl32", "", WS_CHILD | WS_VISIBLE | WS_CLIPCHILDREN | WS_CLIPSIBLINGS,
				0, 0, 0, 0, self.hwnd, None, self.instance, None,
			)
			if not self.tab_hwnd:
				raise ctypes.WinError(ctypes.get_last_error())
			self.status_hwnd = user32.CreateWindowExW(
				0, "msctls_statusbar32", "", WS_CHILD | WS_VISIBLE | SBARS_SIZEGRIP,
				0, 0, 0, 0, self.hwnd, None, self.instance, None,
			)
			if not self.status_hwnd:
				raise ctypes.WinError(ctypes.get_last_error())
			self._layout()
		except Exception:
			user32.DestroyWindow(self.hwnd)
			user32.UnregisterClassW(self.class_name, self.instance)
			raise

	def add_tab(self, title, *, canvas_width=1600, canvas_height=1200, mode=ViewportMode.FREE):
		"""Add a tab and return its child viewport."""
		if self._closed:
			raise RuntimeError("Cannot add a tab to a closed window")
		label = ctypes.create_unicode_buffer(title)
		item = TCITEM()
		item.mask = TCIF_TEXT
		item.pszText = ctypes.cast(label, wintypes.LPWSTR)
		index = len(self.viewports)
		if user32.SendMessageW(self.tab_hwnd, TCM_INSERTITEMW, index, ctypes.addressof(item)) == -1:
			raise RuntimeError("Could not insert tab")
		try:
			viewport = Viewport(parent=self.tab_hwnd, width=1, height=1,
				canvas_width=canvas_width, canvas_height=canvas_height, mode=mode)
		except Exception:
			user32.SendMessageW(self.tab_hwnd, TCM_DELETEITEM, index, 0)
			raise
		self.viewports.append(viewport)
		self.select_tab(index)
		return viewport

	def select_tab(self, index):
		"""Select a tab by its zero-based index."""
		if self._closed:
			raise RuntimeError("Cannot select a tab in a closed window")
		if not 0 <= index < len(self.viewports):
			raise IndexError("Tab index out of range")
		user32.SendMessageW(self.tab_hwnd, TCM_SETCURSEL, index, 0)
		self.on_tab_changed()

	def on_tab_changed(self):
		"""Show the selected viewport and hide all others."""
		selected = user32.SendMessageW(self.tab_hwnd, TCM_GETCURSEL, 0, 0)
		for index, viewport in enumerate(self.viewports):
			viewport.set_visible(index == selected)
		self._resize_selected_viewport()

	def _resize_selected_viewport(self):
		selected = user32.SendMessageW(self.tab_hwnd, TCM_GETCURSEL, 0, 0)
		if not 0 <= selected < len(self.viewports):
			return
		rect = wintypes.RECT()
		if not user32.GetClientRect(self.tab_hwnd, ctypes.byref(rect)):
			raise ctypes.WinError(ctypes.get_last_error())
		user32.SendMessageW(self.tab_hwnd, TCM_ADJUSTRECT, 0, ctypes.addressof(rect))
		self.viewports[selected].resize(max(0, rect.right - rect.left), max(0, rect.bottom - rect.top),
			x=rect.left, y=rect.top)

	def _layout(self):
		client = wintypes.RECT()
		status = wintypes.RECT()
		if not user32.GetClientRect(self.hwnd, ctypes.byref(client)):
			raise ctypes.WinError(ctypes.get_last_error())
		user32.SendMessageW(self.status_hwnd, WM_SIZE, 0, 0)
		if not user32.GetWindowRect(self.status_hwnd, ctypes.byref(status)):
			raise ctypes.WinError(ctypes.get_last_error())
		width = client.right - client.left
		height = client.bottom - client.top
		status_height = min(height, status.bottom - status.top)
		if not user32.MoveWindow(self.tab_hwnd, 0, 0, width, max(0, height - status_height), True):
			raise ctypes.WinError(ctypes.get_last_error())
		self._resize_selected_viewport()

	def set_status(self, text):
		"""Set the status bar text."""
		if self._closed:
			raise RuntimeError("Cannot update a closed window")
		value = ctypes.create_unicode_buffer(text)
		user32.SendMessageW(self.status_hwnd, SB_SETTEXTW, 0, ctypes.addressof(value))

	def set_visible(self, visible=True):
		"""Show or hide the window."""
		if self._closed:
			raise RuntimeError("Cannot show a closed window")
		user32.ShowWindow(self.hwnd, 5 if visible else 0)
		if visible:
			user32.UpdateWindow(self.hwnd)

	def _window_proc(self, hwnd, message, wparam, lparam):
		if message == WM_DESTROY:
			self._closed = True
			for viewport in self.viewports:
				viewport.close()
			return 0
		if message == WM_SIZE and self.tab_hwnd and self.status_hwnd:
			self._layout()
			return 0
		if message == WM_NOTIFY and lparam and self.tab_hwnd:
			notification = ctypes.cast(lparam, ctypes.POINTER(NMHDR)).contents
			if notification.hwndFrom == self.tab_hwnd and ctypes.c_int32(notification.code).value == TCN_SELCHANGE:
				self.on_tab_changed()
				return 0
		return user32.DefWindowProcW(hwnd, message, wparam, lparam)

	def loop(self):
		"""Process pending window messages without blocking."""
		if self._finished:
			return False
		message = wintypes.MSG()
		for _ in range(100):
			if self._closed or not user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
				break
			if message.message == WM_QUIT:
				user32.PostQuitMessage(message.wParam)
				self.close()
				return False
			if message.message == WM_MOUSEWHEEL:
				handled = False
				for viewport in self.viewports:
					if (not viewport._closed and
							(message.hWnd == viewport.hwnd or user32.IsChild(viewport.hwnd, message.hWnd)) and
							viewport._handle_wheel(message.wParam)):
						handled = True
						break
				if handled:
					continue
			user32.TranslateMessage(ctypes.byref(message))
			user32.DispatchMessageW(ctypes.byref(message))
		if self._closed:
			if not user32.UnregisterClassW(self.class_name, self.instance):
				raise ctypes.WinError(ctypes.get_last_error())
			self._finished = True
			return False
		for viewport in self.viewports:
			if viewport._closed and not viewport._finished:
				viewport.loop()
			for control in viewport.controls:
				if "webview" in control:
					control["webview"].loop()
		return True

	def close(self):
		"""Close the window and its child viewports."""
		if threading.get_ident() != self._thread:
			raise RuntimeError("MainWindow must be closed on its creating thread")
		if self._finished:
			return
		if not self._closed and not user32.DestroyWindow(self.hwnd):
			raise ctypes.WinError(ctypes.get_last_error())
		self.loop()

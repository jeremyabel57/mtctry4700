import ctypes
import math
import threading
import time
from ctypes import wintypes
from enum import IntEnum
from uuid import uuid4


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
gdiplus = ctypes.WinDLL("gdiplus", use_last_error=True)
shlwapi = ctypes.WinDLL("shlwapi", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(
	LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class WNDCLASS(ctypes.Structure):
	_fields_ = [
		("style", wintypes.UINT),
		("lpfnWndProc", WNDPROC),
		("cbClsExtra", ctypes.c_int),
		("cbWndExtra", ctypes.c_int),
		("hInstance", wintypes.HINSTANCE),
		("hIcon", wintypes.HICON),
		("hCursor", wintypes.HANDLE),
		("hbrBackground", wintypes.HBRUSH),
		("lpszMenuName", wintypes.LPCWSTR),
		("lpszClassName", wintypes.LPCWSTR),
	]


class SCROLLINFO(ctypes.Structure):
	_fields_ = [
		("cbSize", wintypes.UINT),
		("fMask", wintypes.UINT),
		("nMin", ctypes.c_int),
		("nMax", ctypes.c_int),
		("nPage", wintypes.UINT),
		("nPos", ctypes.c_int),
		("nTrackPos", ctypes.c_int),
	]


class COMBOBOXINFO(ctypes.Structure):
	_fields_ = [
		("cbSize", wintypes.DWORD),
		("rcItem", wintypes.RECT),
		("rcButton", wintypes.RECT),
		("stateButton", wintypes.DWORD),
		("hwndCombo", wintypes.HWND),
		("hwndItem", wintypes.HWND),
		("hwndList", wintypes.HWND),
	]


class GDIPLUSSTARTUPINPUT(ctypes.Structure):
	_fields_ = [
		("version", wintypes.UINT),
		("debug_callback", ctypes.c_void_p),
		("suppress_background_thread", wintypes.BOOL),
		("suppress_external_codecs", wintypes.BOOL),
	]


WS_OVERLAPPEDWINDOW = 0x00CF0000  # Standard top-level window style.
WS_HSCROLL = 0x00100000  # Add a horizontal scrollbar.
WS_VSCROLL = 0x00200000  # Add a vertical scrollbar.
WS_CHILD = 0x40000000  # Create a child window.
WS_VISIBLE = 0x10000000  # Make the window initially visible.
WS_CLIPSIBLINGS = 0x04000000  # Clip drawing against sibling windows.
SS_WHITERECT = 0x00000006  # Fill a static control with white.
SS_BITMAP = 0x0000000E  # Display a bitmap in a static control.
SS_TYPEMASK = 0x0000001F  # Mask for the type of static control.
GWL_STYLE = -16  # Index of a window's style.
STM_SETIMAGE = 0x0172  # Set a static control's image.
STM_GETIMAGE = 0x0173  # Get a static control's image.
IMAGE_BITMAP = 0  # Select a bitmap image.
SW_HIDE = 0  # Hide the window.
SW_SHOW = 5  # Show the window in its current state.
SWP_NOMOVE = 0x0002  # Preserve the window position.
SWP_NOZORDER = 0x0004  # Preserve the window stacking order.
SWP_NOACTIVATE = 0x0010  # Do not activate the window when resizing it.
WM_DESTROY = 0x0002  # Window is being destroyed.
WM_SIZE = 0x0005  # Window client area has been resized.
WM_QUIT = 0x0012  # Thread message requesting the message loop to exit.
WM_HSCROLL = 0x0114  # Horizontal scrollbar request.
WM_VSCROLL = 0x0115  # Vertical scrollbar request.
WM_MOUSEWHEEL = 0x020A  # Mouse wheel movement.
WM_SETFONT = 0x0030  # Assign a font to a control.
CB_SETITEMHEIGHT = 0x0153  # Set a combo box selection-field or list-item height.
CBS_DROPDOWN = 0x0002  # Combo box with an editable field and drop-down list.
MK_SHIFT = 0x0004  # Shift key is held during a mouse message.
MK_CONTROL = 0x0008  # Control key is held during a mouse message.
WHEEL_DELTA = 120  # Wheel movement corresponding to one step.
PM_REMOVE = 0x0001  # Remove the retrieved message from the queue.
SB_HORZ = 0  # Select the horizontal scrollbar.
SB_VERT = 1  # Select the vertical scrollbar.
SB_BOTH = 3
SB_LINEUP = 0  # Scroll one step toward the start.
SB_LINEDOWN = 1  # Scroll one step toward the end.
SB_PAGEUP = 2  # Scroll one page toward the start.
SB_PAGEDOWN = 3  # Scroll one page toward the end.
SB_THUMBPOSITION = 4  # Set the position after the scrollbar thumb is released.
SB_THUMBTRACK = 5  # Track the scrollbar thumb while it is dragged.
SB_TOP = 6  # Scroll to the start of the range.
SB_BOTTOM = 7  # Scroll to the end of the range.
SIF_RANGE = 0x0001  # Read or set the scrollbar's minimum and maximum.
SIF_PAGE = 0x0002  # Read or set the scrollbar's page size.
SIF_POS = 0x0004  # Read or set the scrollbar's current position.
SIF_DISABLENOSCROLL = 0x0008  # Disable a scrollbar rather than removing it when it cannot scroll.
SIF_TRACKPOS = 0x0010  # Read the thumb's current tracking position.


def setup_win32():
	# Configure ctypes signatures before calling the Windows APIs. argtypes lists
	# the expected argument types; restype specifies the returned type. W-suffixed
	# functions use Unicode strings, and POINTER(...) passes a structure by address.

	# Get the handle of a loaded module; None selects the current executable.
	kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
	kernel32.GetModuleHandleW.restype = wintypes.HMODULE

	# Register a window class and return its atom (zero indicates failure).
	user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
	user32.RegisterClassW.restype = wintypes.ATOM

	# Remove a registered window class once its windows have been destroyed.
	user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
	user32.UnregisterClassW.restype = wintypes.BOOL

	# Create a window and return its handle (null indicates failure).
	user32.CreateWindowExW.argtypes = [
		wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,  # Extended style, class, title, style.
		ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,  # Position and dimensions.
		wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,  # Parent, menu, instance, creation data.
	]
	user32.CreateWindowExW.restype = wintypes.HWND

	# Apply default processing to window messages not handled by our callback.
	user32.DefWindowProcW.argtypes = [
		wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
	]
	user32.DefWindowProcW.restype = LRESULT

	# Load a cursor resource and return its handle.
	user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
	user32.LoadCursorW.restype = wintypes.HANDLE

	# Change a window's visibility and report its previous visibility state.
	user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
	user32.ShowWindow.restype = wintypes.BOOL
	user32.ShowScrollBar.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.BOOL]
	user32.ShowScrollBar.restype = wintypes.BOOL

	# Send a paint message immediately if the window needs repainting.
	user32.UpdateWindow.argtypes = [wintypes.HWND]
	user32.UpdateWindow.restype = wintypes.BOOL

	# Check the thread's message queue without waiting for a message.
	user32.PeekMessageW.argtypes = [
		ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT
	]
	user32.PeekMessageW.restype = wintypes.BOOL

	# Translate keyboard messages into character messages when appropriate.
	user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
	user32.TranslateMessage.restype = wintypes.BOOL

	# Deliver a queued message to the target window's callback.
	user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
	user32.DispatchMessageW.restype = LRESULT

	# Post a WM_QUIT message with an exit code to the current thread's queue.
	user32.PostQuitMessage.argtypes = [ctypes.c_int]
	user32.PostQuitMessage.restype = None

	# Destroy a window and its child windows.
	user32.DestroyWindow.argtypes = [wintypes.HWND]
	user32.DestroyWindow.restype = wintypes.BOOL

	# Write the window's client-area dimensions into a RECT structure.
	user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
	user32.GetClientRect.restype = wintypes.BOOL
	user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
	user32.GetWindowRect.restype = wintypes.BOOL
	user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
	user32.ScreenToClient.restype = wintypes.BOOL
	user32.GetComboBoxInfo.argtypes = [wintypes.HWND, ctypes.POINTER(COMBOBOXINFO)]
	user32.GetComboBoxInfo.restype = wintypes.BOOL

	# Change a window's position and size, optionally repainting it.
	user32.MoveWindow.argtypes = [
		wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL
	]
	user32.MoveWindow.restype = wintypes.BOOL
	user32.SetWindowPos.argtypes = [
		wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT
	]
	user32.SetWindowPos.restype = wintypes.BOOL

	# Set selected scrollbar properties and return the resulting position.
	user32.SetScrollInfo.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.POINTER(SCROLLINFO), wintypes.BOOL]
	user32.SetScrollInfo.restype = ctypes.c_int

	# Read selected scrollbar properties into a SCROLLINFO structure.
	user32.GetScrollInfo.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.POINTER(SCROLLINFO)]
	user32.GetScrollInfo.restype = wintypes.BOOL

	user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
	user32.SendMessageW.restype = LRESULT
	user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
	user32.GetClassNameW.restype = ctypes.c_int
	user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
	user32.GetWindowLongW.restype = wintypes.LONG
	user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
	user32.SetWindowLongW.restype = wintypes.LONG
	user32.IsChild.argtypes = [wintypes.HWND, wintypes.HWND]
	user32.IsChild.restype = wintypes.BOOL
	user32.GetDC.argtypes = [wintypes.HWND]
	user32.GetDC.restype = wintypes.HDC
	user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
	user32.ReleaseDC.restype = ctypes.c_int
	gdi32.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
	gdi32.GetDeviceCaps.restype = ctypes.c_int
	gdi32.CreateFontW.argtypes = [
		ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
		wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
		wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPCWSTR,
	]
	gdi32.CreateFontW.restype = wintypes.HANDLE
	gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
	gdi32.DeleteObject.restype = wintypes.BOOL

	shlwapi.SHCreateMemStream.argtypes = [ctypes.POINTER(ctypes.c_ubyte), wintypes.UINT]
	shlwapi.SHCreateMemStream.restype = ctypes.c_void_p
	gdiplus.GdiplusStartup.argtypes = [ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(GDIPLUSSTARTUPINPUT), ctypes.c_void_p]
	gdiplus.GdiplusStartup.restype = ctypes.c_int
	gdiplus.GdiplusShutdown.argtypes = [ctypes.c_size_t]
	gdiplus.GdiplusShutdown.restype = None
	gdiplus.GdipCreateBitmapFromStream.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
	gdiplus.GdipCreateBitmapFromStream.restype = ctypes.c_int
	gdiplus.GdipGetImageWidth.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.UINT)]
	gdiplus.GdipGetImageWidth.restype = ctypes.c_int
	gdiplus.GdipGetImageHeight.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.UINT)]
	gdiplus.GdipGetImageHeight.restype = ctypes.c_int
	gdiplus.GdipCreateBitmapFromScan0.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
		ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
	gdiplus.GdipCreateBitmapFromScan0.restype = ctypes.c_int
	gdiplus.GdipGetImageGraphicsContext.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
	gdiplus.GdipGetImageGraphicsContext.restype = ctypes.c_int
	gdiplus.GdipGraphicsClear.argtypes = [ctypes.c_void_p, wintypes.DWORD]
	gdiplus.GdipGraphicsClear.restype = ctypes.c_int
	gdiplus.GdipSetInterpolationMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
	gdiplus.GdipSetInterpolationMode.restype = ctypes.c_int
	gdiplus.GdipCreateImageAttributes.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
	gdiplus.GdipCreateImageAttributes.restype = ctypes.c_int
	gdiplus.GdipSetImageAttributesWrapMode.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.DWORD, wintypes.BOOL]
	gdiplus.GdipSetImageAttributesWrapMode.restype = ctypes.c_int
	gdiplus.GdipDrawImageRectRectI.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
		ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
		ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
		ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
	gdiplus.GdipDrawImageRectRectI.restype = ctypes.c_int
	gdiplus.GdipDisposeImageAttributes.argtypes = [ctypes.c_void_p]
	gdiplus.GdipDisposeImageAttributes.restype = ctypes.c_int
	gdiplus.GdipCreateHBITMAPFromBitmap.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD]
	gdiplus.GdipCreateHBITMAPFromBitmap.restype = ctypes.c_int
	gdiplus.GdipDeleteGraphics.argtypes = [ctypes.c_void_p]
	gdiplus.GdipDeleteGraphics.restype = ctypes.c_int
	gdiplus.GdipDisposeImage.argtypes = [ctypes.c_void_p]
	gdiplus.GdipDisposeImage.restype = ctypes.c_int


def _create_picture_bitmap(picture_data, width, height):
	def check(status):
		if status:
			raise OSError(f"Could not scale picture (GDI+ status {status})")

	startup = GDIPLUSSTARTUPINPUT(1, None, False, False)
	token = ctypes.c_size_t()
	status = gdiplus.GdiplusStartup(ctypes.byref(token), ctypes.byref(startup), None)
	if status:
		raise OSError(f"GDI+ startup failed with status {status}")
	stream = None
	source = ctypes.c_void_p()
	scaled = ctypes.c_void_p()
	graphics = ctypes.c_void_p()
	attributes = ctypes.c_void_p()
	try:
		buffer = (ctypes.c_ubyte * len(picture_data)).from_buffer_copy(picture_data)
		stream = shlwapi.SHCreateMemStream(buffer, len(picture_data))
		if not stream:
			raise OSError("Could not create an image stream")
		status = gdiplus.GdipCreateBitmapFromStream(stream, ctypes.byref(source))
		if status:
			raise ValueError(f"Invalid or unsupported picture data (GDI+ status {status})")
		source_width = wintypes.UINT()
		source_height = wintypes.UINT()
		check(gdiplus.GdipGetImageWidth(source, ctypes.byref(source_width)))
		check(gdiplus.GdipGetImageHeight(source, ctypes.byref(source_height)))
		check(gdiplus.GdipCreateBitmapFromScan0(width, height, 0, 0x26200A, None, ctypes.byref(scaled)))
		check(gdiplus.GdipGetImageGraphicsContext(scaled, ctypes.byref(graphics)))
		check(gdiplus.GdipGraphicsClear(graphics, 0xFFFFFFFF))
		check(gdiplus.GdipSetInterpolationMode(graphics, 7))
		check(gdiplus.GdipCreateImageAttributes(ctypes.byref(attributes)))
		check(gdiplus.GdipSetImageAttributesWrapMode(attributes, 3, 0, False))
		check(gdiplus.GdipDrawImageRectRectI(graphics, source, 0, 0, width, height,
			0, 0, source_width.value, source_height.value, 2, attributes, None, None))
		bitmap = wintypes.HANDLE()
		status = gdiplus.GdipCreateHBITMAPFromBitmap(scaled, ctypes.byref(bitmap), 0xFFFFFFFF)
		if status:
			raise OSError(f"Could not create picture bitmap (GDI+ status {status})")
		return bitmap.value
	finally:
		if attributes:
			gdiplus.GdipDisposeImageAttributes(attributes)
		if graphics:
			gdiplus.GdipDeleteGraphics(graphics)
		if scaled:
			gdiplus.GdipDisposeImage(scaled)
		if source:
			gdiplus.GdipDisposeImage(source)
		if stream:
			vtable = ctypes.cast(stream, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
			release = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(vtable[2])
			release(stream)
		gdiplus.GdiplusShutdown(token)


class ViewportMode(IntEnum):
	FREE = 0
	MIN = 1


class Viewport:
	"""A native viewport containing a scrollable canvas window."""

	def __init__(self, title="Viewport", width=800, height=600, canvas_width=1600, canvas_height=1200,
			mode=ViewportMode.FREE, parent=None):
		if canvas_width <= 0 or canvas_height <= 0:
			raise ValueError("Canvas dimensions must be positive")
		self._mode = ViewportMode(mode)
		self.canvas_width = canvas_width
		self.canvas_height = canvas_height
		self.original_canvas_size = (canvas_width, canvas_height)
		self.controls = []
		self._thread = threading.get_ident()
		self._zoom = 1.0
		self._fonts = {}
		self._bitmaps = {}
		self._wheel_delta = 0
		self._horizontal_wheel_delta = 0
		self._vertical_wheel_delta = 0
		self.canvas = None
		self._updating_scrollbars = False
		self._ready = False
		self._closed = False
		self._finished = False
		self.instance = kernel32.GetModuleHandleW(None)
		if not self.instance:
			raise ctypes.WinError(ctypes.get_last_error())

		self.class_name = f"Viewport_{uuid4().hex}"
		self._wndproc = WNDPROC(self._window_proc)
		window_class = WNDCLASS()
		window_class.lpfnWndProc = self._wndproc
		window_class.hInstance = self.instance
		window_class.hCursor = user32.LoadCursorW(None, ctypes.cast(32512, wintypes.LPCWSTR))
		window_class.hbrBackground = wintypes.HBRUSH(6)
		window_class.lpszClassName = self.class_name

		if not user32.RegisterClassW(ctypes.byref(window_class)):
			raise ctypes.WinError(ctypes.get_last_error())

		style = WS_HSCROLL | WS_VSCROLL | (WS_CHILD | WS_CLIPSIBLINGS if parent else WS_OVERLAPPEDWINDOW)
		position = 0 if parent else -2147483648
		self.hwnd = user32.CreateWindowExW(
			0, self.class_name, title, style, position, position, width, height,
			parent, None, self.instance, None,
		)
		if not self.hwnd:
			error = ctypes.get_last_error()
			user32.UnregisterClassW(self.class_name, self.instance)
			raise ctypes.WinError(error)

		self.canvas = user32.CreateWindowExW(
			0, "STATIC", "", WS_CHILD | WS_VISIBLE | SS_WHITERECT,
			0, 0, canvas_width, canvas_height, self.hwnd, None, self.instance, None,
		)
		if not self.canvas:
			error = ctypes.get_last_error()
			user32.DestroyWindow(self.hwnd)
			user32.UnregisterClassW(self.class_name, self.instance)
			raise ctypes.WinError(error)
		self._ready = True
		self._update_scrollbars()
		self._layout_scales = self._control_scales(self.zoom)

	@property
	def mode(self):
		"""The canvas sizing mode."""
		return self._mode

	@mode.setter
	def mode(self, value):
		if self._closed:
			raise RuntimeError("Cannot change the mode of a closed viewport")
		mode = ViewportMode(value)
		if mode != self._mode:
			self._mode = mode
			self._update_scrollbars()
			self._relayout_controls()

	@property
	def zoom(self):
		"""The current canvas scale, where 1.0 is the original size."""
		return self._zoom

	@zoom.setter
	def zoom(self, value):
		if self._closed:
			raise RuntimeError("Cannot zoom a closed viewport")
		if not math.isfinite(value) or not 0.05 <= value <= 10.0:
			raise ValueError("Zoom must be between 0.05 and 10.0")
		self._set_zoom(value)

	def set_visible(self, visible=True):
		"""Show or hide the viewport without closing it."""
		if self._closed:
			raise RuntimeError("Cannot change visibility of a closed viewport")
		user32.ShowWindow(self.hwnd, SW_SHOW if visible else SW_HIDE)
		if visible:
			user32.UpdateWindow(self.hwnd)

	def resize(self, width, height, x=None, y=None):
		"""Resize the viewport and optionally move it in parent coordinates."""
		if self._closed:
			raise RuntimeError("Cannot resize a closed viewport")
		if width < 0 or height < 0:
			raise ValueError("Viewport dimensions must not be negative")
		if (x is None) != (y is None):
			raise ValueError("Both x and y are required to move a viewport")
		flags = SWP_NOZORDER | SWP_NOACTIVATE
		if x is None:
			flags |= SWP_NOMOVE
		if not user32.SetWindowPos(self.hwnd, None, x or 0, y or 0, width, height, flags):
			raise ctypes.WinError(ctypes.get_last_error())

	def close(self):
		"""Destroy the viewport and release its registered window class."""
		if threading.get_ident() != self._thread:
			raise RuntimeError("Viewport must be closed on its creating thread")
		if self._finished:
			return
		if not self._closed and not user32.DestroyWindow(self.hwnd):
			raise ctypes.WinError(ctypes.get_last_error())
		self.loop()

	def add_control(self, class_name, text="", x=0, y=0, width=100, height=30,
			style=0, ex_style=0, control_id=0, font_size=12):
		"""Create a visible child control at canvas-relative pixel coordinates."""
		if self._closed:
			raise RuntimeError("Cannot add a control to a closed viewport")
		if width <= 0 or height <= 0:
			raise ValueError("Control dimensions must be positive")
		if font_size <= 0:
			raise ValueError("Font size must be positive")
		scale_x, scale_y = self._control_scales(self.zoom)
		font_scale = min(scale_x, scale_y)
		is_combo = class_name.upper() == "COMBOBOX"
		initial_scale_x = 1.0 if is_combo else scale_x
		initial_scale_y = 1.0 if is_combo else scale_y
		font = self._create_font(font_size, 1.0 if is_combo else font_scale)
		control = user32.CreateWindowExW(
			ex_style, class_name, text, WS_CHILD | WS_VISIBLE | style,
			round(x * scale_x), round(y * scale_y),
			max(1, round(width * initial_scale_x)), max(1, round(height * initial_scale_y)),
			self.canvas, control_id, self.instance, None,
		)
		if not control:
			error = ctypes.get_last_error()
			gdi32.DeleteObject(font)
			raise ctypes.WinError(error)
		try:
			user32.SendMessageW(control, WM_SETFONT, font, True)
			entry = {"hwnd": control, "x": x, "y": y, "width": width,
				"height": height, "font_size": font_size}
			if is_combo:
				child = self._combo_edit(control)
				if child is not None:
					entry["child"] = child
				if (scale_x, scale_y) != (1.0, 1.0):
					scaled_font = self._create_font(font_size, font_scale)
					user32.MoveWindow(control, round(x * scale_x), round(y * scale_y),
						max(1, round(width * scale_x)), max(1, round(height * scale_y)), True)
					user32.SendMessageW(control, WM_SETFONT, scaled_font, True)
					gdi32.DeleteObject(font)
					font = scaled_font
					if child is not None:
						self._move_combo_edit(control, child, scale_x, scale_y)
		except Exception:
			user32.DestroyWindow(control)
			gdi32.DeleteObject(font)
			raise
		self.controls.append(entry)
		self._fonts[control] = font
		return control

	def add_webview(self, x=0, y=0, width=800, height=600, url="about:blank"):
		"""Create a WebView2 control on the canvas and return its browser object."""
		if threading.get_ident() != self._thread:
			raise RuntimeError("WebView controls must be created on the viewport thread")
		from webview import WebViewControl

		host = self.add_control("STATIC", x=x, y=y, width=width, height=height)
		browser = None
		try:
			scale_x, scale_y = self._control_scales(self.zoom)
			browser = WebViewControl(host, max(1, round(width * scale_x)),
				max(1, round(height * scale_y)), url)
			browser.set_zoom(min(scale_x, scale_y))
		except Exception:
			if browser is not None:
				browser.close()
			self.delete_control(host)
			raise
		entry = next(item for item in self.controls if item["hwnd"] == host)
		entry["webview"] = browser
		browser._on_close = lambda: self._webview_closed(host)
		browser._on_resize = lambda width, height: self._resize_webview(host, width, height)
		return browser

	def _webview_closed(self, host):
		if not self._closed and any(item["hwnd"] == host for item in self.controls):
			self.delete_control(host)

	def _resize_webview(self, host, width, height):
		entry = next(item for item in self.controls if item["hwnd"] == host)
		rect = wintypes.RECT()
		if not user32.GetWindowRect(host, ctypes.byref(rect)):
			raise ctypes.WinError(ctypes.get_last_error())
		position = wintypes.POINT(rect.left, rect.top)
		if not user32.ScreenToClient(self.canvas, ctypes.byref(position)):
			raise ctypes.WinError(ctypes.get_last_error())
		if not user32.MoveWindow(host, position.x, position.y, width, height, True):
			raise ctypes.WinError(ctypes.get_last_error())
		scale_x, scale_y = self._control_scales(self.zoom)
		entry["width"] = width / scale_x
		entry["height"] = height / scale_y

	def _combo_edit(self, control):
		info = COMBOBOXINFO()
		info.cbSize = ctypes.sizeof(info)
		if not user32.GetComboBoxInfo(control, ctypes.byref(info)):
			raise ctypes.WinError(ctypes.get_last_error())
		class_name = ctypes.create_unicode_buffer(256)
		if not user32.GetClassNameW(info.hwndItem, class_name, len(class_name)):
			raise ctypes.WinError(ctypes.get_last_error())
		if class_name.value.upper() != "EDIT":
			return None
		rect = wintypes.RECT()
		if not user32.GetWindowRect(info.hwndItem, ctypes.byref(rect)):
			raise ctypes.WinError(ctypes.get_last_error())
		position = wintypes.POINT(rect.left, rect.top)
		if not user32.ScreenToClient(control, ctypes.byref(position)):
			raise ctypes.WinError(ctypes.get_last_error())
		return {"hwnd": info.hwndItem, "x": position.x, "y": position.y,
			"width": rect.right - rect.left, "height": rect.bottom - rect.top}

	def _move_combo_edit(self, control, child, scale_x, scale_y=None):
		if scale_y is None:
			scale_y = scale_x
		x = round(child["x"] * scale_x)
		y = round(child["y"] * scale_y)
		width = max(1, round(child["width"] * scale_x))
		height = max(1, round(child["height"] * scale_y))
		if user32.GetWindowLongW(control, GWL_STYLE) & 3 == CBS_DROPDOWN:
			field_height = max(1, height + 2 * (y - child["y"]))
			user32.SendMessageW(control, CB_SETITEMHEIGHT, ctypes.c_size_t(-1).value, field_height)
		user32.MoveWindow(child["hwnd"], x, y, width, height, True)

	def delete_control(self, control):
		"""Destroy a canvas control and release its resources."""
		if self._closed:
			raise RuntimeError("Cannot delete a control from a closed viewport")
		control = getattr(control, "host_hwnd", control)
		entry = next((item for item in self.controls if item["hwnd"] == control), None)
		if entry is None:
			raise ValueError("Control does not belong to this viewport")
		if not user32.DestroyWindow(control):
			raise ctypes.WinError(ctypes.get_last_error())
		self.controls.remove(entry)
		if "webview" in entry:
			entry["webview"].close()
		gdi32.DeleteObject(self._fonts.pop(control))
		for bitmap in set(self._bitmaps.pop(control, ())):
			if bitmap:
				gdi32.DeleteObject(bitmap)

	def set_picture(self, control, picture_data):
		"""Display encoded picture bytes in a canvas STATIC control."""
		if self._closed:
			raise RuntimeError("Cannot set a picture on a closed viewport")
		entry = next((item for item in self.controls if item["hwnd"] == control), None)
		if entry is None:
			raise ValueError("Control does not belong to this viewport")
		if "webview" in entry:
			raise ValueError("Cannot set a picture on a WebView control")
		class_name = ctypes.create_unicode_buffer(256)
		if not user32.GetClassNameW(control, class_name, len(class_name)) or class_name.value.upper() != "STATIC":
			raise ValueError("Pictures require a STATIC control")
		data = memoryview(picture_data).tobytes()
		if not data:
			raise ValueError("Picture data must not be empty")
		if len(data) > 0xFFFFFFFF:
			raise ValueError("Picture data is too large")
		scale_x, scale_y = self._control_scales(self.zoom)
		bitmap = _create_picture_bitmap(data, max(1, round(entry["width"] * scale_x)),
			max(1, round(entry["height"] * scale_y)))
		style = user32.GetWindowLongW(control, GWL_STYLE)
		ctypes.set_last_error(0)
		result = user32.SetWindowLongW(control, GWL_STYLE, (style & ~SS_TYPEMASK) | SS_BITMAP)
		if not result and ctypes.get_last_error():
			error = ctypes.get_last_error()
			gdi32.DeleteObject(bitmap)
			raise ctypes.WinError(error)
		self._set_control_bitmap(control, bitmap)
		entry["picture_data"] = data

	def _set_control_bitmap(self, control, bitmap):
		user32.SendMessageW(control, STM_SETIMAGE, IMAGE_BITMAP, bitmap)
		displayed = ctypes.c_void_p(user32.SendMessageW(control, STM_GETIMAGE, IMAGE_BITMAP, 0)).value
		old_bitmaps = self._bitmaps.get(control, ())
		self._bitmaps[control] = (bitmap, displayed)
		for old_bitmap in set(old_bitmaps):
			if old_bitmap:
				gdi32.DeleteObject(old_bitmap)

	def _create_font(self, font_size, zoom):
		dc = user32.GetDC(self.hwnd)
		if not dc:
			raise ctypes.WinError(ctypes.get_last_error())
		try:
			dpi = gdi32.GetDeviceCaps(dc, 90)
		finally:
			user32.ReleaseDC(self.hwnd, dc)
		height = -max(1, round(font_size * zoom * dpi / 72))
		font = gdi32.CreateFontW(height, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 0, 0, None)
		if not font:
			raise ctypes.WinError(ctypes.get_last_error())
		return font

	def _zoom_wheel(self, wparam):
		if not wparam & MK_CONTROL:
			return False
		delta = ctypes.c_short((wparam >> 16) & 0xFFFF).value
		self._wheel_delta += delta
		steps = abs(self._wheel_delta) // WHEEL_DELTA
		if self._wheel_delta < 0:
			steps = -steps
		self._wheel_delta -= steps * WHEEL_DELTA
		if steps:
			self.zoom = round(max(0.05, min(10.0, self.zoom + steps * 0.05)), 2)
		return True

	def _handle_wheel(self, wparam):
		if wparam & MK_CONTROL:
			return self._zoom_wheel(wparam)
		horizontal = bool(wparam & MK_SHIFT)
		delta = ctypes.c_short((wparam >> 16) & 0xFFFF).value
		if horizontal:
			self._horizontal_wheel_delta += delta
			pending = self._horizontal_wheel_delta
		else:
			self._vertical_wheel_delta += delta
			pending = self._vertical_wheel_delta
		steps = abs(pending) // WHEEL_DELTA
		if pending < 0:
			steps = -steps
		pending -= steps * WHEEL_DELTA
		if horizontal:
			self._horizontal_wheel_delta = pending
		else:
			self._vertical_wheel_delta = pending
		for _ in range(abs(steps)):
			self._scroll(SB_HORZ if horizontal else SB_VERT, SB_LINEUP if steps > 0 else SB_LINEDOWN)
		return True

	def _set_zoom(self, zoom):
		if zoom == self.zoom:
			return
		scale_x, scale_y = self._control_scales(zoom)
		resources = None
		if (scale_x, scale_y) != self._layout_scales:
			resources = self._prepare_control_layout(scale_x, scale_y)
		self._zoom = zoom
		self._update_scrollbars()
		if resources is not None:
			self._apply_control_layout(scale_x, scale_y, *resources)

	def _prepare_control_layout(self, scale_x, scale_y):
		font_scale = min(scale_x, scale_y)
		fonts = {}
		bitmaps = {}
		try:
			for control in self.controls:
				fonts[control["hwnd"]] = self._create_font(control["font_size"], font_scale)
				if "picture_data" in control:
					bitmaps[control["hwnd"]] = _create_picture_bitmap(control["picture_data"],
						max(1, round(control["width"] * scale_x)), max(1, round(control["height"] * scale_y)))
		except Exception:
			for font in fonts.values():
				gdi32.DeleteObject(font)
			for bitmap in bitmaps.values():
				gdi32.DeleteObject(bitmap)
			raise
		return fonts, bitmaps

	def _relayout_controls(self):
		scale_x, scale_y = self._control_scales(self.zoom)
		if (scale_x, scale_y) != self._layout_scales:
			fonts, bitmaps = self._prepare_control_layout(scale_x, scale_y)
			self._apply_control_layout(scale_x, scale_y, fonts, bitmaps)

	def _apply_control_layout(self, scale_x, scale_y, fonts, bitmaps):
		for control in self.controls:
			hwnd = control["hwnd"]
			width = max(1, round(control["width"] * scale_x))
			height = max(1, round(control["height"] * scale_y))
			user32.MoveWindow(hwnd, round(control["x"] * scale_x), round(control["y"] * scale_y),
				width, height, True)
			if "webview" in control:
				control["webview"]._resize_content(width, height)
				control["webview"].set_zoom(min(scale_x, scale_y))
			user32.SendMessageW(hwnd, WM_SETFONT, fonts[hwnd], True)
			if "child" in control:
				self._move_combo_edit(hwnd, control["child"], scale_x, scale_y)
			gdi32.DeleteObject(self._fonts[hwnd])
			if hwnd in bitmaps:
				self._set_control_bitmap(hwnd, bitmaps[hwnd])
		self._fonts = fonts
		self._layout_scales = (scale_x, scale_y)

	def _window_proc(self, hwnd, message, wparam, lparam):
		if message == WM_DESTROY:
			if self._ready:
				self._closed = True
				for control in self.controls:
					if "webview" in control:
						control["webview"].close()
			return 0
		if message == WM_SIZE and self.canvas and not self._updating_scrollbars:
			self._update_scrollbars()
			if self.mode == ViewportMode.MIN:
				self._relayout_controls()
			return 0
		if message == WM_MOUSEWHEEL and self._handle_wheel(wparam):
			return 0
		if message in (WM_HSCROLL, WM_VSCROLL) and self.canvas:
			self._scroll(SB_HORZ if message == WM_HSCROLL else SB_VERT, wparam & 0xFFFF)
			return 0
		return user32.DefWindowProcW(hwnd, message, wparam, lparam)

	def _scroll_info(self, bar):
		info = SCROLLINFO(ctypes.sizeof(SCROLLINFO), SIF_RANGE | SIF_PAGE | SIF_POS | SIF_TRACKPOS)
		if not user32.GetScrollInfo(self.hwnd, bar, ctypes.byref(info)):
			raise ctypes.WinError(ctypes.get_last_error())
		return info

	def _move_canvas(self):
		horizontal = self._scroll_info(SB_HORZ)
		vertical = self._scroll_info(SB_VERT)
		rect = wintypes.RECT()
		user32.GetClientRect(self.hwnd, ctypes.byref(rect))
		canvas_width, canvas_height = self._canvas_size(rect.right - rect.left, rect.bottom - rect.top)
		x = horizontal.nPos if canvas_width < rect.right - rect.left else -horizontal.nPos
		y = vertical.nPos if canvas_height < rect.bottom - rect.top else -vertical.nPos
		user32.MoveWindow(self.canvas, x, y, canvas_width, canvas_height, True)

	def _control_scales(self, zoom):
		if self.mode == ViewportMode.FREE:
			return zoom, zoom
		rect = wintypes.RECT()
		user32.GetClientRect(self.hwnd, ctypes.byref(rect))
		width, height = self._canvas_size(rect.right - rect.left, rect.bottom - rect.top, zoom)
		base_width, base_height = self.original_canvas_size
		scale_x = width / base_width if width > max(1, round(base_width * zoom)) else zoom
		scale_y = height / base_height if height > max(1, round(base_height * zoom)) else zoom
		return scale_x, scale_y

	def _canvas_size(self, viewport_width, viewport_height, zoom=None):
		if zoom is None:
			zoom = self.zoom
		if self.mode == ViewportMode.MIN:
			base_width, base_height = self.original_canvas_size
		else:
			base_width, base_height = self.canvas_width, self.canvas_height
		width = max(1, round(base_width * zoom))
		height = max(1, round(base_height * zoom))
		if self.mode == ViewportMode.MIN:
			width = max(width, viewport_width)
			height = max(height, viewport_height)
		return width, height

	def _update_scrollbars(self):
		self._updating_scrollbars = True
		try:
			if self.mode == ViewportMode.MIN:
				user32.ShowScrollBar(self.hwnd, SB_BOTH, False)
			while True:
				rect = wintypes.RECT()
				user32.GetClientRect(self.hwnd, ctypes.byref(rect))
				width, height = rect.right - rect.left, rect.bottom - rect.top
				canvas_width, canvas_height = self._canvas_size(width, height)
				for bar, canvas_size, viewport_size in (
					(SB_HORZ, canvas_width, width),
					(SB_VERT, canvas_height, height),
				):
					mask = SIF_RANGE | SIF_PAGE
					if self.mode != ViewportMode.MIN:
						mask |= SIF_DISABLENOSCROLL
					info = SCROLLINFO(ctypes.sizeof(SCROLLINFO), mask,
						0, canvas_size + abs(viewport_size - canvas_size) - 1, canvas_size)
					user32.SetScrollInfo(self.hwnd, bar, ctypes.byref(info), True)
				user32.GetClientRect(self.hwnd, ctypes.byref(rect))
				if (width, height) == (rect.right - rect.left, rect.bottom - rect.top):
					break
			self._move_canvas()
		finally:
			self._updating_scrollbars = False

	def _scroll(self, bar, request):
		info = self._scroll_info(bar)
		position = info.nPos
		if request == SB_LINEUP:
			position -= 20
		elif request == SB_LINEDOWN:
			position += 20
		elif request == SB_PAGEUP:
			position -= info.nPage
		elif request == SB_PAGEDOWN:
			position += info.nPage
		elif request in (SB_THUMBPOSITION, SB_THUMBTRACK):
			position = info.nTrackPos
		elif request == SB_TOP:
			position = info.nMin
		elif request == SB_BOTTOM:
			position = info.nMax
		else:
			return
		info.fMask = SIF_POS
		info.nPos = position
		user32.SetScrollInfo(self.hwnd, bar, ctypes.byref(info), True)
		self._move_canvas()

	def loop(self):
		"""Process pending messages and return whether the viewport is open."""
		if self._finished:
			return False
		message = wintypes.MSG()
		for _ in range(100):
			if self._closed or not user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
				break
			if message.message == WM_QUIT:
				user32.PostQuitMessage(message.wParam)
				if not user32.DestroyWindow(self.hwnd):
					raise ctypes.WinError(ctypes.get_last_error())
				break
			if (message.message == WM_MOUSEWHEEL and
					(message.hWnd == self.hwnd or user32.IsChild(self.hwnd, message.hWnd)) and
					self._handle_wheel(message.wParam)):
				continue
			user32.TranslateMessage(ctypes.byref(message))
			user32.DispatchMessageW(ctypes.byref(message))
		if self._closed:
			for font in self._fonts.values():
				gdi32.DeleteObject(font)
			self._fonts.clear()
			for bitmaps in self._bitmaps.values():
				for bitmap in set(bitmaps):
					if bitmap:
						gdi32.DeleteObject(bitmap)
			self._bitmaps.clear()
			if not user32.UnregisterClassW(self.class_name, self.instance):
				raise ctypes.WinError(ctypes.get_last_error())
			self._finished = True
			return False
		for control in self.controls:
			if "webview" in control:
				control["webview"].loop()
		return True


setup_win32()


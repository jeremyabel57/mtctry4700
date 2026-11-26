import ctypes
import importlib
import importlib.metadata
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path


_webview_dll_directory = None


def _webview2_types():
	global _webview_dll_directory
	try:
		library = Path(str(importlib.metadata.distribution("pywebview").locate_file("webview/lib")))
		clr = importlib.import_module("clr")
	except (ImportError, importlib.metadata.PackageNotFoundError) as error:
		raise RuntimeError("Embedded WebView requires pywebview and pythonnet") from error
	architecture = "win-arm64" if os.environ.get("PROCESSOR_ARCHITECTURE", "").upper() == "ARM64" else (
		"win-x64" if ctypes.sizeof(ctypes.c_void_p) == 8 else "win-x86")
	if _webview_dll_directory is None:
		_webview_dll_directory = os.add_dll_directory(str(library / "runtimes" / architecture / "native"))
	clr.AddReference("System.Windows.Forms")
	clr.AddReference(str(library / "Microsoft.Web.WebView2.Core.dll"))
	clr.AddReference(str(library / "Microsoft.Web.WebView2.WinForms.dll"))
	forms = importlib.import_module("Microsoft.Web.WebView2.WinForms")
	drawing = importlib.import_module("System.Drawing")
	return forms.WebView2, forms.CoreWebView2CreationProperties, drawing.Size


class WebViewControl:
	"""A WebView2 control hosted by an existing native window."""

	def __init__(self, parent, width=800, height=600, url="about:blank"):
		if width <= 0 or height <= 0:
			raise ValueError("Control dimensions must be positive")
		if not isinstance(url, str) or not url:
			raise ValueError("URL must be a non-empty string")
		user32 = ctypes.WinDLL("user32", use_last_error=True)
		user32.IsWindow.argtypes = [ctypes.c_void_p]
		user32.IsWindow.restype = ctypes.c_int
		user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
		user32.GetWindowThreadProcessId.restype = ctypes.c_ulong
		kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
		kernel32.GetCurrentThreadId.argtypes = []
		kernel32.GetCurrentThreadId.restype = ctypes.c_ulong
		if not user32.IsWindow(parent):
			raise ValueError("Parent must be a valid window")
		if user32.GetWindowThreadProcessId(parent, None) != kernel32.GetCurrentThreadId():
			raise RuntimeError("WebViewControl must be created on the parent window's thread")
		self._thread = threading.get_ident()
		self._closed = False
		self._ready = False
		self._loaded = False
		self._navigation_id = None
		self._error = None
		self._url = url
		self._zoom = 1.0
		self._on_close: Callable[[], None] | None = None
		self._on_resize: Callable[[int, int], None] | None = None
		self.host_hwnd = parent
		self._ole32 = ctypes.OleDLL("ole32")
		self._ole32.OleInitialize.argtypes = [ctypes.c_void_p]
		self._ole32.OleInitialize.restype = ctypes.c_long
		self._ole32.OleUninitialize.argtypes = []
		self._ole32.OleUninitialize.restype = None
		self._ole32.OleInitialize(None)
		control = None
		try:
			control_type, properties_type, self._size_type = _webview2_types()
			control = control_type()
			self._control = control
			properties = properties_type()
			properties.UserDataFolder = os.path.join(
				os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "mtctry4700", "EmbeddedWebView2")
			self._control.CreationProperties = properties
			self._control.Size = self._size_type(width, height)
			self._control.CoreWebView2InitializationCompleted += self._initialized
			self._control.NavigationStarting += self._navigation_started
			self._control.NavigationCompleted += self._navigation_completed
			self.hwnd = self._control.Handle.ToInt64()
			user32.SetParent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
			user32.SetParent.restype = ctypes.c_void_p
			ctypes.set_last_error(0)
			if not user32.SetParent(self.hwnd, parent) and ctypes.get_last_error():
				raise ctypes.WinError(ctypes.get_last_error())
			self._control.Visible = True
			self._control.EnsureCoreWebView2Async(None)
		except Exception:
			if control is not None:
				control.Dispose()
			self._ole32.OleUninitialize()
			raise

	def _initialized(self, sender, event):
		if self._closed:
			return
		if not event.IsSuccess:
			self._error = str(event.InitializationException)
			return
		try:
			self._control.ZoomFactor = self._zoom
			self._control.CoreWebView2.Navigate(self._url)
			self._ready = True
		except Exception as error:
			self._error = str(error)

	def _navigation_started(self, sender, event):
		self._navigation_id = event.NavigationId
		self._loaded = False

	def _navigation_completed(self, sender, event):
		if event.NavigationId == self._navigation_id:
			self._loaded = bool(event.IsSuccess)

	def _check_open(self):
		if threading.get_ident() != self._thread:
			raise RuntimeError("WebViewControl must be used on its creating thread")
		if self._closed:
			raise RuntimeError("WebViewControl is closed")
		if self._error:
			raise RuntimeError(f"WebView2 initialization failed: {self._error}")

	def set_url(self, url):
		"""Navigate now or when asynchronous initialization finishes."""
		self._check_open()
		if not isinstance(url, str) or not url:
			raise ValueError("URL must be a non-empty string")
		self._url = url
		self._loaded = False
		if self._ready:
			self._control.CoreWebView2.Navigate(url)

	def resize(self, width, height):
		"""Resize the embedded browser in parent-window pixels."""
		self._check_open()
		if width <= 0 or height <= 0:
			raise ValueError("Control dimensions must be positive")
		if self._on_resize is not None:
			self._on_resize(width, height)
		self._resize_content(width, height)

	def _resize_content(self, width, height):
		self._control.Size = self._size_type(width, height)

	def set_visible(self, visible=True):
		"""Show or hide the embedded browser."""
		self._check_open()
		self._control.Visible = bool(visible)

	def set_zoom(self, zoom):
		"""Set the browser content zoom factor."""
		self._check_open()
		if zoom <= 0:
			raise ValueError("Zoom must be positive")
		self._zoom = zoom
		if self._ready:
			self._control.ZoomFactor = zoom

	@property
	def ready(self):
		"""Whether WebView2 has finished initializing."""
		self._check_open()
		return self._ready

	@property
	def loaded(self):
		"""Whether the latest navigation completed successfully."""
		self._check_open()
		return self._loaded

	def loop(self):
		if self._closed:
			return False
		self._check_open()
		return True

	def close(self):
		if self._closed:
			return
		if threading.get_ident() != self._thread:
			raise RuntimeError("WebViewControl must be used on its creating thread")
		try:
			self._control.Dispose()
		finally:
			self._closed = True
			self._ole32.OleUninitialize()
			on_close = self._on_close
			self._on_close = None
			self._on_resize = None
			if on_close is not None:
				on_close()


class WebView:
	"""A separate, non-blocking Microsoft Edge WebView2 window."""

	def __init__(self, title="WebView", width=800, height=600, url="about:blank"):
		if width <= 0 or height <= 0:
			raise ValueError("Window dimensions must be positive")
		if not isinstance(url, str) or not url:
			raise ValueError("URL must be a non-empty string")
		self._lock = threading.RLock()
		self._replies = queue.Queue()
		self._closed = False
		self._process = subprocess.Popen(
			[sys.executable, "-u", str(Path(__file__).resolve()), "--webview-worker"],
			stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8",
			creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
		)
		threading.Thread(target=self._read_replies, daemon=True).start()
		try:
			self.hwnd = self._request("start", title=title, width=width, height=height, url=url)
		except Exception:
			self._stop_process()
			raise

	def _read_replies(self):
		output = self._process.stdout
		if output is None:
			self._replies.put(None)
			return
		try:
			for line in output:
				try:
					message = json.loads(line)
					if isinstance(message, dict) and "ok" in message:
						self._replies.put(message)
				except json.JSONDecodeError:
					continue
		finally:
			self._replies.put(None)

	def _request(self, command, **arguments):
		with self._lock:
			if self._closed or self._process.poll() is not None:
				raise RuntimeError("WebView is closed")
			input_stream = self._process.stdin
			if input_stream is None:
				raise RuntimeError("WebView input is unavailable")
			try:
				input_stream.write(json.dumps({"command": command, **arguments}) + "\n")
				input_stream.flush()
			except (BrokenPipeError, OSError) as error:
				raise RuntimeError("WebView process stopped") from error
			try:
				reply = self._replies.get(timeout=30)
			except queue.Empty as error:
				self._closed = True
				self._stop_process()
				raise TimeoutError("WebView did not respond") from error
			if reply is None:
				raise RuntimeError("WebView process stopped")
			if not reply.get("ok"):
				raise RuntimeError(reply.get("error", "WebView operation failed"))
			return reply.get("result")

	def set_url(self, url):
		"""Navigate to a URL."""
		if not isinstance(url, str) or not url:
			raise ValueError("URL must be a non-empty string")
		self._request("navigate", url=url)

	def resize(self, width, height):
		"""Resize the browser window in logical pixels."""
		if width <= 0 or height <= 0:
			raise ValueError("Window dimensions must be positive")
		self._request("resize", width=width, height=height)

	def set_visible(self, visible=True):
		"""Show or hide the browser window."""
		self._request("visibility", visible=bool(visible))

	def loop(self):
		"""Return whether the browser window is still open."""
		return not self._closed and self._process.poll() is None

	def _stop_process(self):
		if self._process.stdin:
			try:
				self._process.stdin.close()
			except OSError:
				pass
		try:
			self._process.wait(timeout=10)
		except subprocess.TimeoutExpired:
			self._process.terminate()
			try:
				self._process.wait(timeout=5)
			except subprocess.TimeoutExpired:
				self._process.kill()
				self._process.wait()
		if self._process.stdout:
			self._process.stdout.close()

	def close(self):
		"""Close the browser window and stop its process."""
		with self._lock:
			if self._closed:
				return
			try:
				if self._process.poll() is None:
					self._request("close")
			finally:
				self._closed = True
				self._stop_process()

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		self.close()


def _worker():
	output = sys.stdout
	sys.stdout = sys.stderr

	def reply(**message):
		output.write(json.dumps(message) + "\n")
		output.flush()

	try:
		configuration = json.loads(sys.stdin.readline())
		if configuration.get("command") != "start":
			raise ValueError("Expected a start request")
		workspace = Path(__file__).resolve().parent
		sys.path = [path for path in sys.path if Path(path or os.getcwd()).resolve() != workspace]
		backend = importlib.import_module("webview")

		window = backend.create_window(
			configuration["title"], configuration["url"], width=configuration["width"],
			height=configuration["height"], hidden=True, min_size=(1, 1),
		)

		def serve():
			if not window.events.shown.wait(20):
				reply(ok=False, error="WebView2 window failed to initialize")
				return
			if backend.renderer != "edgechromium":
				reply(ok=False, error="Microsoft Edge WebView2 Runtime is required")
				window.destroy()
				return
			reply(ok=True, result=window.native.Handle.ToInt64())
			for line in sys.stdin:
				try:
					message = json.loads(line)
					command = message["command"]
					if command == "navigate":
						window.load_url(message["url"])
					elif command == "resize":
						window.resize(message["width"], message["height"])
					elif command == "visibility":
						window.show() if message["visible"] else window.hide()
					elif command == "current_url":
						reply(ok=True, result=window.get_current_url())
						continue
					elif command == "size":
						reply(ok=True, result=[window.width, window.height])
						continue
					elif command == "close":
						reply(ok=True)
						window.destroy()
						return
					else:
						raise ValueError(f"Unknown WebView command: {command}")
					reply(ok=True)
				except Exception as error:
					reply(ok=False, error=f"{type(error).__name__}: {error}")
			window.destroy()

		threading.Thread(target=serve, daemon=True).start()
		backend.start(gui="edgechromium")
	except Exception as error:
		reply(ok=False, error=f"{type(error).__name__}: {error}")


if __name__ == "__main__" and sys.argv[1:] == ["--webview-worker"]:
	_worker()

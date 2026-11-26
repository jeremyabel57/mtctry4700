# mtctry4700

Running `python main.py` installs the Python dependencies from
`requirements.txt` before opening the main window with three viewport tabs,
using the same interpreter.
This requires `pip` and network access if packages need to be downloaded.
Importing `main` does not install packages. The installer does not install the
Microsoft Edge WebView2 Runtime or .NET.

## Tabbed Window

`MainWindow` provides a native resizable tab control and a status bar. Each
added tab owns one viewport:

```python
import time
from winmain import MainWindow

window = MainWindow(title="My Application")
first = window.add_tab("First")
first.add_control("BUTTON", "Click", x=20, y=20)
window.add_tab("Second")
window.select_tab(0)
window.set_status("Ready")
window.set_visible(True)

while window.loop():
	time.sleep(0.01)
```

The selected viewport fills the tab's content area; other viewports are hidden.
Create and use the window and its viewports on the same thread. The window
starts hidden and `window.close()` closes its viewports and releases resources.

## WebView2 window

Install the WebView dependency with `python -m pip install -r requirements.txt`.
Windows must have the Microsoft Edge WebView2 Runtime installed.

```python
from webview import WebView

browser = WebView(title="Browser", width=800, height=600)
browser.set_url("https://example.com")
browser.resize(1024, 768)
browser.set_visible(True)

# Later, hide or close the window:
browser.set_visible(False)
browser.close()
```

The window starts hidden. Each `WebView` runs its own GUI process, so the
application can continue running without starting another message loop.
`browser.loop()` returns `False` after the window is closed. `close()` releases
the process; the class also supports a `with WebView(...) as browser:` block.
Window dimensions are in logical pixels.

## Embedded WebView2

Use `add_webview()` to place a browser inside a viewport's canvas:

```python
import time
from wincanvas import Viewport

viewport = Viewport(canvas_width=1200, canvas_height=900)
browser = viewport.add_webview(x=40, y=40, width=600, height=400,
	url="https://example.com")
viewport.set_visible(True)

while viewport.loop():
	time.sleep(0.01)
```

The browser is initialized asynchronously on the viewport thread; the viewport
loop must run to process its messages. `browser.ready` reports initialization,
and `browser.loaded` reports successful navigation. `set_url()`, `resize()`, and
`set_visible()` control the embedded browser. Its canvas position and size
follow scrolling, zoom, and `MIN` mode; WebView2 may clamp content zoom to its
supported range. `viewport.delete_control(browser)` or `browser.close()` removes
it. Closing the viewport also disposes its browsers. Create and use embedded
browsers on the viewport's thread.

For another native host window, `WebViewControl(parent_hwnd, width, height, url)`
creates a child browser directly; the host must pump Windows messages and close
the control before destroying its parent. Embedded WebView2 stores browser data in
`%LOCALAPPDATA%\mtctry4700\EmbeddedWebView2`.

## Win32 viewport

On Windows, the module provides a viewport containing a scrollable canvas.
No external packages are required.

To use the class in another script:

```python
import time

from wincanvas import Viewport

viewport = Viewport(
	title="My Viewport", width=800, height=600,
	canvas_width=1600, canvas_height=1200,
)
button = viewport.add_control("BUTTON", "Click", x=20, y=20, width=100, height=30, control_id=1, font_size=12)
text_box = viewport.add_control("EDIT", "Hello", x=20, y=60, width=200, height=30)
viewport.set_visible(True)

while viewport.loop():
	time.sleep(0.01)
```

`viewport.hwnd` is the viewport's Win32 window handle, and `viewport.canvas`
is the child canvas handle. Canvas dimensions are in pixels. Scrollbars appear
on both axes and reposition the child window. A larger canvas scrolls through
the viewport; a smaller canvas can be moved within the available space. Each
scrollbar's page size is the corresponding scaled canvas dimension, and it is
disabled when the canvas exactly fits that axis.
The viewport starts hidden; call `set_visible(True)` to show it and
`set_visible(False)` to hide it without closing it.

`ViewportMode.FREE` (`0`, the default) keeps the canvas at its original scaled
size. `ViewportMode.MIN` (`1`) expands each canvas dimension to fill
the viewport, but never below the original canvas dimension at the current
zoom. The original dimensions are stored in `viewport.original_canvas_size`.
In `MIN` mode, controls scale from their original coordinates and dimensions
along with each canvas axis as the viewport or zoom changes. Pictures follow
the same dimensions; text uses the smaller axis scale to preserve its shape.
Choose a mode when creating the viewport or change it later:

```python
from wincanvas import ViewportMode

viewport.mode = ViewportMode.MIN
```

Create the viewport and process its messages on the same thread. Each `loop()`
call processes pending messages without waiting for new ones, returning `True`
while the viewport is open and `False` after it closes. Call `viewport.loop()`
regularly until it returns `False` so the window is cleaned up. The loop is
intended for one viewport at a time per thread.

`add_control()` returns the Win32 handle of a visible control parented to the
canvas. Its coordinates and dimensions are in pixels relative to the canvas.
Use the optional `style`, `ex_style`, and `control_id` arguments for Win32
control-specific styles and identifiers; `font_size` is in points and defaults
to 12. Create controls on the viewport's thread. Control notifications go to
the canvas; this module does not yet expose notification callbacks.
Call `viewport.delete_control(handle)` on that thread to remove a control and
release its font and any picture resources.

To display a picture, create a `STATIC` control and supply encoded image bytes:

```python
picture = viewport.add_control("STATIC", x=20, y=100, width=320, height=180)
with open("picture.png", "rb") as image_file:
	viewport.set_picture(picture, image_file.read())
```

GDI+ decodes common image formats, including PNG, JPEG, BMP, GIF, and TIFF.
Images are stretched to the control's dimensions; transparency is composited on
white. The control's entry in `viewport.controls` stores the original bytes as
`picture_data`, and zooming resizes from those bytes rather than a scaled copy.
Call `set_picture()` again to replace an image.

`viewport.controls` contains a dictionary for each control with its `hwnd` and
original `x`, `y`, `width`, `height`, and `font_size` values. These values do not
change when zooming. Editable combo boxes also have a `child` dictionary with
the edit control's handle and original geometry, relative to the combo box.
Win32 may clip the edit field at very large font sizes and zoom levels.
Hold Ctrl and turn the mouse wheel to change `viewport.zoom`
in 0.05 increments. Zoom is limited to 0.05 through 10.0, with 1.0 being the
original size. Assigning `viewport.zoom` also rescales the canvas and controls.
Turn the mouse wheel to scroll vertically. Hold Shift to scroll horizontally:
wheel up moves left, and wheel down moves right. If Ctrl and Shift are both
held, the wheel zooms.
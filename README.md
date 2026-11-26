# mtctry4700

Running `python main.py` installs the Python dependencies from
`requirements.txt` before opening the main window with three viewport tabs,
using the same interpreter.
This requires `pip` and network access if packages need to be downloaded.
Importing `main` does not install packages. The installer does not install the
Microsoft Edge WebView2 Runtime or .NET.

## Instrument Queue

`viqueue` owns an instrument dictionary, request and response queues, and a
script execution stack. Install `requirements.txt` before using it. VISA
VXI-11 connections also require an installed VISA implementation such as
NI-VISA; a `raw:` address uses a TCP socket instead. Modbus uses TCP port 502
by default, configurable through `device.instrument["mbIpPort"]`.

```python
from viqueue import viqueue

device = viqueue("raw:192.0.2.1:5025")
try:
	device.request("*IDN?")
	device.flush()
	value, status = device.response()
finally:
	device.close()
```

Call `loop()` repeatedly for nonblocking operation; `flush()` waits for queued
work to finish and raises `TimeoutError` if its deadline expires. Responses
are `(value, status)` pairs, with status `0` for success and `-1` for an
execution error. `request_blocking`, `command`, `modbus_read`, `modbus_write`,
`upload_file`, `download_file`, picture downloads, and F4T helpers are also
available. `get_id()` tries the configured SCPI protocol, the alternate SCPI
protocol, and then F4T identification.
`script()` supports basic `if`/`else`, `while`, `do`/`until`, `set`, variable
assignments, local logging and file paths, and arithmetic substitutions.
`#` and `##` script prefixes can queue file and picture downloads when a
`file` argument is supplied. Relative script paths use a per-instrument working
directory; `cd` does not change the process working directory.

`eval`, `exec`, and `execute` evaluate Python expressions. They have access to
Python builtins, shared and per-device script variables, `device`, `instrument`,
and the per-device `variables` dictionary. For example,
`$result=eval sum(values)` stores the result in `variables["result"]`.
All three directives accept expressions, not Python statements. They are not
sandboxed and can have side effects, so run only trusted scripts.

A `viqueue("main")` script queue can route instrument commands after calling
`register_device(name, device)` and executing `select name`. A `retName` command
prefix publishes a named `(value, status)` completion through `has_notice()`
and `take_notice()` instead of consuming unrelated response-queue entries.
Notice names are shared across queue instances.

Optional diagnostic edit controls can be attached with
`set_diagnostics(output=..., queue=..., stack=...)`. They must be distinct
multiline Win32 edit controls with automatic vertical scrolling, used on their
owning thread. Attaching or reattaching clears and rebuilds the queue and stack
views. [winfuncs.py](winfuncs.py) contains the edit-control helpers used here.

The port is not fully AutoIt-compatible: arbitrary AutoIt expressions and
`$oDev`/`$$` script syntax are not executed, and subnet scanning and debugger
play/step controls are not implemented. Conditions and substitutions remain
limited to supported AutoIt-style operators and variables. Test against the
target instrument before relying on this code for hardware control.

## Constants and Debugging

`myconstants` exports the color and icon constants from the AutoIt sources.
Supplementary Unicode icons are Python Unicode characters rather than explicit
UTF-16 surrogate pairs. Several source icons use `Chr` with values outside its
documented range; the Python constants use the intended Unicode characters.
`SEP` uses AutoIt's default `|`; importing this module does not change any GUI
event mode.

The included AutoIt color constants are from the [AutoIt3 include mirror](https://github.com/dbkaynor/AutoIt3/blob/master/Include/ColorConstants.au3)
and are accompanied by [AutoIt's license](AUTOIT_LICENSE.txt).
`mydebug` provides `s_print_var`, `s_print_vars`, and console equivalents;
its Python-friendly names also have AutoIt-style aliases.

## Data Types

`datatypes` provides Python versions of the helpers in the AutoIt source,
including handle checks, temperature conversion, variable and dictionary
access, binary formatting, splitting, and engineering notation. The original
function names remain available, with snake-case aliases for Python callers.
For example:

```python
from datatypes import assign_ex, eval_ex, number_engineering

variables = {"measurements": [1.0, 2.0]}
assign_ex("measurements[0]", 3.0, variables)
value = eval_ex("measurements[0]", variables)
label = number_engineering(value)
```

`AssignEx` and `EvalEx` use an explicit variable dictionary, or the module's
`g_vars` when omitted, rather than AutoIt global variables. A failed indexed
assignment returns `0`; failed lookups raise Python exceptions instead of
setting AutoIt's `@error`. The engineering formatter handles zero and values
below the smallest SI prefix, cases that exceed the original prefix loop.
File checks accept Python file objects, descriptors, and Windows file handles;
socket checks accept socket objects or native socket handles.

## File Helpers

`filemisc` provides filename incrementation, Windows path checks, INI array
and native-control persistence, and an Excel write helper. INI functions take
`section` and `filename` arguments, or use the module's `g_configSection` and
`g_configFile` defaults. GUI helpers accept Win32 control handles. Array
lookups return strings and preserve the supplied default when no data exists.
New INI files use UTF-16 so Windows profile APIs preserve Unicode.

```python
from filemisc import file_name_auto_increment, ini_read_array, ini_write_array

destination = file_name_auto_increment("capture.png")
ini_write_array([["first", "second"]], "values", "Settings", "settings.ini")
values = ini_read_array([], "values", "Settings", "settings.ini")
```

Filename generation does not reserve the returned path. `cloud_excel_write`
requires a workbook path or URL as its fifth argument, plus Windows, pywin32,
and an installed Excel application. SharePoint access must already be configured.
Excel automation errors are raised as Python exceptions. The AutoIt source's
hard-coded SharePoint URL was a placeholder, so no default target is supplied.

## Deque, Queue, and Stack

`deque` provides `Deque`, `Queue`, `Stack`, and `pQue` classes backed by
`collections.deque`. `Deque.push()` and `pop_back()` operate at the back;
`push_front()`, `pop()`, and `peek()` operate at the front. `Queue` restricts
the public operations to FIFO use, and `Stack` to LIFO use. Removing or
peeking at an empty collection raises `IndexError`.

```python
from deque import Queue, Stack, pQue

requests = Queue()
requests.push("*IDN?")
request = requests.pop()

blocks = Stack()
block = pQue("while", "$count < 3")
block.push("measurement")
blocks.push(block)
block.release()
statement = block.pc_item()
```

`pQue` retains `cmd`, `cond`, `bCond`, `skip`, and an absolute `pc`. It starts
parked; `release()` and `restart()` move the counter to the first item, and
`pc_item()` returns an item and advances without removing it. `set_done()`
moves the counter past the last item. A parked or finished `pc_item()` raises
`IndexError`. `Deque` also provides bulk transfers, shallow copies, and
front-to-back conversion through `to_array()`.

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
is the child canvas handle. Canvas dimensions are in pixels. Scrollbars
reposition the child window. In `FREE` mode, scrollbars appear on both axes:
a larger canvas scrolls through the viewport, while a smaller canvas can be
moved within the available space. Each scrollbar's page size is the
corresponding scaled canvas dimension, and it is disabled when the canvas
exactly fits that axis. In `MIN` mode, scrollbars appear only when needed.
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
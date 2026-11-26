import ctypes
from ctypes import wintypes


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.IsWindow.argtypes = [wintypes.HWND]
_user32.IsWindow.restype = wintypes.BOOL
_user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetClassNameW.restype = ctypes.c_int
_user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.GetWindowLongW.restype = wintypes.LONG
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetWindowTextW.restype = ctypes.c_int
_user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_user32.SendMessageW.restype = ctypes.c_ssize_t
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.GetCurrentThreadId.restype = wintypes.DWORD

_EM_SETSEL = 0x00B1
_EM_REPLACESEL = 0x00C2
_EM_SCROLLCARET = 0x00B7
_WM_GETTEXTLENGTH = 0x000E


def _edit(hwnd):
	if not _user32.IsWindow(hwnd):
		raise ValueError("Invalid edit control handle")
	name = ctypes.create_unicode_buffer(256)
	if not _user32.GetClassNameW(hwnd, name, len(name)) or not name.value.lower().startswith(("edit", "richedit")):
		raise ValueError("Handle is not an edit control")
	if _user32.GetWindowThreadProcessId(hwnd, None) != _kernel32.GetCurrentThreadId():
		raise RuntimeError("Edit controls must be used on their owning thread")
	return hwnd


def _replace(hwnd, start, end, text):
	buffer = ctypes.create_unicode_buffer(text)
	_user32.SendMessageW(hwnd, _EM_SETSEL, start, end)
	_user32.SendMessageW(hwnd, _EM_REPLACESEL, 0, ctypes.addressof(buffer))


def prepare_diagnostic_edit(hwnd):
	hwnd = _edit(hwnd)
	style = _user32.GetWindowLongW(hwnd, -16)
	if style & 0x44 != 0x44:
		raise ValueError("Diagnostic edits require multiline and automatic vertical scrolling")
	_user32.SendMessageW(hwnd, 0x00C5, 0, 0)


def gui_ctrl_edit_append(hwnd, text):
	hwnd = _edit(hwnd)
	end = _user32.SendMessageW(hwnd, _WM_GETTEXTLENGTH, 0, 0)
	_replace(hwnd, end, end, str(text))
	end = _user32.SendMessageW(hwnd, _WM_GETTEXTLENGTH, 0, 0)
	_user32.SendMessageW(hwnd, _EM_SETSEL, end, end)
	_user32.SendMessageW(hwnd, _EM_SCROLLCARET, 0, 0)


def gui_ctrl_edit_queue_push(hwnd, text):
	hwnd = _edit(hwnd)
	end = _user32.SendMessageW(hwnd, _WM_GETTEXTLENGTH, 0, 0)
	_replace(hwnd, end, end, str(text) + "\r\n")
	_user32.SendMessageW(hwnd, _EM_SETSEL, 0, 0)
	_user32.SendMessageW(hwnd, _EM_SCROLLCARET, 0, 0)


def gui_ctrl_edit_remove_line(hwnd, line_index):
	hwnd = _edit(hwnd)
	length = _user32.SendMessageW(hwnd, _WM_GETTEXTLENGTH, 0, 0)
	if not length:
		return
	buffer = ctypes.create_unicode_buffer(length + 1)
	_user32.GetWindowTextW(hwnd, buffer, len(buffer))
	lines = buffer.value.split("\r\n")
	count = len(lines)
	if line_index < 0:
		line_index += count
	line_index = max(0, min(line_index, count - 1))
	if line_index == count - 1 and not lines[line_index] and line_index > 0:
		line_index -= 1
	start_text = "\r\n".join(lines[:line_index])
	if line_index:
		start_text += "\r\n"
	start = len(start_text.encode("utf-16-le", "surrogatepass")) // 2
	line_length = len(lines[line_index].encode("utf-16-le", "surrogatepass")) // 2
	end = min(start + line_length + 2, length)
	_replace(hwnd, start, end, "")


def gui_ctrl_edit_queue_pop(hwnd):
	gui_ctrl_edit_remove_line(hwnd, 0)


def gui_ctrl_edit_stack_push(hwnd, text):
	gui_ctrl_edit_append(hwnd, str(text) + "\r\n")


def gui_ctrl_edit_stack_pop(hwnd):
	gui_ctrl_edit_remove_line(hwnd, -1)


def gui_ctrl_edit_clear(hwnd):
	hwnd = _edit(hwnd)
	_replace(hwnd, 0, -1, "")


__GUICtrlEdit_Append = gui_ctrl_edit_append
__GUICtrlEdit_QueuePush = gui_ctrl_edit_queue_push
__GUICtrlEdit_QueuePop = gui_ctrl_edit_queue_pop
__GUICtrlEdit_StackPush = gui_ctrl_edit_stack_push
__GUICtrlEdit_StackPop = gui_ctrl_edit_stack_pop
__GUICtrlEdit_RemoveLine = gui_ctrl_edit_remove_line
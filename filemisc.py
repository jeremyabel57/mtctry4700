import ctypes
import ntpath
import os
import re
from ctypes import wintypes


g_configFile = ""
g_configSection = ""


def _config(section, filename):
	section = g_configSection if section is None else section
	filename = g_configFile if filename is None else filename
	if not section or not filename:
		raise ValueError("An INI section and file path are required")
	return str(section), os.path.abspath(os.fspath(filename))


def _profile_api():
	if os.name != "nt":
		raise OSError("Windows INI profile APIs are required")
	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	kernel32.GetPrivateProfileStringW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR,
		wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD, wintypes.LPCWSTR]
	kernel32.GetPrivateProfileStringW.restype = wintypes.DWORD
	kernel32.WritePrivateProfileStringW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR,
		wintypes.LPCWSTR, wintypes.LPCWSTR]
	kernel32.WritePrivateProfileStringW.restype = wintypes.BOOL
	return kernel32


def _ini_read(key, default, section, filename):
	api = _profile_api()
	capacity = 256
	while True:
		buffer = ctypes.create_unicode_buffer(capacity)
		length = api.GetPrivateProfileStringW(section, str(key), str(default), buffer, capacity, filename)
		if length < capacity - 1:
			return buffer.value
		capacity *= 2


def _ini_write(key, value, section, filename):
	api = _profile_api()
	if not os.path.exists(filename):
		try:
			with open(filename, "xb") as stream:
				stream.write(b"\xff\xfe")
		except FileExistsError:
			pass
	if not api.WritePrivateProfileStringW(section, str(key), None if value is None else str(value), filename):
		raise ctypes.WinError(ctypes.get_last_error())


def _control_api(hwnd):
	if os.name != "nt":
		raise OSError("Windows GUI controls are required")
	user32 = ctypes.WinDLL("user32", use_last_error=True)
	user32.IsWindow.argtypes = [wintypes.HWND]
	user32.IsWindow.restype = wintypes.BOOL
	user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
	user32.GetWindowTextLengthW.restype = ctypes.c_int
	user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
	user32.GetWindowTextW.restype = ctypes.c_int
	user32.SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
	user32.SetWindowTextW.restype = wintypes.BOOL
	user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
	user32.SendMessageW.restype = ctypes.c_ssize_t
	if not user32.IsWindow(hwnd):
		raise ValueError("Invalid control window handle")
	return user32


def _control_text(hwnd):
	user32 = _control_api(hwnd)
	length = user32.GetWindowTextLengthW(hwnd)
	buffer = ctypes.create_unicode_buffer(length + 1)
	user32.GetWindowTextW(hwnd, buffer, len(buffer))
	return buffer.value


def _set_control_text(hwnd, value):
	if not _control_api(hwnd).SetWindowTextW(hwnd, str(value)):
		raise ctypes.WinError(ctypes.get_last_error())


def ini_read_gui(hwnd, key, section=None, filename=None):
	section, filename = _config(section, filename)
	_set_control_text(hwnd, _ini_read(key, _control_text(hwnd), section, filename))


def ini_write_gui(hwnd, key, section=None, filename=None):
	section, filename = _config(section, filename)
	_ini_write(key, _control_text(hwnd), section, filename)


def gui_checkbox(hwnd, state=None):
	user32 = _control_api(hwnd)
	if state is None:
		return user32.SendMessageW(hwnd, 0x00F0, 0, 0) == 1
	user32.SendMessageW(hwnd, 0x00F1, int(bool(state)), 0)


def ini_read_gui_checkbox(hwnd, key, section=None, filename=None):
	section, filename = _config(section, filename)
	value = _ini_read(key, int(gui_checkbox(hwnd)), section, filename)
	try:
		state = int(value)
	except ValueError:
		state = 0
	gui_checkbox(hwnd, state)


def ini_write_gui_checkbox(hwnd, key, section=None, filename=None):
	section, filename = _config(section, filename)
	_ini_write(key, int(gui_checkbox(hwnd)), section, filename)


def _combo_items(hwnd):
	user32 = _control_api(hwnd)
	count = user32.SendMessageW(hwnd, 0x0146, 0, 0)
	if count < 0:
		raise ValueError("Control is not a combo box")
	items = []
	for index in range(count):
		length = user32.SendMessageW(hwnd, 0x0149, index, 0)
		if length < 0:
			raise OSError("Could not read combo box item")
		buffer = ctypes.create_unicode_buffer(length + 1)
		if user32.SendMessageW(hwnd, 0x0148, index, ctypes.addressof(buffer)) < 0:
			raise OSError("Could not read combo box item")
		items.append(buffer.value)
	return items


def ini_read_gui_combo_box(hwnd, key, section=None, filename=None):
	section, filename = _config(section, filename)
	items = _ini_read(f"{key}List", "|".join(_combo_items(hwnd)), section, filename)
	selected = _ini_read(key, _control_text(hwnd), section, filename)
	user32 = _control_api(hwnd)
	user32.SendMessageW(hwnd, 0x014B, 0, 0)
	for item in items.split("|") if items else ():
		buffer = ctypes.create_unicode_buffer(item)
		if user32.SendMessageW(hwnd, 0x0143, 0, ctypes.addressof(buffer)) < 0:
			raise OSError("Could not add combo box item")
	buffer = ctypes.create_unicode_buffer(selected)
	index = user32.SendMessageW(hwnd, 0x0158, -1, ctypes.addressof(buffer))
	if index >= 0:
		user32.SendMessageW(hwnd, 0x014E, index, 0)
	else:
		_set_control_text(hwnd, selected)


def ini_write_gui_combo_box(hwnd, key, section=None, filename=None):
	section, filename = _config(section, filename)
	_ini_write(f"{key}List", "|".join(_combo_items(hwnd)), section, filename)
	_ini_write(key, _control_text(hwnd), section, filename)


def file_name_auto_increment(path):
	path = os.path.abspath(os.fspath(path))
	if not os.path.exists(path):
		return path
	base, extension = os.path.splitext(path)
	match = re.fullmatch(r"(.*)_(\d+)", base)
	if match:
		base, number = match.groups()
		width = len(number)
		index = int(number)
	else:
		width = 3
		index = 1
	while True:
		candidate = f"{base}_{index:0{width}d}{extension}"
		if not os.path.exists(candidate):
			return candidate
		index += 1


def is_full_path_specified(path):
	path = os.fspath(path)
	if path in ("", "..."):
		return False
	drive, remainder = ntpath.splitdrive(path)
	directory = ntpath.dirname(remainder)
	return bool(drive and directory and directory not in ("\\", "/") and remainder.startswith(("\\", "/")))


def ini_read_array(default, key, section=None, filename=None):
	section, filename = _config(section, filename)
	def dimension(suffix):
		try:
			return int(_ini_read(f"{key}{suffix}", "0", section, filename))
		except ValueError:
			return 0
	rows, columns = dimension("r"), dimension("c")
	if rows <= 0 or columns <= 0:
		count = rows if rows > 0 else columns
		if count <= 0:
			count = dimension("n")
		if count <= 0:
			return default
		return [_ini_read(f"{key}{index}", "", section, filename) for index in range(count)]
	return [[_ini_read(f"{key}{row}.{column}", "", section, filename)
		for column in range(columns)] for row in range(rows)]


def ini_write_array(values, key, section=None, filename=None):
	if not isinstance(values, (list, tuple)) or not values:
		return False
	matrix = isinstance(values[0], (list, tuple))
	if matrix:
		columns = len(values[0])
		if not columns or any(not isinstance(row, (list, tuple)) or len(row) != columns for row in values):
			return False
	elif any(isinstance(value, (list, tuple)) for value in values):
		return False
	section, filename = _config(section, filename)
	if matrix:
		_ini_write(f"{key}n", None, section, filename)
		_ini_write(f"{key}r", len(values), section, filename)
		_ini_write(f"{key}c", columns, section, filename)
		for row, items in enumerate(values):
			for column, value in enumerate(items):
				_ini_write(f"{key}{row}.{column}", value, section, filename)
	else:
		_ini_write(f"{key}r", None, section, filename)
		_ini_write(f"{key}c", None, section, filename)
		_ini_write(f"{key}n", len(values), section, filename)
		for index, value in enumerate(values):
			_ini_write(f"{key}{index}", value, section, filename)
	return True


def cloud_excel_write(sheet, row, column, value, workbook_path):
	if not isinstance(row, int) or isinstance(row, bool) or row < 1:
		raise ValueError("Excel row must be a positive integer")
	if not isinstance(column, int) or isinstance(column, bool) or column < 1:
		raise ValueError("Excel column must be a positive integer")
	path = os.fspath(workbook_path)
	if not path:
		raise ValueError("An Excel workbook path or URL is required")
	import pythoncom
	import win32com.client
	pythoncom.CoInitialize()
	try:
		excel = win32com.client.DispatchEx("Excel.Application")
		try:
			excel.Visible = False
			excel.DisplayAlerts = False
			workbook = excel.Workbooks.Open(path)
			try:
				workbook.Worksheets(sheet).Cells(row, column).Value = value
				workbook.Save()
			finally:
				workbook.Close(SaveChanges=False)
		finally:
			excel.Quit()
	finally:
		pythoncom.CoUninitialize()
	return True


__FileNameAutoIncrement = file_name_auto_increment
__IsFullPathSpecified = is_full_path_specified
__IniReadArray = ini_read_array
__IniWriteArray = ini_write_array
__IniReadGui = ini_read_gui
__IniWriteGui = ini_write_gui
__GuiCheckbox = gui_checkbox
__IniReadGuiCheckbox = ini_read_gui_checkbox
__IniWriteGuiCheckbox = ini_write_gui_checkbox
__IniReadGuiComboBox = ini_read_gui_combo_box
__IniWriteGuiComboBox = ini_write_gui_combo_box
_CloudExcelWrite = cloud_excel_write
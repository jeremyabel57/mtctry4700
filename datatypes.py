import ctypes
import math
import os
import re
import socket
from ctypes import wintypes


g_vars = {}


def __IsDictionary(value):
	return isinstance(value, dict)


def __IsScriptingDictionary(value):
	return __IsDictionary(value)


def __IsDllHandleValid(handle):
	if os.name != "nt" or isinstance(handle, bool):
		return False
	handle = getattr(handle, "_handle", handle)
	if isinstance(handle, ctypes.c_void_p):
		handle = handle.value
	if not isinstance(handle, int) or handle <= 0:
		return False
	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	kernel32.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
	kernel32.GetModuleFileNameW.restype = wintypes.DWORD
	return bool(kernel32.GetModuleFileNameW(handle, ctypes.create_unicode_buffer(2), 2))


def __IsFileHandle(handle):
	if isinstance(handle, bool):
		return False
	if hasattr(handle, "tell"):
		try:
			handle.tell()
			return True
		except (OSError, ValueError):
			return False
	if not isinstance(handle, int) or handle < 0:
		return False
	try:
		os.lseek(handle, 0, os.SEEK_CUR)
		return True
	except OSError:
		if os.name != "nt" or handle == 0:
			return False
		kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
		kernel32.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong,
			ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]
		kernel32.SetFilePointerEx.restype = wintypes.BOOL
		position = ctypes.c_longlong()
		return bool(kernel32.SetFilePointerEx(handle, 0, ctypes.byref(position), 1))


def __SocketToIP(handle):
	borrowed = None
	try:
		if isinstance(handle, socket.socket):
			connection = handle
		elif isinstance(handle, int) and not isinstance(handle, bool) and handle > 0:
			borrowed = socket.socket(fileno=handle)
			connection = borrowed
		else:
			return 0
		if connection.family != socket.AF_INET:
			return 0
		return connection.getpeername()[0]
	except (OSError, ValueError, OverflowError):
		return 0
	finally:
		if borrowed is not None:
			borrowed.detach()


def __IsTCPsocket(handle):
	return __SocketToIP(handle) != 0


def __TemperatureFtoC(value):
	return (value - 32) * 5 / 9


def __TemperatureCtoF(value):
	return value * 9 / 5 + 32


def _variable_parts(name):
	name = str(name).lstrip("$")
	match = re.fullmatch(r"([A-Za-z_]\w*)((?:\[[^\[\]]*\]){0,2}|\([^()]*\))", name)
	if not match:
		raise ValueError(f"Invalid variable reference: {name}")
	base, suffix = match.groups()
	if not suffix:
		return base, []
	indices = re.findall(r"\[([^\[\]]*)\]", suffix) if suffix.startswith("[") else [suffix[1:-1]]
	return base, [index.strip().strip("\"'") for index in indices]


def _variable_key(variables, name):
	return next((key for key in variables if isinstance(key, str) and key.lower() == name.lower()), name)


def _index(container, key):
	if isinstance(container, (list, tuple)):
		index = int(key)
		if not 0 <= index < len(container):
			raise IndexError("Variable subscript out of range")
		return index
	if isinstance(container, dict):
		return key
	raise TypeError("Variable is not an array or dictionary")


def AssignEx(name, value, variables=None):
	if variables is None:
		variables = g_vars
	if not isinstance(variables, dict):
		raise TypeError("variables must be a dictionary")
	base, indices = _variable_parts(name)
	key = _variable_key(variables, base)
	if not indices:
		variables[key] = value
		return 1
	try:
		container = variables[key]
		for index in indices[:-1]:
			container = container[_index(container, index)]
		container[_index(container, indices[-1])] = value
	except (KeyError, IndexError, ValueError, TypeError):
		return 0
	return 1


def EvalEx(name, variables=None):
	if variables is None:
		variables = g_vars
	if not isinstance(variables, dict):
		raise TypeError("variables must be a dictionary")
	base, indices = _variable_parts(name)
	value = variables[_variable_key(variables, base)]
	for index in indices:
		value = value[_index(value, index)]
	return value


def AssignDict(name, value, dictionary=None):
	if dictionary is None:
		dictionary = g_vars
	if not isinstance(dictionary, dict):
		raise TypeError("dictionary must be a dictionary")
	dictionary[str(name).removeprefix("$")] = value
	return value


def EvalDict(name, dictionary=None):
	if dictionary is None:
		dictionary = g_vars
	if not isinstance(dictionary, dict):
		raise TypeError("dictionary must be a dictionary")
	return dictionary[str(name).removeprefix("$")]


def _Bits(value, bits=8):
	if bits < 0:
		raise ValueError("Bit count must not be negative")
	return "".join(str((int(value) >> index) & 1) for index in range(bits - 1, -1, -1))


def __StringSplitFirst(value, delimiter=","):
	if not delimiter:
		return [value, ""]
	index = value.lower().find(delimiter.lower())
	if index < 0:
		return [value, ""]
	return [value[:index], value[index + 1:]]


def __NumEgr(value, precision=2):
	value = float(value)
	if not math.isfinite(value):
		raise ValueError("Engineering notation requires a finite number")
	if precision < 0:
		raise ValueError("Precision must not be negative")
	prefixes = (("Q", 30), ("R", 27), ("Y", 24), ("Z", 21), ("E", 18),
		("P", 15), ("T", 12), ("G", 9), ("M", 6), ("k", 3), ("", 0),
		("m", -3), ("u", -6), ("n", -9), ("p", -12), ("f", -15),
		("a", -18), ("z", -21), ("y", -24), ("r", -27), ("q", -30))
	if value == 0:
		return f"{value:.{precision}f} "
	prefix, exponent = next(((prefix, exponent) for prefix, exponent in prefixes
		if abs(value) >= 10 ** exponent), prefixes[-1])
	return f"{value / 10 ** exponent:.{precision}f} {prefix}"


is_dictionary = __IsDictionary
is_scripting_dictionary = __IsScriptingDictionary
is_dll_handle_valid = __IsDllHandleValid
is_file_handle = __IsFileHandle
is_tcp_socket = __IsTCPsocket
socket_to_ip = __SocketToIP
temperature_f_to_c = __TemperatureFtoC
temperature_c_to_f = __TemperatureCtoF
bits = _Bits
string_split_first = __StringSplitFirst
number_engineering = __NumEgr
assign_ex = AssignEx
eval_ex = EvalEx
assign_dict = AssignDict
eval_dict = EvalDict
import re
import sys

from deque import Deque


def dbg_is_dictionary(value):
	return isinstance(value, dict)


def _type_name(value):
	if isinstance(value, bool):
		return "Bool"
	if isinstance(value, int):
		return "Int32" if -(2 ** 31) <= value < 2 ** 31 else "Int64"
	if isinstance(value, float):
		return "Double"
	if isinstance(value, str):
		return "String"
	if isinstance(value, (bytes, bytearray, memoryview)):
		return "Binary"
	if isinstance(value, (list, tuple)):
		return "Array"
	if isinstance(value, dict):
		return "Object"
	return type(value).__name__


def s_print_var(value, sep=", ", name="", eol=False):
	return _format_var(value, sep, name, eol, set())


def _format_var(value, sep, name, eol, active):
	label = f"{name} = " if name else ""
	type_name = _type_name(value)
	is_container = isinstance(value, (list, tuple, dict, Deque))
	if is_container and id(value) in active:
		return f"{label}({type_name}) <recursive>"
	if is_container:
		active.add(id(value))
	try:
		if isinstance(value, Deque):
			items = []
			for key in ("cmd", "cond", "bCond", "skip", "pc"):
				if hasattr(value, key):
					items.append(f"{key}=" + _format_var(getattr(value, key), ", ", "", False, active))
			if value:
				items.append("List: " + sep.join(_format_var(item, ", ", "", False, active) for item in value))
			result = f"({type_name}[{len(value)}]) ( " + sep.join(items) + " )"
		elif isinstance(value, (list, tuple)):
			is_matrix = bool(value) and all(isinstance(row, (list, tuple)) for row in value)
			if is_matrix and all(len(row) == len(value[0]) for row in value):
				rows = ["[ " + sep.join(_format_var(item, ", ", "", False, active) for item in row) + " ]"
					for row in value]
				result = f"({type_name}[{len(value)}][{len(value[0])}]) [ " + "\r\n".join(rows) + " ]"
			else:
				items = sep.join(_format_var(item, ", ", "", False, active) for item in value)
				result = f"({type_name}[{len(value)}]) [" + (" " + items if items else "") + " ]"
		elif isinstance(value, dict):
			is_queue = "head" in value and "tail" in value
			items = []
			for key, item in value.items():
				if is_queue and (key in ("head", "tail") or str(key).lstrip("-").isdigit()):
					continue
				items.append(f"{key}=" + _format_var(item, ", ", "", False, active))
			if is_queue:
				queue_items = [value[str(index)] for index in range(int(value["head"]), int(value["tail"]) + 1)
					if str(index) in value]
				if queue_items:
					items.append("List: " + sep.join(_format_var(item, ", ", "", False, active) for item in queue_items))
			result = f"({type_name}[{len(value)}]) ( " + sep.join(items) + " )"
		elif isinstance(value, (bytes, bytearray, memoryview)):
			data = bytes(value)
			result = f"(Binary[{len(data)}]) '0x{data.hex().upper()}'"
		elif isinstance(value, (int, float, bool)):
			result = f"({type_name}) {value}"
		elif isinstance(value, str) and re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value):
			result = f"({type_name}) {value}"
		else:
			result = f"({type_name}) '{value}'"
	finally:
		if is_container:
			active.remove(id(value))
	return label + result + ("\r\n" if name and eol else "")


def s_print_vars(prefix, *name_values):
	separator = prefix[-2:]
	prefix = prefix[:-2]
	if prefix:
		prefix += " "
	if separator == "\r\n":
		separator += prefix
	if not separator:
		separator = ", "
	items = []
	for index in range(0, len(name_values), 2):
		name = name_values[index]
		if name == "":
			continue
		value = name_values[index + 1] if index + 1 < len(name_values) else ""
		items.append(s_print_var(value, name=str(name).removeprefix("$")))
	return prefix + separator.join(items) + "\r\n"


def console_print_var(value, sep=", ", name="", eol=True):
	sys.stdout.write(s_print_var(value, sep, name, eol))


def console_print_vars(prefix, *name_values):
	sys.stdout.write(s_print_vars(prefix, *name_values))


__dbgIsDictionary = dbg_is_dictionary
__sPrintVar = s_print_var
__sPrintVars = s_print_vars
__ConsolePrintVar = console_print_var
__ConsolePrintVars = console_print_vars
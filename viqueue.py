import ast
import operator
import os
import re
import socket
import struct
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

import mydebug
import filemisc
import datatypes
import winfuncs


class viqueue:
	F4T_REGISTERS = ((2782, 300), (27586, 100), (16594, 2000),
		(2804, 103), (2806, 107), (6730, 901))
	notices = {}
	def __init__(self, address):
		host, port, raw = self.parse_ip_address(address)
		if not host:
			raise ValueError("An instrument address is required")
		port = port or (5025 if raw else "inst0")
		index = host if str(port) in ("5025", "inst0") else f"{host}:{port}"
		self.request_queue = deque()
		self.response_queue = deque()
		self.execution_stack = []
		self.variables = {}
		self._devices = {}
		self._active_device = None
		self._forward_state = None
		self._forward_future = None
		self._forward_result = None
		self._directory = Path.cwd()
		self._logfile = self._directory / "log.txt"
		self._diagnostics = {"output": None, "queue": None, "stack": None}
		self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="viqueue")
		self._future = None
		self._resource_manager = None
		self._raw_buffer = b""
		self._skip_terminator = False
		self._closed = False
		self.instrument = {
			"index": index, "sAddr": f"{'raw:' if raw else ''}{host}:{port}",
			"ipAddr": host, "viIpPort": port, "viIpMode": int(raw),
			"viAddr": self.make_visa_address(host, str(port), raw), "viIdn": "", "viType": "",
			"viSession": None, "viSocket": None, "state": False,
			"mbIpPort": 502, "mbSocket": None, "mbTransID": 0x100,
			"f4tWordOrder": -1, "f4tDataMap": -1, "f4tUnits": -1,
			"cmd": "", "timer": 0, "timeout": 1000, "reqdone": False,
			"cStack": self.execution_stack, "rNotice": "", "wNotice": "",
			"upload": None, "cdone": True, "creturn": 1,
			"rMode": 0, "rExpLen": 0, "rParse": -1, "rBuf": b"", "rCount": 0,
			"download": None, "rdone": True, "waitReply": False, "rVar": "", "rExec": "",
			"qreq": self.request_queue, "qret": self.response_queue,
		}

	@staticmethod
	def parse_ip_address(address, default_port=""):
		raw = address[:4].lower() == "raw:"
		address = address[4:] if raw else address
		host, separator, port = address.partition(":")
		return host, port if separator else default_port, raw

	@staticmethod
	def make_visa_address(host, port="", raw=False):
		if raw:
			return f"TCPIP::{host}::{port or 5025}::SOCKET"
		return f"TCPIP0::{host}::{port or 'inst0'}::INSTR"

	def request(self, command, wait=True, timeout_ms=1000, force_no_wait=False):
		if self._closed:
			raise RuntimeError("Instrument queue is closed")
		self._check_diagnostics()
		if not command or command.startswith("//"):
			return False
		match = re.match(r"^([0-9]*)!", command)
		if match:
			timeout_ms = int(match.group(1) or 0)
			command = command[match.end():]
			if timeout_ms > 0:
				wait = True
		if command.endswith("?"):
			wait = True
		if force_no_wait:
			wait = False
			timeout_ms = 0
		item = (command, wait, timeout_ms)
		self.request_queue.append(item)
		self._diagnostic_queue_push(item)
		return True

	def set_diagnostics(self, output=None, queue=None, stack=None):
		if self._closed:
			raise RuntimeError("Instrument queue is closed")
		for hwnd in (output, queue, stack):
			if hwnd is not None:
				winfuncs._edit(hwnd)
		handles = [hwnd for hwnd in (output, queue, stack) if hwnd is not None]
		if len(handles) != len(set(handles)):
			raise ValueError("Diagnostic controls must be distinct")
		for hwnd in handles:
			winfuncs.prepare_diagnostic_edit(hwnd)
		self._diagnostics = {"output": output, "queue": queue, "stack": stack}
		if queue is not None:
			winfuncs.gui_ctrl_edit_clear(queue)
			for item in self.request_queue:
				self._diagnostic_queue_push(item)
		if stack is not None:
			winfuncs.gui_ctrl_edit_clear(stack)
			for frame in self.execution_stack:
				self._diagnostic_stack_push(frame)

	def _diagnostic_queue_push(self, item):
		hwnd = self._diagnostics["queue"]
		if hwnd is not None:
			text = mydebug.s_print_var(item).replace("\r", "\\r").replace("\n", "\\n")
			winfuncs.gui_ctrl_edit_queue_push(hwnd, text)

	def _check_diagnostics(self):
		for hwnd in self._diagnostics.values():
			if hwnd is not None:
				winfuncs._edit(hwnd)

	def _diagnostic_output(self, text):
		hwnd = self._diagnostics["output"]
		if hwnd is not None:
			winfuncs.gui_ctrl_edit_append(hwnd, text + "\r\n")

	def _diagnostic_stack_push(self, frame):
		hwnd = self._diagnostics["stack"]
		if hwnd is not None and frame["kind"] != "script":
			text = frame["kind"]
			if frame.get("condition"):
				text += " " + frame["condition"]
			winfuncs.gui_ctrl_edit_stack_push(hwnd, text)

	def _push_script_frame(self, frame):
		self.execution_stack.append(frame)
		self._diagnostic_stack_push(frame)

	def command(self, command, force_no_wait=False):
		return self.request(command, False, 0 if force_no_wait else 1000, force_no_wait)

	def is_request_done(self):
		done = self.instrument["reqdone"]
		self.instrument["reqdone"] = False
		return done

	def command_status(self):
		return self.instrument["creturn"]

	def is_idle(self):
		return not self.request_queue and not self.execution_stack and self._future is None and self._forward_state is None

	def register_device(self, name, device):
		if not isinstance(device, viqueue) or device is self or device.instrument["index"].lower() == "main":
			raise ValueError("A different instrument queue is required")
		name = str(name).strip().lower()
		if not name:
			raise ValueError("A device name is required")
		self._devices[name] = device

	def has_response(self):
		return bool(self.response_queue)

	def has_notice(self, name):
		return str(name) in self.notices

	def take_notice(self, name):
		return self.notices.pop(str(name))

	def response(self, binary=False):
		value, status = self.response_queue.popleft()
		if isinstance(value, bytes) and not binary:
			value = value.decode(errors="replace").strip()
		return value, status

	def modbus_read(self, data_type, address, timeout_ms=1500, prefix=""):
		return self.request(f"{prefix}modbusread {data_type} {address}", True, timeout_ms)

	def modbus_write(self, data_type, address, value, timeout_ms=1500):
		return self.request(f"modbuswrite {data_type} {address} {value}", False, timeout_ms)

	def modbus_read_blocking(self, data_type, address, timeout_ms=1500):
		result = self.request_blocking(f"modbusread {data_type} {address}", True, timeout_ms)
		if result is None:
			raise RuntimeError("Modbus read returned no response")
		return result[0]

	def command_blocking(self, command, timeout_ms=2000):
		return self.request_blocking(command, False, timeout_ms)

	def get_id(self, timeout_ms=1000):
		self.flush()
		last_error = None
		for attempt in range(2):
			try:
				result = self.request_blocking("*IDN?", True, timeout_ms)
				if result is not None and result[0]:
					identity = str(result[0]).strip()
					self.instrument["viIdn"] = identity
					self.instrument["viType"] = self.classify(identity)
					return identity
			except (RuntimeError, TimeoutError, OSError) as error:
				last_error = error
			if attempt == 0:
				self.toggle_mode()
		try:
			identity = self.f4t_get_id(timeout_ms)
			self.instrument["viIdn"] = identity
			self.instrument["viType"] = self.classify(identity)
			return identity
		except (RuntimeError, TimeoutError, OSError, ValueError) as error:
			raise RuntimeError("Could not identify the instrument") from (last_error or error)

	@staticmethod
	def classify(identity):
		identity = identity.upper()
		for patterns, label in (((",MSO", ",DPO"), "sc Oscilloscope"),
				((",F4T",), "tc Chamber"), ((",5323", ",5313"), "fc Frequency Counter"),
				((",N670", ",E363"), "dc DC Power Supply")):
			if any(pattern in identity for pattern in patterns):
				return label
		return ""

	def toggle_mode(self):
		if self._closed:
			raise RuntimeError("Instrument queue is closed")
		if not self.is_idle():
			raise RuntimeError("Cannot switch modes while commands are pending")
		self._close_connections()
		raw = not self.instrument["viIpMode"]
		port = self.instrument["viIpPort"]
		if raw and not str(port).isdigit():
			port = 5025
		elif not raw and str(port) == "5025":
			port = "inst0"
		host = self.instrument["ipAddr"]
		self.instrument.update(viIpMode=int(raw), viIpPort=port,
			viAddr=self.make_visa_address(host, str(port), raw),
			sAddr=f"{'raw:' if raw else ''}{host}:{port}")

	def get_error(self, timeout_ms=1000):
		result = self.request_blocking(":SYSTem:ERRor?", True, timeout_ms)
		if result is None:
			raise RuntimeError("Error query returned no response")
		return int(float(str(result[0]).split(",", 1)[0].strip()))

	def flush_errors(self, timeout_ms=1000, limit=10):
		for _ in range(limit):
			if self.get_error(timeout_ms) == 0:
				return True
		return False

	def go_to_local(self):
		return self.command("&GTL")

	def f4t_get_data_map(self):
		try:
			value = int(self.modbus_read_blocking("1i", 100))
		except (RuntimeError, TimeoutError):
			value = 0
		self.instrument["f4tDataMap"] = 1 if value == 0 or int(value / 256) == 0x83 else 2
		return self.instrument["f4tDataMap"]

	def f4t_get_word_order(self):
		word_order = 1
		if self.instrument["f4tDataMap"] == 1:
			try:
				value = int(self.modbus_read_blocking("1i", 14092))
			except (RuntimeError, TimeoutError):
				value = 0
			if value | 1 != 1331:
				value = int(self.modbus_read_blocking("1i", 6736))
			if value | 1 == 1331:
				word_order = int(not (value & 1))
		self.instrument["f4tWordOrder"] = word_order
		return word_order

	def f4t_get_units(self):
		if self.instrument["f4tDataMap"] == 1:
			units = int(self.modbus_read_blocking("1i", 6730) == 15)
		else:
			units = int(self.modbus_read_blocking("1i", 901)) & 1
		self.instrument["f4tUnits"] = units
		return units

	def f4t_resolve(self):
		if self.instrument["f4tDataMap"] not in (1, 2):
			self.f4t_get_data_map()
		if self.instrument["f4tWordOrder"] not in (0, 1):
			self.f4t_get_word_order()
		if self.instrument["f4tUnits"] not in (0, 1):
			self.f4t_get_units()

	def f4t_read(self, index):
		if not 0 <= index < len(self.F4T_REGISTERS):
			raise ValueError("Invalid F4T register index")
		self.f4t_resolve()
		data_map = self.instrument["f4tDataMap"]
		address = self.F4T_REGISTERS[index][data_map - 1]
		if data_map == 1 and index != 2:
			return float(self.modbus_read_blocking("2f", address))
		value = int(self.modbus_read_blocking("1i", address))
		return bool(int(value) & 1) if index == 2 else value / 10

	def f4t_read_bg(self, index, variable=""):
		if not 0 <= index < len(self.F4T_REGISTERS):
			raise ValueError("Invalid F4T register index")
		self.f4t_resolve()
		data_map = self.instrument["f4tDataMap"]
		address = self.F4T_REGISTERS[index][data_map - 1]
		data_type = "2f" if data_map == 1 and index != 2 else "1i"
		prefix = f"${variable.removeprefix('$')}=" if variable else ""
		return self.modbus_read(data_type, address, 1000, prefix)

	def f4t_read_bg_process_reply(self, index, value):
		if not 0 <= index < len(self.F4T_REGISTERS):
			raise ValueError("Invalid F4T register index")
		if self.instrument["f4tDataMap"] == 1 and index != 2:
			return value
		return bool(int(value) & 1) if index == 2 else int(value) / 10

	def f4t_get_id(self, timeout_ms=1000):
		self.f4t_resolve()
		if self.instrument["f4tDataMap"] == 1:
			serial = self.modbus_read_blocking("2i", 12, timeout_ms)
			version = self.modbus_read_blocking("2i", 3, timeout_ms)
			manufacturer = self.modbus_read_blocking("30s", 46, timeout_ms)
			model = self.modbus_read_blocking("15s", 16, timeout_ms)
			if not serial or not version or not manufacturer:
				raise ValueError("Incomplete F4T identification")
			return f"{str(manufacturer).strip()},{str(model).strip()},{serial},{version}"
		manufacturer = self.modbus_read_blocking("1i", 3, timeout_ms)
		model = self.modbus_read_blocking("1i", 0, timeout_ms)
		major = int(self.modbus_read_blocking("1i", 4, timeout_ms))
		minor = int(self.modbus_read_blocking("1i", 30, timeout_ms))
		if not manufacturer or not model:
			raise ValueError("Incomplete F4T identification")
		return f"{manufacturer},{model},,{major:02d}.{minor:05d}"

	def f4t_write(self, index, value):
		if not 0 <= index < len(self.F4T_REGISTERS):
			raise ValueError("Invalid F4T register index")
		self.f4t_resolve()
		data_map = self.instrument["f4tDataMap"]
		address = self.F4T_REGISTERS[index][data_map - 1]
		if data_map == 1 and index != 2:
			return self.modbus_write("2f", address, value)
		register_value = int(value) | 62 if data_map == 1 else int(value)
		if index != 2:
			register_value = int(10 * value)
		return self.modbus_write("1i", address, register_value)

	def f4t_temperature(self):
		value = self.f4t_read(1)
		return (value - 32) * 5 / 9 if self.instrument["f4tUnits"] == 0 else value

	def f4t_setpoint(self, value=None):
		if value is not None:
			self.f4t_resolve()
			return self.f4t_write(0, value * 9 / 5 + 32 if self.instrument["f4tUnits"] == 0 else value)
		value = self.f4t_read(0)
		return (value - 32) * 5 / 9 if self.instrument["f4tUnits"] == 0 else value

	def f4t_enable(self, value=None):
		return self.f4t_read(2) if value is None else self.f4t_write(2, value)

	def f4t_heat(self):
		return self.f4t_read(3)

	def f4t_cool(self):
		return self.f4t_read(4)

	def upload_file(self, path, command, timeout_ms=5000):
		return self.request(f"upload::{path}::{command}", False, timeout_ms)

	def download_file(self, path, command, timeout_ms=5000):
		return self.request(f"download::{path}::{command}", True, timeout_ms)

	def download_picture(self, path, command, timeout_ms=5000):
		self.download_file(path, command, timeout_ms)
		self.command(f"parsepic {path}")

	def save_screenshot(self, path, commands):
		reserved_paths = set()
		for command, timeout_ms in commands:
			if command.startswith("!"):
				path = self._available_path(self._resolve_path(path), reserved_paths)
				self.download_picture(path, command[1:], timeout_ms)
			else:
				self.request(command, timeout_ms > 0, timeout_ms)
		return str(path)

	@staticmethod
	def _available_path(path, reserved_paths):
		path = filemisc.file_name_auto_increment(path)
		base, extension = os.path.splitext(path)
		match = re.fullmatch(r"(.*)_(\d+)", base)
		if match:
			base, number = match.groups()
			index = int(number) + 1
			width = len(number)
		else:
			index = 1
			width = 3
		while os.path.normcase(path) in reserved_paths or os.path.exists(path):
			path = f"{base}_{index:0{width}d}{extension}"
			index += 1
		reserved_paths.add(os.path.normcase(path))
		return path

	@staticmethod
	def parse_picture(value):
		path = None if isinstance(value, (bytes, bytearray, memoryview)) else Path(value)
		data = bytes(value) if path is None else path.read_bytes()
		for signature, extension in ((b"GIF87a", ".gif"), (b"GIF89a", ".gif"),
				(b"\x89PNG\r\n\x1a\n", ".png"), (b"BM", ".bmp"), (b"\xff\xd8\xff", ".jpg")):
			position = data.find(signature)
			if position >= 0:
				data = data[position:]
				break
		else:
			raise ValueError("No supported picture signature found")
		if path is None:
			return data, extension
		target = path.with_suffix(extension)
		if target == path:
			if position:
				path.write_bytes(data)
		else:
			with target.open("xb") as stream:
				stream.write(data)
			path.unlink()
		return str(target)

	def loop(self):
		if self._closed:
			return False
		self._check_diagnostics()
		if self._forward_state is not None:
			self._service_forward()
			return True
		if self._future is not None:
			if not self._future.done():
				return True
			forwarded = self._future is self._forward_future
			try:
				result = self._future.result()
			except Exception as error:
				self.instrument["creturn"] = 0
				if forwarded:
					self._forward_result = (None, str(error))
				else:
					self._publish_completion(None, str(error))
				self._diagnostic_output("< " + mydebug.s_print_var(str(error)))
				self._close_connections()
			else:
				self.instrument["creturn"] = 1
				if forwarded:
					self._forward_result = (result, None)
				else:
					self._publish_completion(result, None)
				if result is not None:
					self._diagnostic_output("< " + mydebug.s_print_var(result))
					if self.instrument["cmd"].strip().upper() == "*IDN?":
						self.instrument["viIdn"] = (result.decode(errors="replace") if isinstance(result, bytes) else str(result)).strip()
			self.instrument.update(rVar="", rNotice="")
			self._future = None
			self.instrument.update(cdone=True, rdone=True, waitReply=False, reqdone=True)
		if self.execution_stack:
			item = self._next_script_item()
		elif self.request_queue:
			item = self.request_queue.popleft()
			if self._diagnostics["queue"] is not None:
				winfuncs.gui_ctrl_edit_queue_pop(self._diagnostics["queue"])
		else:
			item = None
		if item is not None:
			command, wait, timeout_ms = item
			if isinstance(command, list):
				self._push_script_frame({"kind": "script", "body": command, "index": 0})
				return True
			assignment = re.match(r"^\$([A-Za-z_]\w*(?:\[[^\[\]]+\]){0,2})(:?)\s*=\s*(.*)$", command)
			self.instrument["rVar"] = assignment.group(1) if assignment else ""
			if assignment:
				command = assignment.group(3)
				wait = True
			notice = re.match(r"^ret(\S+)\s+(.+)$", command, re.IGNORECASE)
			self.instrument["rNotice"] = notice.group(1) if notice else ""
			if notice:
				command = notice.group(2)
			command_parts = command.split(maxsplit=1)
			if not command_parts or command_parts[0].lower() not in ("eval", "exec", "execute"):
				command = self._substitute(command)
			if command.strip().lower() == "flush":
				self.response_queue.clear()
				wait = True
			self._diagnostic_output("> " + command)
			self.instrument.update(cmd=command, timeout=timeout_ms, cdone=False,
				rdone=not wait, waitReply=wait, reqdone=False, timer=time.monotonic())
			if self._local_command(command):
				return True
			if self.instrument["index"].lower() == "main" and command.partition(" ")[0].lower() not in ("sleep", "parsepic", "flushinput"):
				if self._active_device is None:
					self._finish_forward(None, "No instrument selected")
				else:
					self._forward_state = {"device": self._active_device, "command": command,
						"wait": wait, "timeout": timeout_ms, "started": False}
				return True
			self._future = self._executor.submit(self._execute, command, wait, timeout_ms)
		return True

	def _publish_completion(self, result, error, *, has_result=False):
		notice = self.instrument["rNotice"]
		variable = self.instrument["rVar"]
		if error is not None:
			if not notice:
				self.response_queue.append((str(error), -1))
		elif (result is not None or has_result) and variable:
			if isinstance(result, bytes) and not variable.endswith("Data"):
				result = result.decode(errors="replace").strip()
			if not datatypes.AssignEx(variable, result, self.variables):
				self.instrument["creturn"] = 0
				error = "Invalid variable assignment"
				if not notice:
					self.response_queue.append((error, -1))
		elif (result is not None or has_result) and not notice:
			self.response_queue.append((result, 0))
		if notice:
			self.notices[notice] = (result if error is None else str(error), 0 if error is None else -1)

	def _service_forward(self):
		state = self._forward_state
		assert state is not None
		target = state["device"]
		if target._closed:
			self._finish_forward(None, "Selected instrument is closed")
			return
		if not state["started"]:
			if not target.is_idle():
				target.loop()
				return
			target.request(state["command"], state["wait"], state["timeout"])
			target.loop()
			if target._future is None:
				self._finish_forward(None, "Selected instrument did not start the request")
				return
			target._forward_future = target._future
			target._forward_result = None
			state["started"] = True
			return
		target.loop()
		if target._forward_result is not None:
			result, error = target._forward_result
			target._forward_future = None
			target._forward_result = None
			self._finish_forward(result, error)

	def _finish_forward(self, result, error):
		self.instrument["creturn"] = 0 if error is not None else 1
		self._publish_completion(result, error)
		if error is not None:
			self._diagnostic_output("< " + mydebug.s_print_var(error))
		elif result is not None:
			self._diagnostic_output("< " + mydebug.s_print_var(result))
		self._forward_state = None
		self.instrument.update(cdone=True, rdone=True, waitReply=False, reqdone=True, rVar="", rNotice="")

	def script(self, commands, timeout_ms=1000, file="", time_spacer=0):
		if self._closed:
			raise RuntimeError("Instrument queue is closed")
		self._check_diagnostics()
		if isinstance(commands, bytes):
			commands = commands.decode()
		lines = commands.splitlines() if isinstance(commands, str) else list(commands.values() if isinstance(commands, dict) else commands)
		root = []
		blocks: list[tuple[str, list, dict | None]] = [("script", root, None)]
		reserved_paths = set()
		for line in lines:
			entry_timeout = None
			if isinstance(line, (list, tuple)):
				line, entry_timeout = line[0], int(line[1]) if len(line) > 1 else None
			line = line.strip()
			if not line or line.startswith("//"):
				continue
			line_timeout = entry_timeout if entry_timeout is not None else timeout_ms
			timeout_match = re.match(r"^([0-9]*)!", line)
			if timeout_match:
				line_timeout = int(timeout_match.group(1) or 0)
				line = line[timeout_match.end():].strip()
			if line.startswith(("$$", "$oDev")):
				raise NotImplementedError("This AutoIt script syntax is not supported")
			if line.startswith("#"):
				picture = line.startswith("##")
				line = line[2 if picture else 1:].strip()
				if file:
					path = self._available_path(self._resolve_path(file), reserved_paths)
					transfer_timeout = line_timeout if (timeout_match or entry_timeout is not None) and line_timeout > 0 else timeout_ms * 10
					blocks[-1][1].append((f"download::{path}::{line}", True, transfer_timeout))
					if picture:
						blocks[-1][1].append((f"parsepic {path}", False, timeout_ms))
					if time_spacer > 0:
						blocks[-1][1].append((f"sleep {time_spacer}", False, timeout_ms))
					continue
			word, _, argument = line.partition(" ")
			word = word.lower()
			body = blocks[-1][1]
			if word in ("if", "while", "do"):
				node = {"kind": word, "condition": re.sub(r"\s+then$", "", argument, flags=re.I),
					"body": [], "else": []}
				body.append(node)
				blocks.append((word, node["body"], node))
			elif word == "else":
				if blocks[-1][0] != "if":
					raise ValueError("else without if")
				_, _, node = blocks.pop()
				assert node is not None
				blocks.append(("else", node["else"], node))
			elif word in ("end", "endif", "wend"):
				if blocks[-1][0] not in ("if", "else", "while"):
					raise ValueError("end without if or while")
				blocks.pop()
			elif word == "until":
				if blocks[-1][0] != "do":
					raise ValueError("until without do")
				_, _, node = blocks.pop()
				assert node is not None
				node["condition"] = argument
			else:
				wait = ((timeout_match is not None or entry_timeout is not None) and line_timeout > 0
					or line.endswith("?") or line.startswith("$"))
				body.append((line, bool(wait), line_timeout if line_timeout > 0 else timeout_ms))
			if time_spacer > 0:
				blocks[-1][1].append((f"sleep {time_spacer}", False, timeout_ms))
		if len(blocks) != 1:
			raise ValueError("Unclosed script block")
		item = (root, False, timeout_ms)
		self.request_queue.append(item)
		self._diagnostic_queue_push(item)

	def script_file(self, path, timeout_ms=1000):
		self.script(Path(path).read_text(), timeout_ms)

	def _next_script_item(self):
		frame = self.execution_stack[-1]
		if frame["index"] >= len(frame["body"]):
			if frame["kind"] == "while" and self._evaluate(frame["condition"]):
				frame["index"] = 0
			elif frame["kind"] == "do" and not self._evaluate(frame["condition"]):
				frame["index"] = 0
			else:
				self.execution_stack.pop()
				if frame["kind"] != "script" and self._diagnostics["stack"] is not None:
					winfuncs.gui_ctrl_edit_stack_pop(self._diagnostics["stack"])
			return None
		item = frame["body"][frame["index"]]
		frame["index"] += 1
		if isinstance(item, dict):
			kind = item["kind"]
			if kind == "if":
				body = item["body"] if self._evaluate(item["condition"]) else item["else"]
				self._push_script_frame({"kind": "if", "condition": item["condition"], "body": body, "index": 0})
			elif kind == "do" or self._evaluate(item["condition"]):
				self._push_script_frame({**item, "index": 0})
			return None
		return item

	def _local_command(self, command):
		parts = command.split(maxsplit=1)
		operation = parts[0].lower() if parts else ""
		argument = parts[1] if len(parts) > 1 else ""
		is_selection = operation in ("sel", "select") and self.instrument["index"].lower() == "main"
		if not is_selection and operation not in ("set", "dset", "sset", "getret", "read", "flushret", "eval", "exec", "execute", "logfile", "log", "print", "cd", "chdir", "close"):
			return False
		try:
			result = None
			if is_selection:
				self._active_device = None
				self._active_device = self._devices[argument.strip().lower()]
			elif operation in ("set", "dset", "sset"):
				name, separator, expression = argument.strip().partition(" ")
				if not separator or not name:
					raise ValueError("Invalid set statement")
				value = self._evaluate(expression)
				if operation == "set":
					if not datatypes.AssignEx(name, value, self.variables):
						raise ValueError("Invalid variable assignment")
				elif operation == "dset":
					datatypes.AssignDict(name, value)
				else:
					datatypes.AssignDict(name, value, self.instrument)
			elif operation in ("getret", "read"):
				value, status = self.response()
				if status:
					raise RuntimeError(value)
				if argument.strip():
					if not datatypes.AssignEx(argument.strip(), value, self.variables):
						raise ValueError("Invalid variable assignment")
			elif operation == "flushret":
				self.response_queue.clear()
			elif operation in ("eval", "exec", "execute"):
				result = self._evaluate_python(argument)
			elif operation == "logfile":
				self._logfile = self._resolve_path(argument)
			elif operation in ("log", "print"):
				with self._logfile.open("a", encoding="utf-8", newline="") as stream:
					stream.write(argument + "\r\n")
			elif operation in ("cd", "chdir"):
				path = self._resolve_path(argument).resolve(strict=True)
				if not path.is_dir():
					raise NotADirectoryError(path)
				self._directory = path
			elif operation == "close":
				self._close_connections()
			self.instrument["creturn"] = 1
			self._publish_completion(result, None, has_result=operation in ("eval", "exec", "execute"))
		except Exception as error:
			self.instrument["creturn"] = 0
			self._publish_completion(None, str(error))
			self._diagnostic_output("< " + mydebug.s_print_var(str(error)))
		self.instrument.update(rVar="", rNotice="", cdone=True, rdone=True, waitReply=False, reqdone=True)
		return True

	def _resolve_path(self, path):
		path = Path(path)
		return path if path.is_absolute() else self._directory / path

	def _substitute(self, text):
		return re.sub(r"\{([^{}]*)\}", lambda match: str(self._evaluate(match.group(1))), text)

	def _evaluate_python(self, expression):
		namespace = dict(datatypes.g_vars)
		namespace.update(self.variables)
		namespace.update(device=self, instrument=self.instrument, variables=self.variables)
		return eval(expression, namespace, namespace)

	def _evaluate(self, expression):
		expression = re.sub(r"\$([A-Za-z_]\w*)", lambda match: match.group(1).lower(), expression)
		expression = re.sub(r"\b(and|or|not|true|false)\b",
			lambda match: {"true": "True", "false": "False"}.get(match.group(1).lower(), match.group(1).lower()),
			expression, flags=re.I)
		expression = expression.replace("<>", "!=")
		expression = re.sub(r"(?<![<>=!])=(?!=)", "==", expression)
		operations = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
			ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
			ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
			ast.Gt: operator.gt, ast.GtE: operator.ge, ast.USub: operator.neg, ast.UAdd: operator.pos,
			ast.Not: operator.not_}
		def evaluate(node):
			if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool)):
				return node.value
			if isinstance(node, ast.Name):
				name = node.id.lower()
				try:
					return datatypes.EvalEx(name, self.variables)
				except KeyError:
					return datatypes.EvalDict(name)
			if isinstance(node, ast.Subscript):
				container = evaluate(node.value)
				index = evaluate(node.slice)
				if isinstance(container, (list, tuple)) and (not isinstance(index, int) or index < 0):
					raise IndexError("Invalid array index")
				if not isinstance(container, (list, tuple, dict)):
					raise TypeError("Variable is not an array or dictionary")
				return container[index]
			if isinstance(node, ast.BinOp) and type(node.op) in operations:
				return operations[type(node.op)](evaluate(node.left), evaluate(node.right))
			if isinstance(node, ast.UnaryOp) and type(node.op) in operations:
				return operations[type(node.op)](evaluate(node.operand))
			if isinstance(node, ast.BoolOp):
				values = (evaluate(value) for value in node.values)
				return all(values) if isinstance(node.op, ast.And) else any(values)
			if isinstance(node, ast.Compare) and all(type(op) in operations for op in node.ops):
				values = [evaluate(node.left), *(evaluate(value) for value in node.comparators)]
				return all(operations[type(op)](values[index], values[index + 1]) for index, op in enumerate(node.ops))
			raise ValueError("Unsupported script expression")
		return evaluate(ast.parse(expression.strip(), mode="eval").body)

	def flush(self, timeout_ms=10000):
		deadline = time.monotonic() + timeout_ms / 1000
		while not self.is_idle():
			self.loop()
			if time.monotonic() >= deadline:
				raise TimeoutError("Timed out waiting for the instrument queue")
			time.sleep(0.001)

	def request_blocking(self, command, wait=True, timeout_ms=2000):
		self.flush()
		previous_responses = len(self.response_queue)
		if not self.request(command, wait, timeout_ms):
			return None
		self.flush(max(10000, timeout_ms + 1000))
		if self.instrument["creturn"] != 1:
			value, _ = self.response_queue.pop()
			raise RuntimeError(value)
		if len(self.response_queue) > previous_responses:
			value, status = self.response_queue.pop()
			if isinstance(value, bytes):
				value = value.decode(errors="replace").strip()
			return value, status
		return None

	def close(self):
		if self._closed:
			return
		self._closed = True
		self._executor.shutdown(wait=True, cancel_futures=True)
		self._close_connections()

	def _close_connections(self):
		for key in ("viSession", "viSocket", "mbSocket"):
			resource = self.instrument[key]
			if resource is not None:
				resource.close()
				self.instrument[key] = None
		if self._resource_manager is not None:
			self._resource_manager.close()
			self._resource_manager = None
		self.instrument["state"] = False
		self._raw_buffer = b""
		self._skip_terminator = False

	def _execute(self, command, wait, timeout_ms):
		command = command.strip()
		if command.startswith("#") or not command:
			return None
		parts = command.split(maxsplit=3)
		operation = parts[0].lower()
		if command.startswith("$") or operation.startswith("ret"):
			raise NotImplementedError("Unsupported queued script syntax")
		if operation in ("if", "else", "while", "do", "until", "end", "endif", "wend",
				"select", "sel"):
			raise NotImplementedError(f"Unsupported queued script directive: {operation}")
		if operation == "flushinput":
			self._flush_input(timeout_ms)
			return None
		if operation == "flush":
			self._flush_input(timeout_ms)
			self._scpi_exchange(b"\r\n:SYSTem:ERRor?\r\n", True, timeout_ms)
			return None
		if operation == "parsepic":
			return self.parse_picture(self._resolve_path(command[len(parts[0]):].strip()))
		if operation in ("modbusread", "modbuswrite"):
			return self._execute_modbus(parts, timeout_ms)
		if operation == "sleep":
			time.sleep(float(parts[1]) / 1000)
			return None
		if operation in ("write", "send"):
			command = command[len(parts[0]):].strip()
		download = None
		payload = None
		if command.lower().startswith(("upload::", "download::")):
			operation, path, command = command.split("::", 2)
			if operation.lower() == "upload":
				payload = self._resolve_path(path).read_bytes()
				length = str(len(payload)).encode("ascii")
				payload = b"#" + str(len(length)).encode("ascii") + length + payload
				wait = False
			else:
				download = self._resolve_path(path)
				wait = True
		data = command.encode() + (payload if payload is not None else b"\r\n")
		result = self._scpi_exchange(data, wait, timeout_ms)
		if download is not None:
			if result is None:
				raise RuntimeError("Download returned no data")
			download.write_bytes(result)
			return None
		return result

	def _flush_input(self, timeout_ms=3000):
		self._raw_buffer = b""
		self._skip_terminator = False
		deadline = time.monotonic() + max(timeout_ms, 0) / 1000
		connection = self.instrument["viSocket"]
		if connection is not None:
			original_timeout = connection.gettimeout()
			try:
				connection.setblocking(False)
				while time.monotonic() <= deadline:
					try:
						data = connection.recv(2048)
					except BlockingIOError:
						break
					if not data:
						break
			finally:
				connection.settimeout(original_timeout)
		resource = self.instrument["viSession"]
		if resource is not None:
			from pyvisa.constants import StatusCode
			from pyvisa.errors import VisaIOError
			original_timeout = resource.timeout
			try:
				resource.timeout = 15
				while time.monotonic() <= deadline:
					try:
						if not resource.read_bytes(1024):
							break
					except VisaIOError as error:
						if error.error_code != StatusCode.error_timeout:
							raise
						break
			finally:
				resource.timeout = original_timeout

	def _scpi_exchange(self, data, wait, timeout_ms):
		timeout_ms = timeout_ms if timeout_ms > 0 else 1000
		timeout = timeout_ms / 1000
		if self.instrument["viIpMode"]:
			connection = self.instrument["viSocket"]
			if connection is None:
				connection = socket.create_connection((self.instrument["ipAddr"], int(self.instrument["viIpPort"])), timeout)
				self.instrument["viSocket"] = connection
			connection.settimeout(timeout)
			self.instrument["state"] = True
			connection.sendall(data)
			if wait:
				return self._read_raw_response(connection)
			return None
		import pyvisa
		resource = self.instrument["viSession"]
		if resource is None:
			self._resource_manager = pyvisa.ResourceManager()
			resource = cast(pyvisa.resources.MessageBasedResource,
				self._resource_manager.open_resource(self.instrument["viAddr"]))
			self.instrument["viSession"] = resource
		resource.timeout = max(timeout_ms, 1)
		self.instrument["state"] = True
		resource.write_raw(data)
		if wait:
			return self._unpack_scpi_block(resource.read_raw())
		return None

	@staticmethod
	def _unpack_scpi_block(data):
		if len(data) >= 2 and data[:1] == b"#" and data[1:2].isdigit():
			digits = int(data[1:2])
			if digits and len(data) >= 2 + digits and data[2:2 + digits].isdigit():
				length = int(data[2:2 + digits])
				if len(data) < 2 + digits + length:
					raise ValueError("Incomplete SCPI binary block")
				return data[2 + digits:2 + digits + length]
			if digits == 0:
				return data[2:].rstrip(b"\r\n")
		return data.rstrip(b"\r\n")

	def _read_raw_response(self, connection):
		buffer = self._raw_buffer
		while True:
			if self._skip_terminator and buffer:
				buffer = buffer.lstrip(b"\r\n")
				if buffer:
					self._skip_terminator = False
			end = None
			if len(buffer) >= 2 and buffer[:1] == b"#" and buffer[1:2].isdigit() and buffer[1:2] != b"0":
				digits = int(buffer[1:2])
				if len(buffer) >= 2 + digits:
					length = buffer[2:2 + digits]
					if not length.isdigit():
						raise ValueError("Invalid SCPI binary block length")
					end = 2 + digits + int(length)
			elif b"\n" in buffer:
				end = buffer.index(b"\n") + 1
			if end is not None and len(buffer) >= end:
				self._raw_buffer = buffer[end:].lstrip(b"\r\n")
				self._skip_terminator = buffer[:1] == b"#" and buffer[1:2] != b"0" and not self._raw_buffer
				return self._unpack_scpi_block(buffer[:end])
			chunk = connection.recv(65536)
			if not chunk:
				raise ConnectionError("Instrument closed the connection")
			buffer += chunk

	def _execute_modbus(self, parts, timeout_ms):
		from pymodbus.client import ModbusTcpClient
		operation, data_type, address = parts[:3]
		match = re.fullmatch(r"(\d+)([ifs])", data_type.lower())
		if not match:
			raise ValueError(f"Invalid Modbus data type: {data_type}")
		count, kind = int(match.group(1)), match.group(2)
		if not 1 <= count <= 125 or (kind != "s" and count not in (1, 2)):
			raise ValueError(f"Unsupported Modbus data type: {data_type}")
		client = self.instrument["mbSocket"]
		if client is None:
			client = ModbusTcpClient(self.instrument["ipAddr"], port=int(self.instrument["mbIpPort"]),
				timeout=max(timeout_ms, 1) / 1000, retries=0)
			self.instrument["mbSocket"] = client
		if not client.connect():
			raise ConnectionError("Could not connect to Modbus instrument")
		if operation.lower() == "modbusread":
			result = client.read_holding_registers(int(address), count=count, device_id=1)
			if result.isError():
				raise RuntimeError(str(result))
			return self._decode_registers(result.registers, kind)
		registers = self._encode_registers(parts[3], count, kind)
		result = client.write_registers(int(address), registers, device_id=1)
		if result.isError():
			raise RuntimeError(str(result))
		return None

	def _decode_registers(self, registers, kind):
		if len(registers) == 2 and not self.instrument["f4tWordOrder"]:
			registers = registers[::-1]
		data = b"".join(struct.pack(">H", register) for register in registers)
		if kind == "s":
			return data.decode("utf-16-be").rstrip("\x00")
		if kind == "f":
			return struct.unpack(">e" if len(registers) == 1 else ">f", data)[0]
		return int.from_bytes(data, "big")

	def _encode_registers(self, value, count, kind):
		if kind == "s":
			data = value.encode("utf-16-be")
			if len(data) > count * 2:
				raise ValueError("Modbus string exceeds register count")
			data = data.ljust(count * 2, b"\0")
		elif kind == "f":
			data = struct.pack(">e" if count == 1 else ">f", float(value))
		else:
			data = int(value).to_bytes(count * 2, "big", signed=int(value) < 0)
		registers = [int.from_bytes(data[index:index + 2], "big") for index in range(0, len(data), 2)]
		if len(registers) == 2 and not self.instrument["f4tWordOrder"]:
			registers.reverse()
		return registers

import unittest
import socketserver
import struct
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

from viqueue import viqueue
import filemisc
import wincanvas
import pyvisa


class VIQueueTests(unittest.TestCase):
	def test_instrument_state_and_addresses(self):
		device = viqueue("raw:127.0.0.1")
		self.assertEqual(device.instrument["viAddr"], "TCPIP::127.0.0.1::5025::SOCKET")
		self.assertEqual(device.instrument["mbTransID"], 0x100)
		self.assertIs(device.instrument["qreq"], device.request_queue)
		self.assertIs(device.instrument["qret"], device.response_queue)
		self.assertIs(device.instrument["cStack"], device.execution_stack)
		self.assertEqual(viqueue("example:inst1").instrument["viAddr"], "TCPIP0::example::inst1::INSTR")

	def test_request_queue_rules(self):
		device = viqueue("127.0.0.1")
		self.assertFalse(device.request("// comment"))
		device.command("*IDN?")
		device.command("300!CONF")
		device.command("*RST", force_no_wait=True)
		self.assertEqual(list(device.request_queue), [
			("*IDN?", True, 1000), ("CONF", True, 300), ("*RST", False, 0)])
		self.assertFalse(device.is_idle())

	def test_responses_and_completion(self):
		device = viqueue("127.0.0.1")
		device.response_queue.append((b" reply\r\n", 0))
		self.assertTrue(device.has_response())
		self.assertEqual(device.response(), ("reply", 0))
		device.instrument["reqdone"] = True
		self.assertTrue(device.is_request_done())
		self.assertFalse(device.is_request_done())

	def test_queued_scpi_requests_are_sequential(self):
		connection = MagicMock()
		connection.recv.side_effect = [b"Acme,", b"Instrument\r\n", b"#14", b"test\r\n"]
		device = viqueue("raw:127.0.0.1:5025")
		try:
			with patch("viqueue.socket.create_connection", return_value=connection):
				device.command("*RST")
				device.request("*IDN?")
				device.request("DATA?")
				device.flush()
			self.assertEqual(connection.sendall.call_args_list[0].args[0], b"*RST\r\n")
			self.assertEqual(connection.sendall.call_args_list[1].args[0], b"*IDN?\r\n")
			self.assertEqual(connection.sendall.call_args_list[2].args[0], b"DATA?\r\n")
			self.assertEqual(device.response(), ("Acme,Instrument", 0))
			self.assertEqual(device.response(binary=True), (b"test", 0))
			self.assertEqual(device.instrument["viIdn"], "Acme,Instrument")
		finally:
			device.close()

	def test_visa_backend_query_and_cleanup(self):
		resource = MagicMock()
		resource.read_raw.return_value = b"Instrument\n"
		manager = MagicMock()
		manager.open_resource.return_value = resource
		device = viqueue("192.0.2.1")
		try:
			with patch("pyvisa.ResourceManager", return_value=manager):
				self.assertEqual(device.request_blocking("*IDN?"), ("Instrument", 0))
			manager.open_resource.assert_called_once_with("TCPIP0::192.0.2.1::inst0::INSTR")
			resource.write_raw.assert_called_once_with(b"*IDN?\r\n")
		finally:
			device.close()
		resource.close.assert_called_once_with()
		manager.close.assert_called_once_with()

	def test_communication_failure_reports_status(self):
		device = viqueue("raw:127.0.0.1")
		try:
			with patch("viqueue.socket.create_connection", side_effect=OSError("connection failed")):
				device.request("*IDN?")
				device.flush()
			self.assertEqual(device.command_status(), 0)
			self.assertEqual(device.response(), ("connection failed", -1))
		finally:
			device.close()

	def test_optional_native_diagnostics(self):
		viewport = wincanvas.Viewport()
		device = viqueue("raw:127.0.0.1")
		try:
			output = viewport.add_control("EDIT", width=600, height=200, style=0x44)
			queue = viewport.add_control("EDIT", width=600, height=200, style=0x44)
			device.set_diagnostics(output=output, queue=queue)
			device.request("*IDN?")
			self.assertIn("*IDN?", filemisc._control_text(queue))
			connection = MagicMock()
			connection.recv.return_value = b"ACME\r\n"
			with patch("viqueue.socket.create_connection", return_value=connection):
				device.flush()
			self.assertEqual(filemisc._control_text(queue), "")
			self.assertIn("> *IDN?\r\n", filemisc._control_text(output))
			self.assertIn("< (Binary[4]) '0x41434D45'\r\n", filemisc._control_text(output))
		finally:
			device.close()
			viewport.close()

	def test_diagnostic_queue_and_stack_sync(self):
		viewport = wincanvas.Viewport()
		device = viqueue("raw:127.0.0.1")
		try:
			queue = viewport.add_control("EDIT", width=600, height=200, style=0x44)
			stack = viewport.add_control("EDIT", width=600, height=200, style=0x44)
			device.script("set $i 0\nwhile $i < 1\nset $i $i + 1\nend")
			device.set_diagnostics(queue=queue, stack=stack)
			self.assertIn("while", filemisc._control_text(queue))
			device.loop()
			self.assertEqual(filemisc._control_text(queue), "")
			device.loop()
			device.loop()
			self.assertEqual(filemisc._control_text(stack), "while $i < 1\r\n")
			device.set_diagnostics(queue=queue, stack=stack)
			self.assertEqual(filemisc._control_text(stack), "while $i < 1\r\n")
			device.flush()
			self.assertEqual(filemisc._control_text(stack), "")
			self.assertEqual(device.variables["i"], 1)
			with self.assertRaises(ValueError):
				device.set_diagnostics(queue=queue, stack=queue)
		finally:
			device.close()
			viewport.close()

	def test_diagnostic_thread_validation_precedes_enqueue(self):
		viewport = wincanvas.Viewport()
		device = viqueue("raw:127.0.0.1")
		try:
			queue = viewport.add_control("EDIT", width=600, height=200, style=0x44)
			device.set_diagnostics(queue=queue)
			errors = []
			def enqueue():
				try:
					device.request("*IDN?")
				except Exception as error:
					errors.append(error)
			thread = threading.Thread(target=enqueue)
			thread.start()
			thread.join(timeout=5)
			self.assertFalse(thread.is_alive())
			self.assertEqual(len(errors), 1)
			self.assertIsInstance(errors[0], RuntimeError)
			self.assertTrue(device.is_idle())
		finally:
			device.close()
			viewport.close()

	def test_diagnostics_require_auto_scrolling_multiline_edits(self):
		viewport = wincanvas.Viewport()
		device = viqueue("raw:127.0.0.1")
		try:
			edit = viewport.add_control("EDIT", width=600, height=200, style=4)
			with self.assertRaises(ValueError):
				device.set_diagnostics(queue=edit)
			self.assertTrue(device.is_idle())
		finally:
			device.close()
			viewport.close()

	def test_modbus_read_write_and_word_order(self):
		client = MagicMock()
		client.connect.return_value = True
		client.read_holding_registers.return_value.isError.return_value = False
		client.read_holding_registers.return_value.registers = [0x0000, 0x3fc0]
		client.write_registers.return_value.isError.return_value = False
		device = viqueue("127.0.0.1")
		device.instrument["f4tWordOrder"] = 0
		try:
			with patch("pymodbus.client.ModbusTcpClient", return_value=client):
				device.modbus_read("2f", 100)
				device.modbus_write("2f", 101, 1.5)
				device.flush()
			self.assertEqual(device.response(), (1.5, 0))
			client.read_holding_registers.assert_called_once_with(100, count=2, device_id=1)
			client.write_registers.assert_called_once_with(101, [0x0000, 0x3fc0], device_id=1)
		finally:
			device.close()

	def test_script_control_flow_and_reply_assignment(self):
		connection = MagicMock()
		connection.recv.return_value = b"42\r\n"
		device = viqueue("raw:127.0.0.1")
		try:
			with patch("viqueue.socket.create_connection", return_value=connection):
				device.script("""
				set $i 0
				while $i < 2
				  VOLT { $i + 1 }
				  set $i $i + 1
				end
				if $i = 2 then
				  $answer=MEAS?
				else
				  WRONG
				end
				do
				  set $i $i - 1
				until $i = 0
				""")
				device.flush()
			self.assertEqual([call.args[0] for call in connection.sendall.call_args_list],
				[b"VOLT 1\r\n", b"VOLT 2\r\n", b"MEAS?\r\n"])
			self.assertEqual(device.variables["answer"], "42")
			self.assertEqual(device.variables["i"], 0)
			self.assertFalse(device.has_response())
		finally:
			device.close()

	def test_script_timeout_prefixes_are_not_transmitted(self):
		device = viqueue("raw:127.0.0.1")
		try:
			with patch.object(device, "_execute", return_value=None) as execute:
				device.script("250!MEAS?\nVOLT 3\n100!MODE\n0!ZERO?")
				device.flush()
			self.assertEqual([call.args for call in execute.call_args_list], [
				("MEAS?", True, 250), ("VOLT 3", False, 1000), ("MODE", True, 100),
				("ZERO?", True, 1000)])
		finally:
			device.close()

	def test_local_script_directives_and_paths(self):
		device = viqueue("raw:127.0.0.1")
		try:
			with tempfile.TemporaryDirectory() as directory:
				device.response_queue.append((b"42\r\n", 0))
				device.script(f"cd {directory}\nread $answer\nset $count 2\n"
					"logfile result.txt\nlog Value { $count + 1 }\n$result=execute count + 3")
				device.flush()
				self.assertEqual(device.variables["answer"], "42")
				self.assertEqual(device.variables["result"], 5)
				self.assertEqual((Path(directory) / "result.txt").read_bytes(), b"Value 3\r\n")
				device.response_queue.append(("old", 0))
				device.command("flushret")
				device.flush()
				self.assertFalse(device.has_response())
		finally:
			device.close()

	def test_flushinput_drains_and_restores_timeouts(self):
		device = viqueue("raw:127.0.0.1")
		connection = MagicMock()
		connection.gettimeout.return_value = 2.5
		connection.recv.side_effect = [b"stale", BlockingIOError()]
		device.instrument["viSocket"] = connection
		device._raw_buffer = b"old"
		try:
			device.command("flushinput")
			device.flush()
			self.assertEqual(device.command_status(), 1)
			self.assertEqual(device._raw_buffer, b"")
			connection.setblocking.assert_called_once_with(False)
			connection.settimeout.assert_called_once_with(2.5)
		finally:
			device.close()
		device = viqueue("127.0.0.1")
		resource = MagicMock()
		resource.timeout = 500
		resource.read_bytes.side_effect = [b"stale", pyvisa.errors.VisaIOError(pyvisa.constants.StatusCode.error_timeout)]
		device.instrument["viSession"] = resource
		try:
			device.command("flushinput")
			device.flush()
			self.assertEqual(device.command_status(), 1)
			self.assertEqual(resource.timeout, 500)
			self.assertEqual(resource.read_bytes.call_count, 2)
		finally:
			device.close()

	def test_flush_directive_and_error_queue(self):
		device = viqueue("raw:127.0.0.1")
		try:
			device.response_queue.append(("old", 0))
			with patch.object(device, "_flush_input") as drain, patch.object(device, "_scpi_exchange", return_value=b"0,no error") as exchange:
				device.command("flush")
				device.flush()
			drain.assert_called_once_with(1000)
			exchange.assert_called_once_with(b"\r\n:SYSTem:ERRor?\r\n", True, 1000)
			self.assertFalse(device.has_response())
			with patch.object(device, "request_blocking", side_effect=[("-100,problem", 0), ("0,No error", 0)]):
				self.assertTrue(device.flush_errors())
		finally:
			device.close()

	def test_indexed_script_variables(self):
		device = viqueue("raw:127.0.0.1")
		device.variables["Values"] = [0, 0]
		try:
			connection = MagicMock()
			connection.recv.return_value = b"7\n"
			with patch("viqueue.socket.create_connection", return_value=connection):
				device.script("set $values[0] 2\n$values[1]=MEAS?\n$result=eval Values[0] + 3")
				device.flush()
			self.assertEqual(device.variables["Values"], [2, "7"])
			self.assertEqual(device.variables["result"], 5)
		finally:
			device.close()

	def test_python_eval_and_exec_expressions(self):
		device = viqueue("raw:127.0.0.1")
		device.variables.update(values=[1, 2, 3], scale=4)
		try:
			device.script("$result=eval {'total': sum(value * scale for value in values), 'text': 'a=b'}\n"
				"$host=exec instrument['ipAddr'].upper()\nexecute len(values)")
			device.flush()
			self.assertEqual(device.variables["result"], {"total": 24, "text": "a=b"})
			self.assertEqual(device.variables["host"], "127.0.0.1")
			self.assertEqual(device.response(), (3, 0))
		finally:
			device.close()

	def test_python_expression_errors_are_reported(self):
		device = viqueue("raw:127.0.0.1")
		try:
			device.command("eval missing_name + 1")
			device.flush()
			message, status = device.response()
			self.assertEqual(status, -1)
			self.assertIn("missing_name", message)
			self.assertEqual(device.command_status(), 0)
		finally:
			device.close()

	def test_python_expression_none_and_side_effects(self):
		device = viqueue("raw:127.0.0.1")
		try:
			device.script("$result=eval None\nexec\tvariables.update({'changed': True})\n"
				"eval (device is not None, instrument['ipAddr'])")
			device.flush()
			self.assertIn("result", device.variables)
			self.assertIsNone(device.variables["result"])
			self.assertTrue(device.variables["changed"])
			self.assertEqual(device.response(), (None, 0))
			self.assertEqual(device.response(), ((True, "127.0.0.1"), 0))
		finally:
			device.close()

	def test_unsupported_directives_are_not_sent(self):
		device = viqueue("raw:127.0.0.1")
		try:
			with patch("viqueue.socket.create_connection") as connect:
				device.command("select sc")
				device.flush()
				connect.assert_not_called()
			self.assertEqual(device.command_status(), 0)
			self.assertIn("Unsupported queued script directive", device.response()[0])
		finally:
			device.close()

	def test_main_queue_selects_and_forwards_without_consuming_other_replies(self):
		main = viqueue("main")
		target = viqueue("raw:127.0.0.1")
		target.response_queue.append((b"older", 0))
		try:
			main.register_device("sc", target)
			with patch.object(target, "_execute", side_effect=[b"42", None]) as execute:
				main.script("select sc\n$answer=MEAS?\nVOLT 4")
				main.flush()
			self.assertEqual(main.variables["answer"], "42")
			self.assertEqual([call.args for call in execute.call_args_list], [
				("MEAS?", True, 1000), ("VOLT 4", False, 1000)])
			self.assertEqual(target.response(), ("older", 0))
			self.assertFalse(target.has_response())
		finally:
			main.close()
			target.close()

	def test_main_queue_routes_real_raw_tcp(self):
		class Handler(socketserver.StreamRequestHandler):
			def handle(self):
				while line := self.rfile.readline():
					if line.strip() == b"MEAS?":
						self.wfile.write(b"42\r\n")
		server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
		thread = threading.Thread(target=server.serve_forever, daemon=True)
		thread.start()
		main = viqueue("main")
		target = viqueue(f"raw:127.0.0.1:{server.server_address[1]}")
		try:
			main.register_device("sc", target)
			main.script("select sc\nMEAS?")
			main.flush()
			self.assertEqual(main.response(), ("42", 0))
			self.assertFalse(target.has_response())
		finally:
			main.close()
			target.close()
			server.shutdown()
			server.server_close()
			thread.join()

	def test_main_queue_failed_selection_does_not_use_previous_target(self):
		main = viqueue("main")
		target = viqueue("raw:127.0.0.1")
		try:
			main.register_device("sc", target)
			with patch.object(target, "_execute", return_value=None) as execute:
				main.script("select sc\nselect missing\nVOLT 4")
				main.flush()
				execute.assert_not_called()
			self.assertEqual(main.command_status(), 0)
			self.assertEqual(main.response_queue[-1], ("No instrument selected", -1))
		finally:
			main.close()
			target.close()

	def test_named_completion_notices(self):
		device = viqueue("raw:127.0.0.1")
		other = viqueue("raw:127.0.0.2")
		try:
			with patch.object(device, "_execute", side_effect=[b"answer", None, OSError("failed")]):
				device.request("retquery READ?")
				device.command("retdone VOLT 1")
				device.request("reterror BAD?")
				device.flush()
			self.assertEqual(other.take_notice("query"), (b"answer", 0))
			self.assertEqual(other.take_notice("done"), (None, 0))
			self.assertEqual(other.take_notice("error"), ("failed", -1))
			self.assertFalse(device.has_response())
		finally:
			for name in ("query", "done", "error"):
				device.notices.pop(name, None)
			device.close()
			other.close()

	def test_forward_waits_for_existing_target_request_and_reports_failure(self):
		main = viqueue("main")
		target = viqueue("raw:127.0.0.1")
		try:
			main.register_device("sc", target)
			with patch.object(target, "_execute", side_effect=[b"older", OSError("instrument failed")]) as execute:
				target.request("OLD?")
				main.script("select sc\nretforward READ?")
				main.flush()
			self.assertEqual([call.args[0] for call in execute.call_args_list], ["OLD?", "READ?"])
			self.assertEqual(target.response(), ("older", 0))
			self.assertEqual(main.take_notice("forward"), ("instrument failed", -1))
			self.assertFalse(main.has_response())
		finally:
			main.notices.pop("forward", None)
			main.close()
			target.close()

	def test_notice_reports_invalid_reply_assignment(self):
		device = viqueue("raw:127.0.0.1")
		device.variables["values"] = [0]
		try:
			with patch.object(device, "_execute", return_value=b"42"):
				device.request("$values[9]=retbad READ?")
				device.flush()
			self.assertEqual(device.take_notice("bad"), ("Invalid variable assignment", -1))
			self.assertEqual(device.command_status(), 0)
		finally:
			device.notices.pop("bad", None)
			device.close()

	def test_identity_and_modbus_blocking_helpers(self):
		device = viqueue("127.0.0.1")
		try:
			with patch.object(device, "request_blocking", side_effect=[("ACME,MODEL", 0), (42, 0), (None)]):
				self.assertEqual(device.get_id(), "ACME,MODEL")
				self.assertEqual(device.modbus_read_blocking("1i", 100), 42)
				self.assertIsNone(device.command_blocking("*RST"))
		finally:
			device.close()

	def test_identity_falls_back_to_raw_and_classifies(self):
		device = viqueue("192.0.2.1")
		try:
			with patch.object(device, "request_blocking", side_effect=[RuntimeError("VISA unavailable"), ("TEK,MSO123", 0)]):
				self.assertEqual(device.get_id(), "TEK,MSO123")
			self.assertEqual(device.instrument["viIpMode"], 1)
			self.assertEqual(device.instrument["viAddr"], "TCPIP::192.0.2.1::5025::SOCKET")
			self.assertEqual(device.instrument["viType"], "sc Oscilloscope")
			device.toggle_mode()
			self.assertEqual(device.instrument["viAddr"], "TCPIP0::192.0.2.1::inst0::INSTR")
			device.command("*RST")
			with self.assertRaises(RuntimeError):
				device.toggle_mode()
		finally:
			device.close()

	def test_real_raw_tcp_binary_then_text(self):
		class Handler(socketserver.StreamRequestHandler):
			def handle(self):
				while line := self.rfile.readline():
					if line.strip() == b"BINARY?":
						self.wfile.write(b"#14test\r\n")
					elif line.strip() == b"NEXT?":
						self.wfile.write(b"next\r\n")
		server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
		thread = threading.Thread(target=server.serve_forever, daemon=True)
		thread.start()
		device = viqueue(f"raw:127.0.0.1:{server.server_address[1]}")
		try:
			device.request("BINARY?")
			device.request("NEXT?")
			device.flush()
			self.assertEqual(device.response(binary=True), (b"test", 0))
			self.assertEqual(device.response(), ("next", 0))
		finally:
			device.close()
			server.shutdown()
			server.server_close()
			thread.join()

	def test_blocking_request_preserves_earlier_responses(self):
		connection = MagicMock()
		connection.recv.return_value = b"new\n"
		device = viqueue("raw:127.0.0.1")
		device.response_queue.append((b"old", 0))
		try:
			with patch("viqueue.socket.create_connection", return_value=connection):
				self.assertEqual(device.request_blocking("READ?"), ("new", 0))
			self.assertEqual(device.response(), ("old", 0))
		finally:
			device.close()

	def test_file_transfers(self):
		connection = MagicMock()
		connection.recv.return_value = b"#15hello\r\n"
		device = viqueue("raw:127.0.0.1")
		try:
			with tempfile.TemporaryDirectory() as directory:
				source = Path(directory) / "source.bin"
				target = Path(directory) / "target.bin"
				source.write_bytes(b"abc")
				with patch("viqueue.socket.create_connection", return_value=connection):
					device.upload_file(source, "DATA,")
					device.download_file(target, "DATA?")
					device.flush()
				self.assertEqual(connection.sendall.call_args_list[0].args[0], b"DATA,#13abc")
				self.assertEqual(target.read_bytes(), b"hello")
		finally:
			device.close()

	def test_picture_download_and_collision(self):
		connection = MagicMock()
		image = b"\x89PNG\r\n\x1a\nimage"
		payload = b"prefix" + image
		connection.recv.return_value = b"#2" + str(len(payload)).encode() + payload + b"\r\n"
		device = viqueue("raw:127.0.0.1")
		try:
			with tempfile.TemporaryDirectory() as directory:
				path = Path(directory) / "capture.bin"
				with patch("viqueue.socket.create_connection", return_value=connection):
					device.download_picture(path, "IMAGE?")
					device.flush()
				target = path.with_suffix(".png")
				self.assertEqual(target.read_bytes(), image)
				self.assertFalse(path.exists())
				self.assertEqual(device.response(), (str(target), 0))
				path.write_bytes(payload)
				with self.assertRaises(FileExistsError):
					device.parse_picture(path)
				self.assertEqual(path.read_bytes(), payload)
				self.assertEqual(target.read_bytes(), image)
				self.assertEqual(device.parse_picture(payload), (image, ".png"))
		finally:
			device.close()

	def test_script_download_markers_use_distinct_paths(self):
		device = viqueue("raw:127.0.0.1")
		try:
			with tempfile.TemporaryDirectory() as directory:
				path = Path(directory) / "capture.bin"
				device.script("#DATA?\n##IMAGE?", file=path)
				items = device.request_queue[0][0]
				self.assertEqual(items[0], (f"download::{path}::DATA?", True, 10000))
				self.assertEqual(items[1], (f"download::{path.with_name('capture_001.bin')}::IMAGE?", True, 10000))
				self.assertEqual(items[2][0], f"parsepic {path.with_name('capture_001.bin')}")
		finally:
			device.close()

	def test_multiple_screenshots_use_distinct_names(self):
		device = viqueue("raw:127.0.0.1")
		try:
			with tempfile.TemporaryDirectory() as directory:
				path = Path(directory) / "capture.bin"
				result = device.save_screenshot(path, [("!IMAGE?", 5000), ("!IMAGE?", 5000)])
				self.assertEqual(result, str(path.with_name("capture_001.bin")))
				self.assertEqual(device.request_queue[0][0], f"download::{path}::IMAGE?")
				self.assertEqual(device.request_queue[2][0], f"download::{result}::IMAGE?")
		finally:
			device.close()

	def test_real_modbus_tcp_read_and_write(self):
		registers = {100: 42}
		class Handler(socketserver.BaseRequestHandler):
			def handle(self):
				while True:
					header = self._read(7)
					if not header:
						return
					transaction, protocol, length, unit = struct.unpack(">HHHB", header)
					request = self._read(length - 1)
					function, address, count = struct.unpack(">BHH", request[:5])
					if function == 3:
						data = b"".join(struct.pack(">H", registers.get(address + offset, 0))
							for offset in range(count))
						response = bytes((function, len(data))) + data
					else:
						for offset in range(count):
							registers[address + offset] = struct.unpack_from(">H", request, 6 + 2 * offset)[0]
						response = request[:5]
					self.request.sendall(struct.pack(">HHHB", transaction, protocol, len(response) + 1, unit) + response)

			def _read(self, length):
				data = b""
				while len(data) < length:
					chunk = self.request.recv(length - len(data))
					if not chunk:
						return b""
					data += chunk
				return data
		server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
		thread = threading.Thread(target=server.serve_forever, daemon=True)
		thread.start()
		device = viqueue("127.0.0.1")
		device.instrument["mbIpPort"] = server.server_address[1]
		try:
			device.modbus_read("1i", 100)
			device.modbus_write("1i", 101, 123)
			device.modbus_read("1i", 101)
			device.flush()
			self.assertEqual(device.response(), (42, 0))
			self.assertEqual(device.response(), (123, 0))
		finally:
			device.close()
			server.shutdown()
			server.server_close()
			thread.join()

	def test_f4t_register_map_and_temperature_conversion(self):
		device = viqueue("127.0.0.1")
		device.instrument.update(f4tDataMap=2, f4tWordOrder=1, f4tUnits=0)
		try:
			with patch.object(device, "modbus_read_blocking", side_effect=[770, 1]):
				self.assertEqual(device.f4t_temperature(), 25)
				self.assertTrue(device.f4t_enable())
			with patch.object(device, "modbus_write", return_value=True) as write:
				self.assertTrue(device.f4t_setpoint(25))
				write.assert_called_once_with("1i", 300, 770)
			device.instrument["f4tDataMap"] = 1
			with patch.object(device, "modbus_write", return_value=True) as write:
				self.assertTrue(device.f4t_enable(True))
				write.assert_called_once_with("1i", 16594, 63)
		finally:
			device.close()

	def test_f4t_identity_and_background_read(self):
		device = viqueue("127.0.0.1")
		device.instrument.update(f4tDataMap=1, f4tWordOrder=1, f4tUnits=1)
		try:
			with patch.object(device, "modbus_read_blocking", side_effect=[123, 456, " Watlow ", " F4T "]):
				self.assertEqual(device.f4t_get_id(), "Watlow,F4T,123,456")
			self.assertTrue(device.f4t_read_bg(1, "temperature"))
			self.assertEqual(device.request_queue.pop(), ("$temperature=modbusread 2f 27586", True, 1000))
			self.assertEqual(device.f4t_read_bg_process_reply(1, 21.5), 21.5)
			device.instrument["f4tDataMap"] = 2
			self.assertEqual(device.f4t_read_bg_process_reply(1, 215), 21.5)
			self.assertTrue(device.f4t_read_bg_process_reply(2, 1))
			with patch.object(device, "modbus_read_blocking", side_effect=[11, 22, 3, 4]):
				self.assertEqual(device.f4t_get_id(), "11,22,,03.00004")
		finally:
			device.close()

	def test_f4t_word_order_uses_fallback_register(self):
		device = viqueue("127.0.0.1")
		device.instrument["f4tDataMap"] = 1
		try:
			with patch.object(device, "modbus_read_blocking", side_effect=[RuntimeError("unavailable"), 1331]) as read:
				self.assertEqual(device.f4t_get_word_order(), 0)
				self.assertEqual([call.args for call in read.call_args_list], [("1i", 14092), ("1i", 6736)])
		finally:
			device.close()


if __name__ == "__main__":
	unittest.main()
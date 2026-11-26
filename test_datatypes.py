import ctypes
import os
import socket
import tempfile
import unittest

import datatypes


class DataTypesTests(unittest.TestCase):
	def test_dictionary_and_temperature(self):
		self.assertTrue(datatypes.is_dictionary({}))
		self.assertFalse(datatypes.is_dictionary([]))
		self.assertTrue(datatypes.is_scripting_dictionary({}))
		self.assertEqual(datatypes.temperature_f_to_c(212), 100)
		self.assertEqual(datatypes.temperature_c_to_f(100), 212)

	def test_bits_and_first_split(self):
		self.assertEqual(datatypes._Bits(5), "00000101")
		self.assertEqual(datatypes._Bits(-1, 4), "1111")
		self.assertEqual(datatypes._Bits(5, 0), "")
		self.assertEqual(datatypes.string_split_first("one,two,three"), ["one", "two,three"])
		self.assertEqual(datatypes.string_split_first("one--two", "--"), ["one", "-two"])
		self.assertEqual(datatypes.string_split_first("one"), ["one", ""])

	def test_assign_and_eval_variables(self):
		variables = {"Array": [[1, 2], [3, 4]], "map": {"name": "old"}}
		self.assertEqual(datatypes.AssignEx("$answer", 42, variables), 1)
		self.assertEqual(datatypes.EvalEx("ANSWER", variables), 42)
		self.assertEqual(datatypes.AssignEx("array[1][0]", 7, variables), 1)
		self.assertEqual(datatypes.EvalEx("Array[1][0]", variables), 7)
		self.assertEqual(datatypes.AssignEx("map('name')", "new", variables), 1)
		self.assertEqual(datatypes.EvalEx("map[\"name\"]", variables), "new")
		self.assertEqual(datatypes.AssignEx("array[-1]", 5, variables), 0)
		with self.assertRaises(IndexError):
			datatypes.EvalEx("array[2]", variables)
		with self.assertRaises(KeyError):
			datatypes.EvalEx("missing", variables)

	def test_assign_and_eval_dictionary(self):
		variables = {}
		self.assertEqual(datatypes.AssignDict("$name", 3, variables), 3)
		self.assertEqual(datatypes.EvalDict("name", variables), 3)
		with self.assertRaises(KeyError):
			datatypes.EvalDict("missing", variables)
		with self.assertRaises(TypeError):
			datatypes.AssignDict("name", 1, [])

	def test_dll_and_file_handles(self):
		self.assertFalse(datatypes.is_dll_handle_valid(0))
		self.assertFalse(datatypes.is_dll_handle_valid(True))
		if os.name == "nt":
			self.assertTrue(datatypes.is_dll_handle_valid(ctypes.WinDLL("kernel32")))
		with tempfile.TemporaryFile() as handle:
			self.assertTrue(datatypes.is_file_handle(handle))
			self.assertTrue(datatypes.is_file_handle(handle.fileno()))
			if os.name == "nt":
				import msvcrt
				self.assertTrue(datatypes.is_file_handle(msvcrt.get_osfhandle(handle.fileno())))
		self.assertFalse(datatypes.is_file_handle(handle))
		self.assertFalse(datatypes.is_file_handle(-1))

	def test_connected_socket(self):
		with socket.socket() as listener:
			listener.bind(("127.0.0.1", 0))
			listener.listen()
			with socket.create_connection(listener.getsockname()) as client:
				with listener.accept()[0] as server:
					self.assertTrue(datatypes.is_tcp_socket(client))
					self.assertEqual(datatypes.socket_to_ip(server.fileno()), "127.0.0.1")
					self.assertEqual(server.getpeername()[0], "127.0.0.1")
		self.assertFalse(datatypes.is_tcp_socket(client))
		self.assertEqual(datatypes.socket_to_ip(-1), 0)

	def test_engineering_notation(self):
		self.assertEqual(datatypes.number_engineering(1234), "1.23 k")
		self.assertEqual(datatypes.number_engineering(-0.0012, 1), "-1.2 m")
		self.assertEqual(datatypes.number_engineering(0), "0.00 ")
		self.assertEqual(datatypes.number_engineering(1e-31), "0.10 q")
		with self.assertRaises(ValueError):
			datatypes.number_engineering(float("inf"))


if __name__ == "__main__":
	unittest.main()
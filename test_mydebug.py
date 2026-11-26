import io
import unittest
from contextlib import redirect_stdout

import mydebug
from deque import pQue


class DebugTests(unittest.TestCase):
	def test_scalar_and_pair_formatting(self):
		self.assertEqual(mydebug.s_print_var(42, name="count", eol=True), "count = (Int32) 42\r\n")
		self.assertEqual(mydebug.s_print_var(b"\x01\xff"), "(Binary[2]) '0x01FF'")
		self.assertEqual(mydebug.s_print_var("123"), "(String) 123")
		self.assertEqual(mydebug.s_print_vars("output, ", "$count", 2, "label", "ok"),
			"output count = (Int32) 2, label = (String) 'ok'\r\n")
		output = io.StringIO()
		with redirect_stdout(output):
			mydebug.console_print_vars("output, ", "value", 1)
		self.assertEqual(output.getvalue(), "output value = (Int32) 1\r\n")

	def test_nested_arrays_and_cycles(self):
		self.assertEqual(mydebug.s_print_var([1, 2]), "(Array[2]) [ (Int32) 1, (Int32) 2 ]")
		self.assertEqual(mydebug.s_print_var([[1], [2]]), "(Array[2][1]) [ [ (Int32) 1 ]\r\n[ (Int32) 2 ] ]")
		value = []
		value.append(value)
		self.assertIn("<recursive>", mydebug.s_print_var(value))

	def test_dictionary_queue(self):
		value = {"head": 2, "tail": 3, "2": "a", "3": "b", "cmd": "while"}
		self.assertEqual(mydebug.s_print_var(value),
			"(Object[5]) ( cmd=(String) 'while', List: (String) 'a', (String) 'b' )")

	def test_program_queue_and_recursive_contents(self):
		queue = pQue("while", "$count < 2")
		queue.push("statement")
		queue.push(queue)
		text = mydebug.s_print_var(queue)
		self.assertIn("(pQue[2])", text)
		self.assertIn("cmd=(String) 'while'", text)
		self.assertIn("List: (String) 'statement'", text)
		self.assertIn("<recursive>", text)


if __name__ == "__main__":
	unittest.main()
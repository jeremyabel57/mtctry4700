import unittest

import filemisc
import wincanvas
import winfuncs


class EditControlTests(unittest.TestCase):
	def setUp(self):
		self.viewport = wincanvas.Viewport()
		self.edit = self.viewport.add_control("EDIT", width=600, height=200, style=0x44)

	def tearDown(self):
		self.viewport.close()

	def test_queue_and_stack_line_operations(self):
		winfuncs.gui_ctrl_edit_queue_push(self.edit, "first")
		winfuncs.gui_ctrl_edit_queue_push(self.edit, "second")
		winfuncs.gui_ctrl_edit_stack_push(self.edit, "third")
		self.assertEqual(filemisc._control_text(self.edit), "first\r\nsecond\r\nthird\r\n")
		winfuncs.gui_ctrl_edit_queue_pop(self.edit)
		self.assertEqual(filemisc._control_text(self.edit), "second\r\nthird\r\n")
		winfuncs.gui_ctrl_edit_stack_pop(self.edit)
		self.assertEqual(filemisc._control_text(self.edit), "second\r\n")
		winfuncs.gui_ctrl_edit_stack_pop(self.edit)
		self.assertEqual(filemisc._control_text(self.edit), "")

	def test_line_removal_and_unicode(self):
		winfuncs.gui_ctrl_edit_append(self.edit, "first\r\n\U0001f4f7\r\nlast")
		winfuncs.gui_ctrl_edit_remove_line(self.edit, 1)
		self.assertEqual(filemisc._control_text(self.edit), "first\r\nlast")
		winfuncs.gui_ctrl_edit_remove_line(self.edit, -1)
		self.assertEqual(filemisc._control_text(self.edit), "first\r\n")
		winfuncs.gui_ctrl_edit_remove_line(self.edit, -100)
		self.assertEqual(filemisc._control_text(self.edit), "")

	def test_invalid_handle(self):
		with self.assertRaises(ValueError):
			winfuncs.gui_ctrl_edit_append(0, "text")
		button = self.viewport.add_control("BUTTON", "Not an edit")
		with self.assertRaises(ValueError):
			winfuncs.gui_ctrl_edit_append(button, "text")

	def test_wrapped_line_is_removed_as_one_item(self):
		wincanvas.user32.SendMessageW(self.edit, 0x00C5, 4096, 0)
		winfuncs.gui_ctrl_edit_queue_push(self.edit, "a" * 1000 + "\U0001f4f7")
		self.assertIn("\U0001f4f7", filemisc._control_text(self.edit))
		winfuncs.gui_ctrl_edit_queue_push(self.edit, "next")
		winfuncs.gui_ctrl_edit_queue_pop(self.edit)
		self.assertEqual(filemisc._control_text(self.edit), "next\r\n")


if __name__ == "__main__":
	unittest.main()
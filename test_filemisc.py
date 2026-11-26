import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import filemisc
import wincanvas


class FileMiscTests(unittest.TestCase):
	def test_filename_auto_increment(self):
		with tempfile.TemporaryDirectory() as directory:
			path = Path(directory) / "capture.png"
			self.assertEqual(filemisc.file_name_auto_increment(path), str(path))
			path.touch()
			(Path(directory) / "capture_001.png").touch()
			self.assertEqual(filemisc.file_name_auto_increment(path), str(Path(directory) / "capture_002.png"))
			(Path(directory) / "capture_009.png").touch()
			self.assertEqual(filemisc.file_name_auto_increment(Path(directory) / "capture_009.png"),
				str(Path(directory) / "capture_010.png"))
			(Path(directory) / "capture_000.png").touch()
			self.assertEqual(filemisc.file_name_auto_increment(Path(directory) / "capture_000.png"),
				str(Path(directory) / "capture_002.png"))

	def test_full_windows_path(self):
		for path in ("", "...", "file.txt", r"C:\file.txt", r"C:folder\file.txt"):
			self.assertFalse(filemisc.is_full_path_specified(path), path)
		for path in (r"C:\folder\file.txt", r"\\server\share\folder\file.txt"):
			self.assertTrue(filemisc.is_full_path_specified(path), path)

	def test_ini_arrays_and_dimension_changes(self):
		with tempfile.TemporaryDirectory() as directory:
			path = Path(directory) / "settings.ini"
			default = ["default"]
			self.assertIs(filemisc.ini_read_array(default, "data", "Settings", path), default)
			self.assertTrue(filemisc.ini_write_array([["a", "b"], ["c", "d"]], "data", "Settings", path))
			self.assertEqual(filemisc.ini_read_array(default, "data", "settings", path), [["a", "b"], ["c", "d"]])
			self.assertTrue(filemisc.ini_write_array(["hello", "100%", "\u03a9"], "data", "Settings", path))
			self.assertEqual(filemisc.ini_read_array(default, "data", "Settings", path), ["hello", "100%", "\u03a9"])
			self.assertTrue(filemisc.ini_write_array([["new"]], "data", "Settings", path))
			self.assertEqual(filemisc.ini_read_array(default, "data", "Settings", path), [["new"]])
			self.assertFalse(filemisc.ini_write_array([["a"], ["b", "c"]], "data", "Settings", path))
			self.assertEqual(filemisc.ini_read_array(default, "data", "Settings", path), [["new"]])

	def test_ini_native_controls(self):
		viewport = wincanvas.Viewport()
		try:
			edit = viewport.add_control("EDIT", "original")
			checkbox = viewport.add_control("BUTTON", "Check", style=3)
			combo = viewport.add_control("COMBOBOX", "", height=100, style=2)
			with tempfile.TemporaryDirectory() as directory:
				path = Path(directory) / "settings.ini"
				filemisc.ini_write_gui(edit, "text", "Settings", path)
				filemisc._set_control_text(edit, "changed")
				filemisc.ini_read_gui(edit, "text", "Settings", path)
				self.assertEqual(filemisc._control_text(edit), "original")
				filemisc.gui_checkbox(checkbox, True)
				self.assertTrue(filemisc.gui_checkbox(checkbox))
				filemisc.ini_write_gui_checkbox(checkbox, "check", "Settings", path)
				filemisc.gui_checkbox(checkbox, False)
				filemisc.ini_read_gui_checkbox(checkbox, "check", "Settings", path)
				self.assertTrue(filemisc.gui_checkbox(checkbox))
				filemisc._ini_write("choiceList", "one|two|three", "Settings", str(path))
				filemisc._ini_write("choice", "two", "Settings", str(path))
				filemisc.ini_read_gui_combo_box(combo, "choice", "Settings", path)
				self.assertEqual(filemisc._combo_items(combo), ["one", "two", "three"])
				self.assertEqual(filemisc._control_text(combo), "two")
				filemisc.ini_write_gui_combo_box(combo, "copy", "Settings", path)
				self.assertEqual(filemisc._ini_read("copyList", "", "Settings", str(path)), "one|two|three")
				self.assertEqual(filemisc._ini_read("copy", "", "Settings", str(path)), "two")
		finally:
			viewport.close()

	def test_excel_write_and_cleanup(self):
		excel = MagicMock()
		workbook = excel.Workbooks.Open.return_value
		with patch("pythoncom.CoInitialize") as initialize, patch("pythoncom.CoUninitialize") as uninitialize:
			with patch("win32com.client.DispatchEx", return_value=excel):
				self.assertTrue(filemisc.cloud_excel_write("Sheet1", 2, 3, 42, "book.xlsx"))
		initialize.assert_called_once_with()
		uninitialize.assert_called_once_with()
		excel.Workbooks.Open.assert_called_once_with("book.xlsx")
		self.assertEqual(workbook.Worksheets("Sheet1").Cells(2, 3).Value, 42)
		workbook.Save.assert_called_once_with()
		workbook.Close.assert_called_once_with(SaveChanges=False)
		excel.Quit.assert_called_once_with()

	def test_excel_error_closes_without_saving(self):
		excel = MagicMock()
		workbook = excel.Workbooks.Open.return_value
		workbook.Worksheets.side_effect = RuntimeError("write failed")
		with patch("pythoncom.CoInitialize"), patch("pythoncom.CoUninitialize") as uninitialize:
			with patch("win32com.client.DispatchEx", return_value=excel):
				with self.assertRaisesRegex(RuntimeError, "write failed"):
					filemisc.cloud_excel_write("Sheet1", 1, 1, 42, "book.xlsx")
		workbook.Save.assert_not_called()
		workbook.Close.assert_called_once_with(SaveChanges=False)
		excel.Quit.assert_called_once_with()
		uninitialize.assert_called_once_with()


if __name__ == "__main__":
	unittest.main()
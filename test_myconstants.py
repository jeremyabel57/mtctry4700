import re
import unittest
from pathlib import Path

import myconstants


class ConstantsTests(unittest.TestCase):
	def test_color_values_match_include(self):
		text = Path(__file__).with_name("ColorConstants.au3").read_text()
		items = re.findall(r"^Global Const \$(\w+)\s*=\s*(0x[0-9A-Fa-f]+)", text, re.MULTILINE)
		self.assertGreater(len(items), 40)
		for name, value in items:
			self.assertEqual(getattr(myconstants, name), int(value, 16), name)

	def test_every_original_icon_and_color_is_present(self):
		text = Path(__file__).with_name("myconstants.au3").read_text()
		items = re.findall(r"^\s*Global Const \$((?:ICON|COLOR)_\w+)", text, re.MULTILINE | re.IGNORECASE)
		for name in items:
			self.assertTrue(hasattr(myconstants, name), name)

	def test_icons_and_unicode(self):
		self.assertEqual(myconstants.ICON_SCREENSHOT, myconstants.ICON_STILL_CAMERA)
		self.assertEqual(myconstants.ICON_SEARCH2, "\U0001f50d\ufe0e")
		self.assertEqual(myconstants.ICON_RTRI, "\u23f5")
		self.assertEqual(myconstants.ICON_NEXT1, "\u23f5\u2759")
		self.assertEqual(myconstants.ChrW32(0x1F4BE), "\U0001f4be")
		with self.assertRaises(ValueError):
			myconstants.ChrW32(0x110000)

	def test_all_original_icon_values(self):
		text = Path(__file__).with_name("myconstants.au3").read_text()
		definitions = re.findall(r"^\s*Global Const \$(ICON_\w+)\s*=\s*([^;\r\n]+)",
			text, re.MULTILINE | re.IGNORECASE)
		for name, expression in definitions:
			parts = []
			for part in expression.split("&"):
				part = part.strip()
				match = re.fullmatch(r"Chr(?:W32|W)?\((0x[0-9A-Fa-f]+)\)", part, re.IGNORECASE)
				if match:
					parts.append(chr(int(match.group(1), 16)))
				elif len(part) >= 2 and part[0] == part[-1] == '"':
					parts.append(part[1:-1])
				else:
					self.assertTrue(part.startswith("$"), part)
					parts.append(getattr(myconstants, part[1:]))
			expected = "".join(parts).encode("utf-16-le", "surrogatepass").decode("utf-16-le")
			self.assertEqual(getattr(myconstants, name), expected, name)


if __name__ == "__main__":
	unittest.main()
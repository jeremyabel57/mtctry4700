import runpy
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class DependencyInstallationTests(unittest.TestCase):
	def test_install_dependencies_uses_current_interpreter(self):
		with patch("main.subprocess.run") as run:
			main.install_dependencies()
		requirements = Path(main.__file__).resolve().with_name("requirements.txt")
		run.assert_called_once_with(
			[sys.executable, "-m", "pip", "install", "-r", str(requirements)], check=True
		)

	def test_startup_installs_before_creating_viewport(self):
		operations = []
		with patch("subprocess.run", side_effect=lambda *args, **kwargs: operations.append("install")):
			with patch("wincanvas.Viewport") as viewport:
				viewport.side_effect = lambda: operations.append("viewport") or viewport.return_value
				viewport.return_value.loop.return_value = False
				runpy.run_path(main.__file__, run_name="__main__")
		self.assertEqual(operations, ["install", "viewport"])

	def test_startup_stops_if_installation_fails(self):
		error = subprocess.CalledProcessError(1, "pip")
		with patch("subprocess.run", side_effect=error):
			with patch("wincanvas.Viewport") as viewport:
				with self.assertRaises(subprocess.CalledProcessError):
					runpy.run_path(main.__file__, run_name="__main__")
				viewport.assert_not_called()


if __name__ == "__main__":
	unittest.main()
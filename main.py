

import subprocess
import sys
import time
from pathlib import Path

loop = []

from winmain import MainWindow
from wincanvas import ViewportMode


def install_dependencies():
	"""Install the declared Python dependencies into the current environment."""
	requirements = Path(__file__).resolve().with_name("requirements.txt")
	subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements)], check=True)


def main_setup():
	window = MainWindow()
	try:
		viewport = window.add_tab("Tab 1", mode=ViewportMode.MIN)
		viewport.add_webview(width=viewport.canvas_width, height=viewport.canvas_height, url="http://google.com")
		window.add_tab("Tab 2")
		window.add_tab("Tab 3")
		window.select_tab(0)
		window.set_visible(True)
		loop.append(window.loop)
	except Exception:
		window.close()
		raise
	return window


def main_loop():
	while True:
		for i in loop:
			if not i():
				return
		time.sleep(0)    # yield this cpu slice for other processes


if __name__ == "__main__":
	install_dependencies()
	main_setup()
	main_loop()


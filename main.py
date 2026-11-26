

import subprocess
import sys
import time
from pathlib import Path

loop = []

from wincanvas import Viewport


def install_dependencies():
	"""Install the declared Python dependencies into the current environment."""
	requirements = Path(__file__).resolve().with_name("requirements.txt")
	subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements)], check=True)


def main_setup():
	viewport = Viewport()
	loop.append(viewport.loop)


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


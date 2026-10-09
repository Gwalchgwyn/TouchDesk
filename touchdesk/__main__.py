import logging
import os
import sys

from touchdesk.app import main

code = main()
logging.shutdown()
sys.stdout.flush()
sys.stderr.flush()
# Skip Python's final clean-up of Qt objects: some PySide6/Python combinations
# can crash there, which would make "Exit to desktop" look like a crash and
# restart the app. Settings are always saved the moment they change.
os._exit(code)

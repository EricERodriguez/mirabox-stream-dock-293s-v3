"""Run as ``python -m editor`` with this package's parent directory as the
working directory (so the sibling ``profile_store`` module is importable).
"""

from .app import StreamDockEditor

if __name__ == "__main__":
    StreamDockEditor().run(None)

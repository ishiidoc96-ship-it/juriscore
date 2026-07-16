import importlib
import logging

logger = logging.getLogger("juriscore")

_loaded = []

for _name in [
    "auth", "cases", "statutes", "constitution", "notebook",
    "flashcards", "study", "export", "search", "bookmarks",
    "gazettes", "tribunals", "workspaces", "history",
    "student_workspace",
]:
    try:
        importlib.import_module(f".{_name}", __name__)
        _loaded.append(_name)
    except Exception as e:
        logger.warning(f"Router '{_name}' failed to load: {e}")

__all__ = _loaded

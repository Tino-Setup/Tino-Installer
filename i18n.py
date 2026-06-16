import gettext
import os
import sys

def get_base_path():
    """Returns the base path, accounting for PyInstaller frozen executable mode."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()
LOCALE_DIR = os.path.join(BASE_DIR, 'locale')


_current_translator = lambda s: s

def _(s):
    """Proxy function that always calls the currently active translator."""
    return _current_translator(s)

def set_language(lang_code):
    """Updates the active translator to the specified language."""
    global _current_translator
    lang_list = [lang_code] if lang_code else None
    try:
        new_translate = gettext.translation('tinoinstaller', LOCALE_DIR, languages=lang_list, fallback=True)
        _current_translator = new_translate.gettext
    except Exception:
        _current_translator = lambda s: s

try:
    initial_translate = gettext.translation('tinoinstaller', LOCALE_DIR, fallback=True)
    _current_translator = initial_translate.gettext
except Exception:
    _current_translator = lambda s: s

def get_available_languages(config=None):
    """
    Returns a dictionary of {code: name}.
    If config is provided, it uses the 'Language Label' from the .tino file.
    Otherwise, it fallbacks to the directory names.
    """
    if config and hasattr(config, 'localization'):
        return {code: loc.language_label for code, loc in config.localization.items()}

    langs = {}
    if os.path.exists(LOCALE_DIR):
        for item in os.listdir(LOCALE_DIR):
            item_path = os.path.join(LOCALE_DIR, item)
            mo_path = os.path.join(item_path, 'LC_MESSAGES', 'tinoinstaller.mo')
            if os.path.isdir(item_path) and os.path.exists(mo_path):
                langs[item] = item
    return langs
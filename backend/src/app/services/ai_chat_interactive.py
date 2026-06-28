import sys

from .ai import chat_interactive as _chat_interactive


sys.modules[__name__] = _chat_interactive

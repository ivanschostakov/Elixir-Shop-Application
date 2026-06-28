import sys

from .ai import chat as _chat


sys.modules[__name__] = _chat

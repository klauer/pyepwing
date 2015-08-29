from .jisx0208 import jisx0208
from .codec import register as creg


def register():
    creg()

from __future__ import print_function
import struct
import codecs
import six
import logging


from .jisx0208 import jisx0208 as jisx0208_map

logger = logging.getLogger(__name__)


class CharmapCodec(object):
    def __init__(self, decode_map, encode_map=None):
        self.decode_map = decode_map
        self.encode_map = encode_map

    def encode(self, input, errors='strict'):
        raise NotImplementedError()

    def decode(self, input, errors='strict'):
        n_char = len(input) // 2
        encoded = struct.unpack('>' + 'H' * n_char, input)
        return u''.join(self.decode_map[ch] for ch in encoded), 0


codec_info = {'jisx0208': (jisx0208_map, None),
              }


_codecs = {}


def find_codecs(encoding):
    try:
        charmap = _codecs[encoding]
    except KeyError:
        return None

    return codecs.CodecInfo(name=encoding,
                            encode=charmap.encode,
                            decode=charmap.decode,
                            )


def register():
    codecs.register(find_codecs)

    for name, (decode, encode) in codec_info.items():
        if name in _codecs:
            continue

        _codecs[name] = CharmapCodec(decode, encode)

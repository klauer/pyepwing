from __future__ import print_function
import six
import logging

from . import encodings
# from .bcd import bcd_map


logger = logging.getLogger(__name__)


if six.PY3:
    def decode(value, encoding='ascii'):
        value = bytes(value)

        try:
            value = value[:value.index(0)]
        except ValueError:
            pass

        return value.decode(encoding)

else:
    def decode(value, encoding='ascii'):
        s = ''.join(chr(c) for c in value)

        try:
            s = s[:s.index('\x00')]
        except ValueError:
            pass

        return s.decode(encoding)


class encoded_string(object):
    def __init__(self, field, strip=True, encoding=None):
        self.field = field
        self.strip = strip
        self.encoding = encoding

    def __get__(self, obj, objtype):
        if self.encoding is not None:
            encoding = self.encoding
        else:
            encoding = obj._encoding

        value = getattr(obj, self.field)
        ret = decode(value, encoding)
        if self.strip:
            return ret.strip()
        else:
            return ret


class encoded_string_array(object):
    def __init__(self, field, strip=True, encoding=None,
                 remove_empty=True):
        self.field = field
        self.strip = strip
        self.encoding = encoding
        self.remove_empty = remove_empty

    def __get__(self, obj, objtype):
        if self.encoding is not None:
            encoding = self.encoding
        else:
            encoding = obj._encoding

        values = getattr(obj, self.field)
        if self.strip:
            ret = [decode(value, encoding).strip() for value in values]
        else:
            ret = [decode(value, encoding) for value in values]

        if self.remove_empty:
            return [decoded for decoded in ret
                    if decoded]
        else:
            return ret


class uint24(object):
    def __init__(self, field):
        self._field = field

    def __get__(self, obj, objtype):
        b2, b1, b0 = getattr(obj, self._field)
        return (b2 << 16) + (b1 << 8) + b0


class bcd(object):
    def __init__(self, field):
        self._field = field

    def __get__(self, obj, objtype):
        bytes_ = getattr(obj, self._field)

        assert(len(bytes_) in (2, 4))

        # TODO: remember: big-endian

        # TODO this can be done cleaner if called a lot
        #      for now, copying the c source
        if len(bytes_) == 2:
            b0, b1 = bytes_
            value = ((b0 >> 4) & 0x0f) * 1000
            value += ((b0) & 0x0f) * 100
            value += ((b1 >> 4) & 0x0f) * 10
            value += ((b1) & 0x0f)
        else:
            b0, b1, b2, b3 = bytes_
            value = ((b0 >> 4) & 0x0f) * 10000000
            value += ((b0) & 0x0f) * 1000000
            value += ((b1 >> 4) & 0x0f) * 100000
            value += ((b1) & 0x0f) * 10000
            value += ((b2 >> 4) & 0x0f) * 1000
            value += ((b2) & 0x0f) * 100
            value += ((b3 >> 4) & 0x0f) * 10
            value += ((b3) & 0x0f)

        return value


encodings.register()

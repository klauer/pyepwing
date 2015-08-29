from __future__ import print_function
import ctypes

from .const import SECTION_CODE


class TextStruct(ctypes.BigEndianStructure):
    _pack_ = 1
    _size_on_disk_ = 2
    _extra_args_ = None
    _info_keys_ = None

    _fields_ = [('code1', ctypes.c_ubyte),
                ('code2', ctypes.c_ubyte),
                ]

    @property
    def _args(self):
        cls = self.__class__
        if not hasattr(cls, '__args__'):
            argi = 1
            try:
                while getattr(cls, 'arg{}'.format(argi)):
                    argi += 1
            except AttributeError:
                pass

            cls.__args__ = ['arg{}'.format(i) for i in range(1, argi)]
            if self._extra_args_:
                cls.__args__.extend(self._extra_args_)

        ret = [(self.code1, self.code2)]
        return ret + [getattr(self, arg) for arg in self.__args__]

    @property
    def info(self):
        if not self._info_keys_:
            return {}

        return {key: getattr(self, key)
                for key in self._info_keys_
                }

    def is_section(self):
        return (self.code1 == SECTION_CODE)

from __future__ import print_function
import ctypes
import logging
import six

from collections import OrderedDict

from .descriptors import (encoded_string, encoded_string_array, uint24)

logger = logging.getLogger(__name__)


EB_MAX_DIRECTORY_NAME_LENGTH = 8
EB_MAX_FONTS = 4
EB_MAX_EPWING_TITLE_LENGTH = 80
# EB_MAX_ALTERNATION_CACHE = 16
# EB_MAX_ALTERNATION_TEXT_LENGTH = 31
# EB_MAX_CROSS_ENTRIES = 5
# EB_MAX_EB_TITLE_LENGTH = 30
# EB_MAX_FILE_NAME_LENGTH = 14
# EB_MAX_KEYWORDS = 5
# EB_MAX_MULTI_ENTRIES = 5
# EB_MAX_MULTI_LABEL_LENGTH = 30
# EB_MAX_MULTI_SEARCHES = 10
# EB_MAX_MULTI_TITLE_LENGTH = 32
# EB_MAX_PATH_LENGTH = 1024
# EB_MAX_SUBBOOKS = 50
# EB_MAX_TITLE_LENGTH = 80
# EB_MAX_WORD_LENGTH = 255


c_directory = ctypes.c_ubyte * EB_MAX_DIRECTORY_NAME_LENGTH


def _pad_structure(st):
    struct_size = ctypes.sizeof(st)
    pad_amount = st._size_on_disk_ - struct_size

    logger.debug('{} pad_amount {}'.format(st, pad_amount))
    assert pad_amount >= 0, 'Struct size incorrect?'

    if pad_amount > 0:
        class Padded(st):
            _pack_ = 1
            _fields_ = [('__padding__', ctypes.c_ubyte * pad_amount)]

        ret = Padded
        ret.__name__ = st.__name__[1:]
    else:
        ret = st

    return ret


class _EbCatalogHeader(ctypes.BigEndianStructure):
    _pack_ = 1
    _size_on_disk_ = 16

    _fields_ = [('subbook_count', ctypes.c_ushort),
                ]


EbCatalogHeader = _pad_structure(_EbCatalogHeader)


class _EpwingCatalogHeader(ctypes.BigEndianStructure):
    _pack_ = 1
    _size_on_disk_ = 16

    _fields_ = [('subbook_count', ctypes.c_ushort),
                ('epwing_version', ctypes.c_ushort),
                ('_unknown0', ctypes.c_ubyte * 12),
                ]


EpwingCatalogHeader = _pad_structure(_EpwingCatalogHeader)


class _StructWithStrings(ctypes.BigEndianStructure):
    def set_default_encoding(self, encoding):
        self._encoding = encoding

    def __str__(self):
        kv_pairs = ('{}={!r}'.format(k, v)
                    for k, v in six.iteritems(self.info_dict))
        return '{.__class__.__name__}({})'.format(self, ', '.join(kv_pairs))


class _EpwingCatalog(_StructWithStrings, ctypes.BigEndianStructure):
    _pack_ = 1
    _size_on_disk_ = 164
    book_type = 'epwing'

    header_class = EpwingCatalogHeader

    _fields_ = [('head', ctypes.c_ushort),
                ('_title', ctypes.c_ubyte * EB_MAX_EPWING_TITLE_LENGTH),
                ('_directory', c_directory),
                ('_filler0', ctypes.c_ubyte * 4),
                ('index_page', ctypes.c_ushort),
                ('_filler1', ctypes.c_ubyte * 4),
                ('_wide_fonts', (c_directory * EB_MAX_FONTS)),
                ('_narrow_fonts', (c_directory * EB_MAX_FONTS)),
                ]

    title = encoded_string('_title')
    directory = encoded_string('_directory', encoding='latin-1')
    narrow_fonts = encoded_string_array('_narrow_fonts', encoding='latin-1')
    wide_fonts = encoded_string_array('_wide_fonts', encoding='latin-1')

    @property
    def info_dict(self):
        return OrderedDict([('title', self.title),
                            ('directory', self.directory),
                            ('index_page', self.index_page),
                            ('narrow_fonts', self.narrow_fonts),
                            ('wide_fonts', self.wide_fonts),
                            ])

EpwingCatalog = _pad_structure(_EpwingCatalog)


class _EbCatalog(_StructWithStrings, ctypes.BigEndianStructure):
    _pack_ = 1
    _size_on_disk_ = 164
    book_type = 'eb'

    header_class = EpwingCatalogHeader

    _fields_ = []

    @property
    def info_dict(self):
        raise NotImplementedError()


EbCatalog = _pad_structure(_EbCatalog)


class _EpwingSubbookResource(_StructWithStrings, ctypes.BigEndianStructure):
    _pack_ = 1
    _size_on_disk_ = 164

    header_class = EpwingCatalogHeader

    _fields_ = [('header', ctypes.c_ubyte * 3),
                ('_valid', ctypes.c_ubyte),
                ('_text_filename', c_directory),
                ('_unknown0', ctypes.c_ubyte * 29),
                ('_resource_types', ctypes.c_ubyte * 2),
                ('_unknown1', ctypes.c_ubyte),
                ('_resource_path2', c_directory),
                ('_unknown2', ctypes.c_ubyte),
                ('_zio_codes', ctypes.c_ubyte * 3),
                ('_resource_path1', c_directory),
                ]

    @property
    def is_valid(self):
        code = self.zio_types[2]
        return (self._valid != 0) and (code is not None)

    def _get_resource_type(self, value):
        value = (value & 3)
        if value == 1:
            return 'sound'
        elif value == 2:
            return 'graphic'

    @property
    def resource_types(self):
        return [self._get_resource_type(value)
                for value in self._resource_types]

    @property
    def zio_types(self):
        info = {0x00: 'plain',
                0x11: 'epwing',
                0x12: 'epwing6',
                }
        return [info.get(code, None)
                for code in self._zio_codes]

    text_filename = encoded_string('_text_filename', encoding='latin-1')
    resource_path1 = encoded_string('_resource_path1', encoding='latin-1')
    resource_path2 = encoded_string('_resource_path2', encoding='latin-1')

    @property
    def resource_paths(self):
        return [self.resource_path1,
                self.resource_path2]

    @property
    def resources(self):
        ret = list(zip(self.resource_types,
                       self.resource_paths,
                       self.zio_types,
                       ))

        return [(type_, path, zio_type)
                for type_, path, zio_type in ret
                if type_ is not None]

    @property
    def info_dict(self):
        return OrderedDict([('is_valid', self.is_valid),
                            ('text_filename', self.text_filename),
                            ('resource_path1', self.resource_path1),
                            ('resource_path2', self.resource_path2),
                            ('zio_types', self.zio_types),
                            ('resource_types', self.resource_types),
                            ])


EpwingSubbookResource = _pad_structure(_EpwingSubbookResource)


class SubbookSearchIndex(ctypes.BigEndianStructure):
    _pack_ = 1
    _size_on_disk_ = 16

    _fields_ = [('index_id', ctypes.c_ubyte),
                ('_unknown0', ctypes.c_ubyte),
                ('start_page', ctypes.c_uint),
                ('_end_page', ctypes.c_uint),
                ('availability', ctypes.c_ubyte),
                ('_flags', ctypes.c_ubyte * 3),
                ('_unknown1', ctypes.c_ubyte * 2),
                ]

    flags = uint24('_flags')

    @property
    def end_page(self):
        return self.start_page + self._end_page - 1


class _SubbookIndices(ctypes.BigEndianStructure):
    _pack_ = 1
    _max_indices = int(2048 / 16) - 1
    _size_on_disk_ = (_max_indices + 1) * 16

    _fields_ = [('_header', ctypes.c_ubyte),
                ('index_count', ctypes.c_ubyte),
                ('_unknown0', ctypes.c_ubyte * 2),
                ('global_availability', ctypes.c_ubyte),
                ('_unknown1', ctypes.c_ubyte * 11),

                # up to 256 search methods, limited by index count
                ('search_methods', SubbookSearchIndex * _max_indices),
                ]


SubbookIndices = _pad_structure(_SubbookIndices)

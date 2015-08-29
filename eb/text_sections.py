# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
import logging
import six
import ctypes

from .text_structs import TextStruct
from .descriptors import bcd
from .const import SECTION_CODE

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)


class TextStop(Exception):
    pass


class TextSoftStop(TextStop):
    pass


class TextHardStop(TextStop):
    pass


class Skip(Exception):
    pass


class StepBytes(Exception):
    def __init__(self, bytes):
        self.bytes = bytes


class PageOffsetStruct(TextStruct):
    _pack_ = 1
    _size_on_disk_ = 8
    _info_keys_ = ('page', 'offset', 'is_leaf')

    _fields_ = [('_page', ctypes.c_ubyte * 4),
                ('_offset', ctypes.c_ubyte * 2),
                ]

    page = bcd('_page')
    offset = bcd('_offset')

    @property
    def is_leaf(self):
        return self.page == 0 and self.offset == 0


class Section(object):
    tag = None

    def __init__(self, name, data=None, handler=None, **info):
        self.name = name
        self.info = info
        self.data = data

        if handler is not None:
            self.handler = handler()
        else:
            self.handler = None

    def _get_struct(self):
        pass

    def __str__(self):
        items = list(self.info.items())
        if self.data is not None:
            items.append(('data', self.data))

        info = ', '.join('{}={}'.format(k, v) for k, v in items)

        if info:
            return '{}({!r}, {})'.format(self.__class__.__name__,
                                         self.name, info)
        else:
            return '{}({!r})'.format(self.__class__.__name__, self.name)

    __repr__ = __str__

    def with_data(self, data):
        return Section(self.name, data=data, **self.info)

    def as_data_dict(self, data):
        dict_ = {'name': self.name, 'data': data}
        dict_.update(self.info)
        return dict_

    def pprint(self, first_indent=False, indent=0, f=sys.stdout):
        if first_indent:
            print(' ' * (4 * indent), end='', file=f)

        indent += 1
        indent_str = ' ' * (4 * indent)

        if self.data:
            print(u'{0.__class__.__name__}({0.name!r}, info={0.info}, '
                  u'data=['.format(self), file=f)
            for item in self.data:
                if hasattr(item, 'pprint'):
                    item.pprint(indent=indent, first_indent=True, f=f)
                else:
                    print(indent_str, end='', file=f)
                    if isinstance(item, six.string_types):
                        print(u'"{}"'.format(item.strip()), file=f)
                    else:
                        print(u'{!r}'.format(item), file=f)
            print(indent_str + '])', file=f)

        else:
            print(u'{}'.format(self), file=f)


class SectionStart(Section):
    tag = 'start'


class SectionEnd(Section):
    tag = 'end'


class TextDirective(object):
    def __init__(self, name, handler=None, **info):
        self.name = name
        self.info = info
        if handler is not None:
            self.handler = handler()
        else:
            self.handler = None

    def as_data_dict(self, data):
        dict_ = {'name': self.name, 'data': data}
        dict_.update(self.info)
        return dict_

    def __str__(self):
        return '{}({!r})'.format(self.__class__.__name__,
                                 self.name)

    __repr__ = __str__


class SectionHandler(object):
    start_struct = None
    end_struct = None
    start_skip = 0
    end_skip = 0

    def start(self, context, **kwargs):
        pass

    def end(self, context, **kwargs):
        pass


class DirectiveHandler(object):
    struct = None
    key = None
    skip_bytes = 0

    def start(self, context, **kwargs):
        pass

    def __str__(self):
        return '{}(key={})'.format(self.__class__.__name__, self.key)


class SkipCode(DirectiveHandler):
    name = 'skip_code'

    def __init__(self, skip_code):
        if skip_code == 0x14:
            self.key = 0x15
        elif skip_code >= 0xe4 and skip_code <= 0xfe:
            self.key = 0x01 + skip_code
        else:
            self.key = 0x20 + skip_code

        # TODO fix how this works
        self.handler = self

    def start(self, context):
        pass


sections = {0x02: SectionStart('text'),
            0x03: SectionEnd('text'),
            0x04: SectionStart('narrow'),
            0x05: SectionEnd('narrow'),
            0x06: SectionStart('subscript'),
            0x07: SectionEnd('subscript'),
            0x09: TextDirective('set_indent'),
            0x0a: TextDirective('newline',
                                context=dict(text_status='soft_stop')),
            0x0b: SectionStart('unicode'),
            0x0c: SectionEnd('unicode'),
            0x0e: SectionStart('superscript'),
            0x0f: SectionEnd('superscript'),
            0x10: SectionStart('no_newline'),
            0x11: SectionEnd('no_newline'),
            0x12: SectionStart('emphasis'),
            0x13: SectionEnd('emphasis'),

            0x1a: TextDirective('emphasis'),
            0x1b: TextDirective('emphasis'),
            0x1e: TextDirective('emphasis'),
            0x1f: TextDirective('emphasis'),

            0x1c: SectionStart('gaiji'),
            0x1d: SectionEnd('gaiji'),

            0x32: SectionStart('mono_graphic_ref'),
            0x39: SectionStart('mpeg'),
            0x3c: SectionStart('inline_graphic'),

            0x41: SectionStart('keyword'),
            0x42: SectionStart('reference'),

            0x43: SectionStart('candidate'),
            0x44: SectionStart('mono_graphic'),
            0x45: SectionStart('graphic_block'),
            0x4a: SectionStart('wave_sound'),
            0x4b: SectionStart('paged_reference'),
            0x4c: SectionStart('image_page'),
            0x4d: SectionStart('graphic'),
            0x4f: SectionStart('clickable'),

            0x52: SectionEnd('mono_graphic_ref'),
            0x53: SectionEnd('eb_sound'),
            0x59: SectionEnd('mpeg'),
            0x5c: SectionEnd('inline_graphic'),
            0x61: SectionEnd('keyword'),
            0x62: SectionEnd('reference'),
            0x63: SectionEnd('candidate'),

            0x64: SectionEnd('mono_graphic'),
            0x6a: SectionEnd('wave_sound'),
            0x6b: SectionEnd('paged_reference'),
            0x6c: SectionEnd('image_page'),
            0x6d: SectionEnd('graphic'),
            0x6f: SectionEnd('clickable'),

            0xe0: SectionStart('decoration'),
            0xe1: SectionEnd('decoration'),
            }


skip_codes = [0x14,
              0x35, 0x36, 0x37, 0x38, 0x3a, 0x3b, 0x3d, 0x3e, 0x3f,

              0x49, 0x4e,

              0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7a,
              0x7b, 0x7c, 0x7d, 0x7e, 0x7f, 0x80, 0x81, 0x82, 0x83, 0x84, 0x85,
              0x86, 0x87, 0x88, 0x89, 0x8a, 0x8b, 0x8c, 0x8d, 0x8e, 0x8f,

              0xe4, 0xe6, 0xe8, 0xea, 0xec, 0xee,
              0xf0, 0xf2, 0xf4, 0xf6, 0xf8, 0xfa,
              0xfc, 0xfe,
              ]


# skip codes mean hooks aren't called until skip code is reset
for skip_code in skip_codes:
    sections[skip_code] = SkipCode(skip_code)


handlers = {}


def _get_section_name_dict():
    def _name_key(section):
        if isinstance(section, SectionEnd):
            return ('end', section.name)

        return ('start', section.name)

    return {_name_key(section): code
            for code, section in sections.items()}


def register_handler(key, replace=False):
    def _reg(cls):
        if key in handlers and not replace:
            raise KeyError('Cannot have multiple handlers')

        logger.debug('Registered text handler %s for key %s',
                     cls.__name__, key)

        if issubclass(cls, SectionEnd):
            name_key = ('end', key)
        else:
            name_key = ('start', key)

        try:
            code = _get_section_name_dict()[name_key]
        except KeyError:
            logger.warning('Section code not found for handler: %s[%s]' %
                           name_key)
        else:
            if issubclass(cls, SectionEnd):
                cls.end_code = code
            else:
                cls.start_code = code

        handlers[key] = cls()
        cls.key = key
        return cls

    return _reg


@register_handler('text')
class TextSection(SectionHandler):
    def end(self, context):
        context.seek_cur(-2)
        raise TextHardStop('End of text section')


@register_handler('set_indent')
class SetIndentHandler(DirectiveHandler):
    class struct(TextStruct):
        _pack_ = 1
        _size_on_disk_ = 2 + 2
        _info_keys_ = ('indent', )
        _fields_ = [('indent', ctypes.c_ushort)]

    def start(self, context, indent=None):
        subbook = context.subbook
        if subbook.appendix is None or subbook.stop_code is None:
            print('stop code'
            print('check auto stop code')
            if context.auto_stop_code[0] == self.start_code:
                raise TextSoftStop('Auto stop code match')
            # if (no appendix, or no appendix stop code)
            #    result = (this is keyword beginning AND
            #              next is auto_stop_code)
            # else
            #    (this is stop code0, next is stop code1)

@register_handler('emphasis')
class EmphasisDirective(DirectiveHandler):
    # described in JIS X 4081-1996
    def start(self, context):
        return context.check_next_eb()


@register_handler('gaiji')
class GaijiSection(SectionHandler):
    def start(self, context):
        if context.book.encoding == 'jisx0208-gb2312':
            context['ebxac_gaiji'] = True
        else:
            return context.check_next_eb()

    def end(self, context):
        if context.book.encoding == 'jisx0208-gb2312':
            context['ebxac_gaiji'] = True
        else:
            return context.check_next_eb()


@register_handler('mono_graphic')
class MonoGraphicSection(SectionHandler):
    class start_struct(TextStruct):
        _pack_ = 1
        _size_on_disk_ = 12
        _info_keys_ = ('width', 'height')

        # fields listed unknown are actually unknown according to the eb docs
        _fields_ = [('_unknown', ctypes.c_ushort),
                    ('_width', ctypes.c_ubyte * 4),
                    ('_height', ctypes.c_ubyte * 4),
                    ]

        width = bcd('_width')
        height = bcd('_height')

    end_struct = PageOffsetStruct

    def start(self, context, width=None, height=None):
        if 0 in (width, height):
            raise Skip()

    def end(self, context, page=None, offset=None, is_leaf=None):
        pass


@register_handler('mono_graphic_ref')
class MonoGraphicRefSection(SectionHandler):
    key = 'mono_graphic_ref'
    start_struct = None
    end_struct = PageOffsetStruct


@register_handler('mpeg')
class MPEGSection(SectionHandler):
    class start_struct(TextStruct):
        _pack_ = 1
        _size_on_disk_ = 46

        _fields_ = [('_unknown0', ctypes.c_uint),        # 02:06 (arg1)
                    ('_unknown1', ctypes.c_ubyte * 16),  # 06:22
                    ('arg2', ctypes.c_uint),             # 22:
                    ('arg3', ctypes.c_uint),             # 26:
                    ('arg4', ctypes.c_uint),             # 30:
                    ('arg5', ctypes.c_uint),             # 34:38
                    ('_unknown2', ctypes.c_ubyte * 8),   # 38:46
                    ]

        # TODO i think the movie filename comes from &arg2 to
        #      &arg2 + EB_MAX_DIRECTORY_NAME_LENGTH, encoded in jisx0208
        # docs:
        # フック EB_HOOK_BEGIN_WAVE が、フック関数に渡す argc は 6 です。 argv[0]
        # はエスケープシーケンスのコードそのもので、 0x1f4a になります。
        # argv[2] と argv[3] は音声データの開始位置の
        # ページ番号と��フセット、argv[4] と argv[5] は
        # 終了位置のページ番号とオフセットをそれぞれ表します。 argv[1]
        # の意味は不明です。
    end_struct = None


@register_handler('keyword')
class KeywordSection(SectionHandler):
    class start_struct(TextStruct):
        _pack_ = 1
        _size_on_disk_ = 4
        _info_keys_ = ('auto_stop_code', )
        _fields_ = [('auto_stop_code', ctypes.c_ubyte * 2),
                    ]

    end_struct = None

    def start(self, context, auto_stop_code=None):
        if context.printable_count > 0 and context.is_main_text:
            if context.check_stop_code():
                raise TextSoftStop('Main text stop code match; hit keyword')

        if context.auto_stop_code is None:
            print('set auto stop code', tuple(auto_stop_code))
            context.auto_stop_code = tuple(auto_stop_code)


@register_handler('reference')
class ReferenceSection(SectionHandler):
    class start_struct(TextStruct):
        _pack_ = 1
        _size_on_disk_ = 4
        _info_keys_ = ('arg_check', )

        _fields_ = [('arg_check', ctypes.c_ubyte),
                    ('unknown', ctypes.c_ubyte),
                    ]

    end_struct = PageOffsetStruct

    def start(self, context, arg_check=None):
        if arg_check != 0:
            # next byte isn't part of the structure...
            context.seek_cur(-2)


@register_handler('candidate')
class CandidateSection(SectionHandler):
    start_struct = None
    end_struct = PageOffsetStruct


@register_handler('graphic_block')
class GraphicBlockSection(SectionHandler):
    class start_struct(TextStruct):
        _pack_ = 1
        _size_on_disk_ = 4
        _info_keys_ = ('arg_check', 'arg1')

        _fields_ = [('_arg1', ctypes.c_ubyte * 2),
                    ]

        arg1 = bcd('_arg1')

        def arg_check(self):
            return (self._arg1[0] != SECTION_CODE)

    end_struct = None

    def start(self, context, arg_check=None):
        # TODO: bug in source? bcd4 with in_step=2
        if arg_check is not None and not arg_check:
            context.seek_cur(-2)


@register_handler('wave_sound')
class WaveSoundSection(SectionHandler):
    class start_struct(TextStruct):
        _pack_ = 1
        _size_on_disk_ = 18
        _info_keys_ = ('start_page', 'start_offset',
                       'end_page', 'end_offset')

        _fields_ = [('arg1', ctypes.c_uint),
                    ('_start_page', ctypes.c_ubyte * 4),
                    ('_start_offset', ctypes.c_ubyte * 2),
                    ('_end_page', ctypes.c_ubyte * 4),
                    ('_end_offset', ctypes.c_ubyte * 2),
                    ]

        start_page = bcd('_start_page')
        start_offset = bcd('_start_offset')
        end_page = bcd('_end_page')
        end_offset = bcd('_end_offset')

    end_struct = None


@register_handler('paged_reference')
class PagedReferenceSection(SectionHandler):
    start_struct = PageOffsetStruct
    end_struct = None

    def start(self, context, page=None, offset=None, is_leaf=None):
        if context.next_code == (SECTION_CODE, self.end_code):
            context.seek_cur(-2)
            raise TextSoftStop('Paged reference section start')


@register_handler('image_page')
class ImagePageSection(SectionHandler):
    start_skip = 2


@register_handler('graphic')
class GraphicSection(SectionHandler):
    class start_struct(TextStruct):
        _pack_ = 1
        _size_on_disk_ = 20
        _info_keys_ = ('page', 'offset', 'image_type')

        # NOTE: docs on this structure versus code seem to differ
        _fields_ = [('_type_info', ctypes.c_ushort),
                    ('_unknown', ctypes.c_ubyte * 10),
                    ('_page', ctypes.c_ubyte * 4),
                    ('_offset', ctypes.c_ubyte * 2),
                    ]

        page = bcd('_page')
        offset = bcd('_offset')

        @property
        def image_type(self):
            if (self._type_info >> 8) == 0:
                return 'bmp'
            else:
                return 'jpeg'


@register_handler('inline_graphic')
class InlineGraphicSection(SectionHandler):
    start_struct = GraphicSection.start_struct
    end_struct = None


@register_handler('clickable')
class ClickableSection(SectionHandler):
    class start_struct(TextStruct):
        _pack_ = 1
        _size_on_disk_ = 34

        _fields_ = [('_unknown0', ctypes.c_ubyte * 6),   # 2:8
                    ('_x', ctypes.c_ubyte * 2),       # 8:10
                    ('_y', ctypes.c_ubyte * 2),       # 10:12
                    ('_width', ctypes.c_ubyte * 2),       # 12:14
                    ('_height', ctypes.c_ubyte * 2),       # 14:16
                    ('_unknown1', ctypes.c_ubyte * 12),  # 16:28
                    ('_page', ctypes.c_ubyte * 4),       # 28:32
                    ('_offset', ctypes.c_ubyte * 2),       # 32:34
                    ]

        x = bcd('_x')
        y = bcd('_y')
        width = bcd('_width')
        height = bcd('_height')
        page = bcd('_page')
        offset = bcd('_offset')


@register_handler('eb_sound')
class EBSoundSection(SectionHandler):
    start_skip = 8


@register_handler('decoration')
class EBDecoration(SectionHandler):
    class start_struct(TextStruct):
        _pack_ = 1
        _size_on_disk_ = 4
        _info_keys_ = ('decoration_type', )

        _fields_ = [('decoration_code', ctypes.c_ushort),
                    ]

        @property
        def decoration_type(self):
            return {1: 'italic',
                    3: 'bold',
                    }.get(self.decoration_code, 'unknown')

    def start(self, context, decoration_type=None):
        byte = context.get_byte(2)
        if not context.book.is_epwing and byte >= SECTION_CODE:
            context.seek_cur(-2)


def update_handlers():
    for key, obj in sections.items():
        try:
            handler = handlers[obj.name]
        except KeyError:
            logger.debug('No handler for %s', obj)
            obj.handler = None
        else:
            logger.debug('Set handler for %s', obj)
            obj.handler = handler


def _check_handlers():
    import ctypes
    update_handlers()

    for key, obj in sections.items():
        name = obj.name
        handler = obj.handler

        if handler is not None:
            logger.debug('Checking handler %s', handler.__class__.__name__)
            if isinstance(handler, SectionHandler):
                structs = [handler.start_struct, handler.end_struct]
            elif isinstance(handler, DirectiveHandler):
                structs = [handler.struct]
            else:
                raise ValueError('Invalid handler superclass?')

            for struct_ in structs:
                if struct_ is not None:
                    assert ctypes.sizeof(struct_) == struct_._size_on_disk_, \
                        'Size check failed for {}'.format(struct_)
        else:
            if name not in ('skip_code', ):
                logger.debug('No handler for %r', name)


if __name__ == '__main__':
    _check_handlers()
else:
    update_handlers()

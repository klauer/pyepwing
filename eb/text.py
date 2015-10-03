from __future__ import print_function
import logging
import pprint
import time

import six

from . import (structs, zio)
from . import text_sections as tsec
from .string_util import to_narrow
from .text_sections import SECTION_CODE


logger = logging.getLogger(__name__)


class TextContext(object):
    def __init__(self, text, **info):
        self.text = text
        self.subbook = text._subbook
        self.book = self.subbook.book
        self.encoding = self.book.encoding

        self.sections = []
        self.printable_count = 0
        self.skip_code = None
        self.auto_stop_code = None
        self.info = {}
        self._struct_cache = {}
        self._keyword_count = 0

        # TODO: text context main/optional; readtext.c:1800
        self.is_main_text = True

    def __getitem__(self, key):
        return self.info[key]

    def __setitem__(self, key, value):
        self.info[key] = value

    @property
    def last_section(self):
        try:
            return self.sections[-1]
        except IndexError:
            return None

    @property
    def section_names(self):
        return [section['name'] for section in self.sections]

    def seek_cur(self, nbytes):
        self.zio.seek_cur(nbytes)

    def get_byte(self, offset):
        '''offset in relation to start of current structure,

        so get_byte(0) would be 'code1'
        '''
        raise NotImplementedError()

    def _code_from_ushort(self, ushort):
        c1 = (ushort & 0xff00) >> 8
        c2 = ushort & 0xff
        return (c1, c2)

    def check_stop_code(self, code):
        appendix = self.subbook.appendix
        cur_code = self.header.code2
        if appendix is None or appendix.stop_code is None:
            is_section = self.header.is_section
            return ((is_section and cur_code == tsec.KeywordSection.start_code)
                    and (code == self.auto_stop_code))

        return (((self.header.code1, self.header.code2), code) ==
                appendix.stop_code)

    @property
    def next_is_code(self):
        # next 2 bytes are >= 0x1f00:
        raise NotImplementedError()

    def next_code(self):
        raise NotImplementedError()

    def check_next_eb(self):
        if not self.book.is_epwing:
            if self.next_is_code:
                return

        self.seek_cur(4)


class SubbookText(object):
    # Size of a page in bytes (page = block in JIS X 4081)
    _page_size = 2048

    _index_style_convert = 0
    _index_style_asis = 1
    _index_style_reversed_convert = 2
    _index_style_delete = 2

    _search_types = {0x00: 'text',
                     0x01: 'menu',
                     0x02: 'copyright',
                     0x10: 'image_menu',
                     0x70: 'endword_kana',
                     0x71: 'endword_asis',
                     0x72: 'endword_alphabet',
                     0x80: 'keyword',
                     0x81: 'cross',
                     0x90: 'word_kana',
                     0x91: 'word_asis',
                     0x92: 'word_alphabet',
                     0xd8: 'sound',

                     # number is counted
                     0xff: 'multi',

                     # eb only, plain mode
                     0x21: ('eb', 'sebxa_zip', 'text'),
                     0x22: ('eb', 'sebxa_zip', 'index'),
                     0xf1: ('eb', 'wide_font', 0),
                     0xf2: ('eb', 'narrow_font', 0),
                     0xf3: ('eb', 'wide_font', 1),
                     0xf4: ('eb', 'narrow_font', 1),
                     0xf5: ('eb', 'wide_font', 2),
                     0xf6: ('eb', 'narrow_font', 2),
                     0xf7: ('eb', 'wide_font', 3),
                     0xf8: ('eb', 'narrow_font', 3),

                     # epwing-only
                     0x16: ('epwing', 'search_title_page', None),

                     }

    def __init__(self, subbook, path, filename):
        self._subbook = subbook
        self._path = path
        self._filename = filename
        self._index_page = self._subbook._index_page

        self._zio = zio.open_zio_file(self._path, self._filename)
        self._sebxa_settings = {}
        self._load_indices()

    def _seek_index(self):
        self._seek_page(self._index_page)

    def _seek_page(self, page, offset=0):
        seek_pos = (page - 1) * self._page_size + offset
        logger.debug('Seeking page %d offset %d (pos=%d)', page, offset,
                     seek_pos)
        self._zio.seek_start(seek_pos)

    def _seek_search_page(self, search_key, page_offset=0, offset=0):
        method = self._subbook._searches[search_key]

        logger.debug('Seeking start page of search %s (offset page=%d byte '
                     'offset=%d)', search_key, page_offset, offset)
        self._seek_page(method['start_page'] + page_offset,
                        offset=offset)

    def _load_indices(self):
        self._zio.open()
        self._seek_index()

        indices = structs.SubbookIndices()
        if indices.index_count >= (int(self._page_size / 16) - 1):
            logger.debug('Unexpected text where index should be')
            return

        self.indices = indices
        self._zio.readinto(indices)
        logger.debug('index count %x', indices.index_count)

        if indices.global_availability > 2:
            logger.debug('(global availability was %x)',
                         indices.global_availability)
            indices.global_availability = 0

        glob = indices.global_availability
        logger.debug('global availability %x', glob)

        self._subbook._reset_searches()
        methods = indices.search_methods[:indices.index_count]

        for i, method in enumerate(methods):
            logger.debug('Search method %d id %d', i, method.index_id)
            logger.debug('- start page %d', method.start_page)
            logger.debug('- end page %d', method.end_page)
            logger.debug('- flags %x' % method.flags)
            logger.debug('- availability %x', method.availability)

            assert(method.start_page <= method.end_page)

            search = {'start_page': method.start_page,
                      'end_page': method.end_page,
                      }

            if ((glob == 0 and method.availability == 2) or (glob == 2)):
                search['katakana'] = (method.flags & 0xc00000) >> 22
                search['lower'] = (method.flags & 0x300000) >> 20
                if ((method.flags & 0x0c0000) >> 18 == 0):
                    search['mark'] = self._index_style_delete
                else:
                    search['mark'] = self._index_style_asis

                search['long_vowel'] = (method.flags & 0x030000) >> 16
                search['double_consonant'] = (method.flags & 0x00c000) >> 14
                search['contracted_sound'] = (method.flags & 0x003000) >> 12
                search['small_vowel'] = (method.flags & 0x000c00) >> 10
                search['voiced_consonant'] = (method.flags & 0x000300) >> 8
                search['p_sound'] = (method.flags & 0x0000c0) >> 6
            elif method.index_id == 0x70 or search.index_id == 0x90:
                search['katakana'] = self._index_style_convert
                search['lower'] = self._index_style_convert
                search['mark'] = self._index_style_delete
                search['long_vowel'] = self._index_style_convert
                search['double_consonant'] = self._index_style_convert
                search['contracted_sound'] = self._index_style_convert
                search['small_vowel'] = self._index_style_convert
                search['voiced_consonant'] = self._index_style_convert
                search['p_sound'] = self._index_style_convert
            else:
                search['katakana'] = self._index_style_asis
                search['lower'] = self._index_style_convert
                search['mark'] = self._index_style_asis
                search['long_vowel'] = self._index_style_asis
                search['double_consonant'] = self._index_style_asis
                search['contracted_sound'] = self._index_style_asis
                search['small_vowel'] = self._index_style_asis
                search['voiced_consonant'] = self._index_style_asis
                search['p_sound'] = self._index_style_asis

            if self.encoding == 'iso8859-1' or method.index_id in (0x72, 0x92):
                search['space'] = self._index_style_asis
            else:
                search['space'] = self._index_style_delete

            try:
                search_type = self._search_types[method.index_id]
            except KeyError:
                logger.debug('Unknown search type %d', method.index_id)
            else:
                self._subbook._set_search(search_type, search)

            logger.debug('Search method %s', search)

    @property
    def book(self):
        return self._subbook._book

    @property
    def encoding(self):
        return self.book.encoding

    @property
    def is_zio_plain(self):
        return issubclass(self._zio.__class__, zio.ZioPlainFile)

    def _sebxa_init(self, index_loc=None, index_base=None):
        # zio_start = self._zio.first_page
        # zio_end = self._zio.last_page
        raise NotImplementedError('sebxa mode')

    def _set_sebxa(self, key, start_page=None, end_page=None, **kwargs):
        if not (self.book.is_eb and self.is_zio_plain):
            logger.debug('Sebxa settings in unsupported book?')
            return

        settings = self._sebxa_settings
        if key == 'index':
            settings['index_loc'] = start_page
        elif key == 'text':
            settings['index_base'] = start_page
        else:
            raise ValueError('Unknown sebxa key: {}'.format(key))

        if 'index_base' in settings and 'index_loc' in settings:
            self._sebxa_reinit(**settings)

    def _read_character(self, context, header):
        if context['encoding'] == 'iso8859-1':
            # The book is mainly written in ISO 8859 1.
            if ((0x20 <= header.code1 < 0x7f) or
                    (0xa0 <= header.code1 <= 0xff)):
                self._zio.seek_cur(-1)
                if context.skip_code is None:
                    return chr(header.code1)
            else:
                # Narrow
                if context.skip_code is None:
                    return chr(header.code1)
        else:
            # The book is written in JIS X 0208 or JIS X 0208 + GB 2312.
            if context.skip_code is not None:
                return

            bytes_ = header.code_bytes

            if (0x20 < header.code1 < 0x7f) and (0x20 < header.code2 < 0x7f):
                return bytes_.decode('jisx0208')

            elif (0x20 < header.code1 < 0x7f) and (0xa0 < header.code2 < 0xff):
                # TODO maybe necessary to take (code1 | 0x80)
                # bytes_ = bytes([0x80 | header.code1, header.code2])
                # bytes_ = bytearray(bytes_)
                # bytes_[0] |= 0x80
                return bytes_.decode('gb2312')
                return '<gb2312?>'

            elif (0xa0 < header.code1 < 0xff) and (0x20 < header.code2 < 0x7f):
                # TODO check for latest section name
                # local character
                # 'local character' = stored in file somehow? see narwalt.c
                if 'narrow' in context.section_names:
                    # print('(TODO local character, wide)')
                    return '<local_narrow?>'
                    return bytes_.decode('latin-1')
                else:
                    # print('(TODO local character, wide)')
                    return '<local_wide?>'

    def _read_section(self, context, section):
        f = self._zio

        last_section = context.last_section
        handler = section.handler

        def get_struct_instance(cls):
            if cls is None:
                return None

            try:
                return context._struct_cache[cls]
            except KeyError:
                context._struct_cache[cls] = inst = cls()
                return inst

        if isinstance(section, tsec.SectionStart):
            cur_item = section.as_data_dict([])
            if cur_item['name'] in ('narrow', ) and context.convert_narrow:
                return

            cur_item['_started_'] = True

            if last_section is not None:
                last_section['data'].append(cur_item)
            context.sections.append(cur_item)

            if handler is None:
                return

            info = {'function': handler.start,
                    'struct': get_struct_instance(handler.start_struct),
                    'skip_bytes': handler.start_skip,
                    }

        elif isinstance(section, tsec.SectionEnd):
            if section.name in ('narrow', ) and context.convert_narrow:
                return

            assert (last_section is not None and
                    last_section['name'] == section.name), \
                   ('Mismatched start/end section '
                    '({!r}/{!r})'.format(last_section, section.name))

            # remove the last, finished section from the stack
            cur_item = context.sections.pop(-1)
            del cur_item['_started_']

            if handler is None:
                return cur_item

            info = {'function': handler.end,
                    'struct': get_struct_instance(handler.end_struct),
                    'skip_bytes': handler.end_skip,
                    }

        elif isinstance(section, tsec.TextDirective):
            directive = section

            cur_item = directive.as_data_dict(None)
            if last_section is not None:
                last_section['data'].append(cur_item)

            if handler is None:
                return

            info = {'function': handler.start,
                    'struct': get_struct_instance(handler.struct),
                    'skip_bytes': handler.skip_bytes,
                    }

        elif isinstance(section, tsec.SkipCode):
            raise NotImplementedError('skip codes')

        # run the handler callback function
        struct = info['struct']
        handler_fcn = info['function']
        struct_info = {}
        if struct is not None:
            f.seek_cur(-2)
            f.readinto(struct)

            struct_info = struct.info
            if 'info' not in cur_item:
                cur_item['info'] = struct_info
            else:
                cur_item['info'].update(struct_info)

        handler_fcn(context, **struct_info)

        skip_bytes = info['skip_bytes']
        if skip_bytes:
            f.seek_cur(skip_bytes)

        # TODO temporary way of doing this
        if '_started_' in cur_item:
            return

        if cur_item['name'] in ('keyword', ):
            context._keyword_count += 1
            if 0:
                print('[End] ', end='')
                # cur_item.pprint()
                pprint.pprint(cur_item)

            if (context._keyword_count % 100) == 0:
                print('keyword count', context._keyword_count)
                time.sleep(0.1)

        if cur_item['name'] == 'narrow':
            # TODO this should go elsewhere
            if context.convert_narrow:
                data = cur_item['data']
                if len(data) == 1 and isinstance(data[0],
                                                 six.string_types):
                    text = data[0]
                    cur_item['data'] = [to_narrow(text)]
                    # TODO whole section should be replaced, but that
                    # means need to keep track of parent sections as
                    # well...
                else:
                    logger.warning('Something else in a narrow section? '
                                   '({})', data)

        if isinstance(section, tsec.SectionEnd):
            return cur_item

    def read(self, location=None, convert_narrow=True, search=None,
             by='section'):
        # TODO: have book locking mechanism for multithreaded applications
        if location is not None:
            self.seek(location)
        elif search is not None:
            self._seek_search_page(search)

        header = tsec.TextStruct()

        book = self._subbook.book
        encoding = book.encoding
        f = self._zio

        context = TextContext(self)
        context['encoding'] = encoding
        context.zio = self._zio
        context.new_section = []
        context.sections = []
        context.convert_narrow = convert_narrow
        context.header = header

        while True:
            f.readinto(header)

            if header.is_section:
                user_sec = None
                try:
                    section = tsec.sections[header.code2]
                except KeyError:
                    if context.skip_code == header.code2:
                        context.skip_code = None
                else:
                    try:
                        user_sec = self._read_section(context, section)
                    except tsec.TextHardStop:
                        logger.debug('Reached text hard stop')
                        break
                    except tsec.TextSoftStop:
                        logger.debug('Reached text soft stop')
                        # break

                    if user_sec is not None and by == 'section':
                        print(context.sections)
                        yield user_sec

            elif not context.sections:
                # Not in a section
                pass
            else:
                ch = self._read_character(context, header)
                if ch is not None:
                    context.printable_count += 1
                    last_section = context.last_section
                    if last_section is None:
                        continue

                    data = last_section['data']
                    if data and isinstance(data[-1], six.string_types):
                        data[-1] += ch
                    else:
                        data.append(ch)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

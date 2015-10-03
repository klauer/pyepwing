from __future__ import print_function
import os
import logging

from .errors import ZioFileNotFoundError
from .zio import (get_zio_language, get_zio_catalog)
from .util import fix_path_case
from .text import SubbookText

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    logging.basicConfig()


class Subbook(object):
    _named_paths = {'data': 'data',
                    'gaiji': 'gaiji',
                    'stream': 'stream',
                    'movie': 'movie',
                    }

    def __init__(self, book, idx, title=None, directory=None, index_page=None,
                 narrow_fonts=None, wide_fonts=None, resources=None,
                 text_filename=None, named_paths=None):
        print('Subbook', idx, title, 'index page', index_page)

        if named_paths is not None:
            self._named_paths.update(named_paths)

        self._book = book

        self._path = fix_path_case(self._book._path, directory)
        self._index_page = index_page

        self._title = title
        self._narrow_fonts = narrow_fonts
        self._wide_fonts = wide_fonts
        self._appendix = None

        if resources:
            self._resources = resources
            logger.warning('TODO: resources')

        if self.stream_data_only:
            self._text_filename = None
            self.text = None
        else:
            self._text_filename = text_filename

            self._data_path = fix_path_case(self._path,
                                            self._named_paths['data'])
            if self._text_filename is not None:
                self.text = SubbookText(self, self._data_path,
                                        self._text_filename)

    @property
    def appendix(self):
        return self._appendix

    @property
    def book(self):
        return self._book

    @property
    def stream_data_only(self):
        return (self._index_page == 0)

    def _set_search(self, key, search):
        if isinstance(key, str):
            logger.debug('Search added %s=%s', key, search)
            if key == 'multi':
                if 'multi' not in self._searches:
                    self._searches['multi'] = []
                self._searches['multi'].append(search)
                return

            self._searches[key] = search
        else:
            type_required, key, subkey = key

            if type_required == self.book.type_:
                logger.debug('Book type match for search %s[%s]=%s',
                             key, subkey, search)

                if key == 'sebxa_zip':
                    self.text._set_sebxa(subkey, **search)
                else:
                    if subkey is not None:
                        key = (key, subkey)

                    self._searches[key] = search

    def _reset_searches(self):
        self._multi_count = 0
        self._searches = {}

    def read(self, location=None, **kwargs):
        if self.text is None:
            raise ValueError('No text in this subbbook')

        return self.text.read(location=location, **kwargs)


class Book(object):
    _default_encoding = 'jisx0208'

    def __init__(self, path):
        self._path = path

        self._load_language()
        self._load_catalog()

    def _load_language(self):
        try:
            zlang = get_zio_language(self, self._path)
        except ZioFileNotFoundError:
            logger.debug('Language file not found; assuming %s',
                         self._default_encoding)
            self._encoding = self._default_encoding
        else:
            self._encoding = zlang.encoding

    def _load_catalog(self):
        try:
            catalog = self._catalog = get_zio_catalog(self, self._path)
        except ZioFileNotFoundError:
            raise

        def create_subbook(i, info):
            try:
                return Subbook(self, i, **info)
            except Exception as ex:
                logger.error('Subbook %d of %d creation failed', i + 1,
                             len(catalog._subbooks), exc_info=ex)

        self._subbooks = [create_subbook(i, subbook)
                          for i, subbook in enumerate(catalog._subbooks)]

    @property
    def subbooks(self):
        return tuple(self._subbooks)

    @property
    def encoding(self):
        return self._encoding

    @property
    def is_epwing(self):
        return self.type_ == 'epwing'

    @property
    def is_eb(self):
        return self.type_ == 'eb'

    @property
    def type_(self):
        return self._catalog.book_type


def test_all(base_path):
    logging.basicConfig(level=logging.DEBUG)

    book_list = []
    for root, dirs, files in os.walk(base_path):
        lower_files = [fn.lower() for fn in files]
        if 'catalog' in lower_files or 'catalogs' in lower_files:
            print('Adding book: {} ({})'.format(os.path.split(root)[-1], root))
            book_list.append(os.path.abspath(root))

    for name in book_list:
        print()
        print('------{}------'.format(name))
        book = Book(name)
        print(book._catalog._subbooks)
        # book.subbooks[0].read()

    return book


def test():
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('eb').setLevel(logging.DEBUG)

    book_list = ('daijisen', 'daijirin', 'kojien', 'meikyou', 'shinjirin',
                 'shinmeikai')

    print('-----------------------')
    print('------ book test ------')
    book_list = ('daijirin', )
    # book_list = ('shinmeikai', )
    for name in book_list:
        name = fix_path_case('.', name)
        print()
        print('------{}------'.format(name))
        book = Book(name)
        print(book._catalog._subbooks)
        for sec in book.subbooks[0].read(search='text', by='section'):
            name = sec['name']
            print('read section ({}) {}'.format(name, sec['data']))

    return book


if __name__ == '__main__':
    import sys
    if sys.stdout.isatty() and sys.stdout.encoding.lower() != 'utf-8':
        logger.warning('TTY output encoding: {}'.format(
                       sys.stdout.encoding))

    book = test()
    # book = test_all('all')

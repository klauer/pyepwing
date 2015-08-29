from __future__ import print_function
import struct
import logging
import io
import os
import ctypes

import six

from .structs import (EpwingCatalog, EbCatalog, EpwingSubbookResource)
from .errors import (ZioFileNotFoundError, CharCodeUnsupportedError, )
from .util import listdir_lower

# NOTE: io.open gives a buffered interface to the file, which is default in
#       python 3 but not python 2


logger = logging.getLogger(__name__)


class ZioFileBase(object):
    _EXTENSIONS_ = []

    def __init__(self, filename, mode='rb'):
        self._filename = os.path.abspath(filename)
        self._mode = mode
        self._f = None

        self._name_ext = os.path.split(filename)[-1]
        self._name = os.path.splitext(self._name_ext)[0]
        self.buf = b''

    def open(self):
        if self._f is not None:
            return

        logger.debug('Opening file {}'.format(self._filename))
        self._f = io.open(self._filename, mode='rb')

    def close(self):
        if self._f is not None:
            logger.debug('Closing file {}'.format(self._f))
            self._f.close()
            self._f = None

    @property
    def filename(self):
        return self._filename

    def seek_start(self, pos):
        raise NotImplementedError()

    seek = seek_start

    def seek_cur(self, pos):
        raise NotImplementedError()

    def seek_end(self, pos):
        raise NotImplementedError()

    def tell(self):
        raise NotImplementedError()

    def readinto(self, struct):
        raise NotImplementedError()

    def read(self, nbytes=16):
        raise NotImplementedError()

    def read_uchar(self):
        raise NotImplementedError()

    def read_ushort(self):
        raise NotImplementedError()


class ZioPlainFile(ZioFileBase):
    _EXTENSIONS_ = ['.org', '']

    def seek_start(self, pos):
        self._f.seek(pos, 0)

    seek = seek_start

    def seek_cur(self, pos):
        self._f.seek(pos, 1)

    def seek_end(self, pos):
        self._f.seek(pos, 2)

    def tell(self):
        return self._f.tell()

    def readinto(self, struct, advance=True):
        if self._f is None:
            self.open()

        if advance:
            return self._f.readinto(struct)
        else:
            ret = self._f.readinto(struct)
            self.seek_cur(-ctypes.sizeof(struct))
            return ret

    def read(self, nbytes=16):
        if self._f is None:
            self.open()

        return self._f.read(nbytes)

    def read_uchar(self):
        return struct.unpack('>B', self.read(1))

    def read_ushort(self):
        return struct.unpack('>H', self.read(2))

    def read_uint(self):
        return struct.unpack('>I', self.read(4))


class ZioEbzipFile(ZioFileBase):
    _EXTENSIONS_ = ['.ebz']

    def __init__(self, *args, **kwargs):
        super(ZioEbzipFile, self).__init__(*args, **kwargs)

        self._pos = 0
        self._file_size = 0

    def open(self):
        raise NotImplementedError()

    def seek_start(self, pos):
        self._pos = pos

    def seek_cur(self, pos):
        self._pos += pos

    def seek_end(self, pos):
        self._pos = self._file_size - pos
        raise NotImplementedError('set filesize properly')


_ZioHandlers = {}
_ZioDefaultHandler = ZioPlainFile


def _register_zio_handler(class_):
    for ext in class_._EXTENSIONS_:
        _ZioHandlers[ext.lower()] = class_


_register_zio_handler(ZioPlainFile)
_register_zio_handler(ZioEbzipFile)


def open_zio_file(path, name, **kwargs):
    if isinstance(name, six.string_types):
        fns = [(''.join([name, ext]), handler)
               for ext, handler in six.iteritems(_ZioHandlers)]
        print(path, fns)
    else:
        names = name
        for name in names:
            try:
                return open_zio_file(path, name, **kwargs)
            except ZioFileNotFoundError:
                err = ('File(s) not found ({}*, {})'.format(
                    os.path.join(path, '|'.join(names)), kwargs))

                raise ZioFileNotFoundError(err)

    lower_files = listdir_lower(path)

    for fn, handler in fns:
        try:
            case_fn = lower_files[fn.lower()]
        except KeyError:
            pass
        else:
            full_path = os.path.join(path, case_fn)
            return handler(full_path, **kwargs)

    err = ('File not found ({}*, valid names: {})'.format(
           os.path.join(path, name), [fn[0] for fn in fns]))

    raise ZioFileNotFoundError(err)


class ZioBase(object):
    def __init__(self, book, path, name, f=None, **kwargs):
        self._book = book
        self._path = path

        if f is not None:
            self._f = f
            logger.info('Specified ZioFile: {}'.format(self._f))
            logger.debug('Resetting position')
            self.seek(0)
        else:
            self._f = open_zio_file(path, name, **kwargs)
            logger.info('Found ZioFile: {}'.format(self._f.filename))

    @property
    def name(self):
        return self._f._name


class ZioLanguage(ZioBase):
    code_to_encoding = {1: 'iso8859-1',
                        2: 'jisx0208',
                        3: 'jisx0208-gb2312',
                        }

    def __init__(self, book, path, name='language'):
        super(ZioLanguage, self).__init__(book, path, name)

        self._char_code = self._f.read_ushort()
        try:
            self._encoding = self.code_to_encoding[self._char_code]
        except KeyError:
            err = 'Character code {}'.format(self._char_code)
            raise CharCodeUnsupportedError(err)

    @property
    def char_code(self):
        return self._char_code

    @property
    def encoding(self):
        return self._encoding


class ZioCatalog(ZioBase):
    disk_filenames = None

    def __init__(self, book, path, name):
        super(ZioCatalog, self).__init__(book, path, name)

        self._subbooks = []

        self._read_catalog()

    def _read_catalog(self):
        cat_cls = self._catalog_cls
        header_cls = cat_cls.header_class

        self._header = header_cls()
        self._f.readinto(self._header)

        self._subbook_count = self._header.subbook_count
        logger.debug('Subbook count {}'.format(self._subbook_count))

        encoding = self._book.encoding
        catalog_entry = cat_cls()

        self._subbooks = []
        for subbook in range(1, self._subbook_count + 1):
            logger.debug('Subbook #%d', subbook)
            self._f.readinto(catalog_entry)

            catalog_entry.set_default_encoding(encoding)
            cat_info = catalog_entry.info_dict

            logger.debug('Subbook %d: %s', subbook, cat_info)
            self._subbooks.append(cat_info)

    @property
    def book_type(self):
        return self._catalog_cls.book_type


class ZioEbCatalog(ZioCatalog):
    '''Catalogs for EB/EBG/EBXA/EBXA-C/S-EBXA formats'''

    disk_filenames = ('catalog', )

    _catalog_cls = EbCatalog


class ZioEpwingCatalog(ZioCatalog):
    '''Catalogs for the Epwing format'''

    disk_filenames = ('catalogs', )

    _catalog_cls = EpwingCatalog

    def _read_catalog(self):
        super(ZioEpwingCatalog, self)._read_catalog()

        self._epwing_version = self._header.epwing_version
        logger.debug('EPWing version {}'.format(self._epwing_version))

        sbs = EpwingSubbookResource()
        sbs.set_default_encoding(self._book.encoding)

        for i, subbook in enumerate(self._subbooks):
            self._f.readinto(sbs)
            logger.debug('Sub-book %d filename: %s', i + 1,
                         sbs.text_filename)

            if sbs.is_valid:
                resources = sbs.resources
                subbook['text_filename'] = sbs.text_filename
                if resources:
                    logger.debug('Found resources: %s', resources)

                    # TODO if resource path not specified, use text path
                    subbook['resources'] = resources


catalog_types = [ZioEbCatalog, ZioEpwingCatalog]


def _class_by_filename(types, attr='disk_filenames'):
    '''Instantiate a class based on the existance of a filename'''
    def instantiate(book, path, **kwargs):
        all_filenames = []

        for class_ in types:
            filenames = getattr(class_, attr)
            all_filenames.extend(filenames)
            for filename in filenames:
                try:
                    open_zio_file(path, filename)
                except ZioFileNotFoundError:
                    pass
                else:
                    logger.info('Filename %s -> %s',
                                filename, class_)
                    return class_(book, path, filename, **kwargs)

        err = ('File(s) not found ({}*, {})'.format(
            os.path.join(path, '|'.join(all_filenames)), kwargs))

        raise ZioFileNotFoundError(err)

    return instantiate


get_zio_catalog = _class_by_filename(catalog_types)
get_zio_language = ZioLanguage

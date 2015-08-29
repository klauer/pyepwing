class ZioError(Exception):
    pass


class ZioFileNotFoundError(IOError, ZioError):
    pass


class ZioCatalogOpenFailedError(ZioFileNotFoundError):
    pass


class BookError(Exception):
    pass


class CharCodeUnsupportedError(BookError):
    pass

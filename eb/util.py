from __future__ import print_function
import os
from .errors import (ZioFileNotFoundError, )


def listdir_lower(path):
    return {fn.lower(): fn for fn in os.listdir(path)}


def fix_path_case(path, fn):
    '''
    path is known with correct case
    fn is expected to be there, but with possibly incorrect case

    returns:
        path/FN_with_correct_case
    '''
    files = listdir_lower(path)
    try:
        return os.path.join(path, files[fn.lower()])
    except KeyError as ex:
        raise ZioFileNotFoundError(os.path.join(path, fn))

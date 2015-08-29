#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import logging
import six
import unicodedata


logger = logging.getLogger(__name__)

_wide_to_narrow = None
_narrow_to_wide = None


def _init_cache():
    '''Creates a mapping of wide->narrow and narrow->wide characters'''

    global _wide_to_narrow
    global _narrow_to_wide

    _wide_to_narrow = {}
    _narrow_to_wide = {}

    char_names = {six.unichr(i): unicodedata.name(six.unichr(i), None)
                  for i in range(0, 65536)
                  }

    for wide_ch, name in char_names.items():
        if name is None:
            continue

        if name.upper().startswith('FULLWIDTH '):
            half_name = name[len('FULLWIDTH '):]
        else:
            half_name = 'HALFWIDTH {}'.format(name)

        try:
            half_ch = unicodedata.lookup(half_name)
        except KeyError:
            pass
        else:
            _wide_to_narrow[wide_ch] = half_ch
            _narrow_to_wide[half_ch] = wide_ch

    logger.debug('Mapped %d characters from wide<->narrow',
                 len(_wide_to_narrow))


def to_narrow(s):
    '''Take a wide-character string and convert it to a narrow one'''
    if _wide_to_narrow is None:
        _init_cache()

    return u''.join(_wide_to_narrow.get(ch, ch) for ch in s)


def to_wide(s):
    '''Take a narrow-character string and convert it to a wide one'''
    if _narrow_to_wide is None:
        _init_cache()

    return u''.join(_narrow_to_wide.get(ch, ch) for ch in s)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    tests = [(u'アイウエオカキクケコサシスセソナニヌネノ',
              u'ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾅﾆﾇﾈﾉ'),
             (u'ｔｅｓｔ', u'test'),
             ]

    for wide_test, narrow_test in tests:
        print(wide_test, narrow_test)
        assert to_narrow(wide_test) == narrow_test
        assert to_wide(narrow_test) == wide_test
        assert to_narrow(to_wide(narrow_test)) == narrow_test

    # this is a quick demo of how the map is generated
    wide_t = u'ｔ'
    narrow_t = u't'
    wide_a = u'ア'
    half_a = u'ｱ'

    for ch in [wide_t, narrow_t, wide_a, half_a]:
        print(ch, unicodedata.name(ch))

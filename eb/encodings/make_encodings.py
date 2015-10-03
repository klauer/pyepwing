from __future__ import print_function
import os
import sys


def make_encoding(fn, enc_col, utf8_col, out_f=sys.stdout, name=None):
    if name is None:
        name = os.path.split(fn)[1].lower()
        name = os.path.splitext(name)[0]

    print('{} = {{'.format(name), file=out_f)

    with open(fn, 'rt') as f:
        for line in f.readlines():
            line = line.strip()
            if line.startswith('#') or not line:
                continue

            cols = line.split('\t')
            cols[enc_col]

            print('    {}: u"\\u{}",'.format(cols[enc_col], cols[utf8_col][2:]),
                  file=out_f)
    print('}', file=out_f)


if __name__ == '__main__':
    with open('jisx0208.py', 'wt') as f:
        make_encoding('jisx0208.txt', 1, 2, out_f=f)

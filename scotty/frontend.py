from __future__ import print_function
import sys
from . import beam_up


def main():
    if len(sys.argv) < 2:
        print('Usage: beamup [directory] <scotty>')
        print('  scotty - Optional URL for scotty. Defaults to http://scotty')
        return 1

    kwargs = {
        'directory': sys.argv[1]
    }
    if len(sys.argv) > 2:
        kwargs['scotty_url'] = sys.argv[2]

    print('Beaming up {0}'.format(sys.argv[1]))
    beam_up(**kwargs)

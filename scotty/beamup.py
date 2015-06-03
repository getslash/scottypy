from __future__ import print_function
import logging
import sys
from . import Scotty


def main():
    if len(sys.argv) < 3:
        print('Usage: beamup [directory] [scotty]')
        print('  scotty - URL for scotty')
        return 1

    logging.basicConfig(format='%(name)s:%(levelname)s:%(message)s', level=logging.DEBUG)

    scotty = Scotty(sys.argv[2])

    logging.info('Beaming up %s', sys.argv[1])
    beam_id = scotty.beam_up(sys.argv[1])
    logging.info('Successfully beamed beam #%d', beam_id)

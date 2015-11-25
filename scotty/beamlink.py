import os
import click
from . import Scotty


@click.command()
@click.argument("beam_id")
@click.option('--url', default='http://scotty.infinidat.com', help='Base URL of Scotty')
@click.option('--storage_base', default='/var/scotty', help='Base location of Scotty\'s storage')
@click.option('-n', '--name', default=None, help='A user friendly name for the beam. The default is the beam id')
def main(beam_id, url, storage_base, name):
    scotty = Scotty(url)

    beam = scotty.get_beam(beam_id)

    dest = beam_id if name is None else name
    if not os.path.isdir(dest):
        os.mkdir(dest)

    for file_ in beam.iter_files():
        file_.link(storage_base, dest)

    click.echo("Created a view of beam {} in {}".format(dest, dest))

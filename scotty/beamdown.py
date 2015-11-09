import os
import click
from . import Scotty, NotOverwriting


@click.command()
@click.argument("beam_id")
@click.option('--dest', default=None, help='Destination directory')
@click.option('--url', default='http://scotty.infinidat.com', help='Base URL of Scotty')
@click.option('--overwrite/--no-overwrite', default=False, help='Overwrite existing files on the disk')
def main(beam_id, dest, url, overwrite):
    scotty = Scotty(url)

    beam = scotty.get_beam(beam_id)

    if dest is None:
        dest = beam_id
        if not os.path.isdir(dest):
            os.mkdir(dest)

    click.echo("Downloading beam {} to directory {}".format(beam_id, dest))

    for file_ in beam.iter_files():
        click.echo("Downloading {}".format(file_.file_name))
        try:
            file_.download(dest, overwrite=overwrite)
        except NotOverwriting as e:
            click.echo("{} already exists. Use --overwrite to overwrite".format(e.file))

    click.echo("Downloaded beam {} to directory {}".format(beam_id, dest))

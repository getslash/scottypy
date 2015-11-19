import os
import click
from . import Scotty, NotOverwriting


@click.command()
@click.argument("beam_id")
@click.option('--dest', default=None, help='Destination directory')
@click.option('--url', default='http://scotty.infinidat.com', help='Base URL of Scotty')
@click.option('-f', '--filter', default=None, help="Download only files that contain the given string in their name (case insensetive)")
@click.option('--overwrite/--no-overwrite', default=False, help='Overwrite existing files on the disk')
def main(beam_id, dest, url, overwrite, filter): # pylint: disable=W0622
    scotty = Scotty(url)

    beam = scotty.get_beam(beam_id)

    if dest is None:
        dest = beam_id

    if not os.path.isdir(dest):
        os.makedirs(dest)

    click.echo("Downloading beam {} to directory {}".format(beam_id, dest))

    for file_ in beam.iter_files():
        if filter is not None and filter not in file_.file_name:
            click.echo("Skipping {}".format(file_.file_name))
            continue

        click.echo("Downloading {}".format(file_.file_name))
        try:
            file_.download(dest, overwrite=overwrite)
        except NotOverwriting as e:
            click.echo("{} already exists. Use --overwrite to overwrite".format(e.file))

    click.echo("Downloaded beam {} to directory {}".format(beam_id, dest))

import logging
import sys
import click
import os
import json
from . import Scotty, NotOverwriting


_CONFIG_PATH = os.path.expanduser("~/.scotty.conf")


def obsolete_command():
    subcommand = os.path.basename(sys.argv[0])[4:]
    print("beam{0} is obsolete. Run \"scotty {0}\" instead".format(subcommand))
    return 0


def _get_config():
    try:
        with open(_CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(config):
    with open(_CONFIG_PATH, "w") as f:
        json.dump(config, f)


@click.group()
def main():
    pass


def _get_url():
    config = _get_config()
    if not config or 'url' not in config:
        raise click.ClickException(
            """The URL of Scotty has not been set.
You can set the URL either by using the --url flag or by running \"scotty set_url http://some.scotty.com\"""")
    return config['url']


@main.command()
@click.argument("beam_id")
@click.option('--url', default=_get_url, help='Base URL of Scotty')
@click.option('--storage_base', default='/var/scotty', help='Base location of Scotty\'s storage')
@click.option('-n', '--name', default=None, help='A user friendly name for the beam. The default is the beam id')
def link(beam_id, url, storage_base, name):
    scotty = Scotty(url)

    beam = scotty.get_beam(beam_id)

    dest = beam_id if name is None else name
    if not os.path.isdir(dest):
        os.mkdir(dest)

    for file_ in beam.iter_files():
        file_.link(storage_base, dest)

    click.echo("Created a view of beam {} in {}".format(dest, dest))


@main.command()
@click.argument("beam_id")
@click.option('--dest', default=None, help='Destination directory')
@click.option('--url', default=_get_url, help='Base URL of Scotty')
@click.option('-f', '--filter', default=None, help="Download only files that contain the given string in their name (case insensetive)")
@click.option('--overwrite/--no-overwrite', default=False, help='Overwrite existing files on the disk')
def down(beam_id, dest, url, overwrite, filter): # pylint: disable=W0622
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


@main.command()
@click.argument("directory")
@click.option('--url', default=_get_url, help='Base URL of Scotty')
def up(directory, url):
    logging.basicConfig(format='%(name)s:%(levelname)s:%(message)s', level=logging.DEBUG)

    scotty = Scotty(url)

    click.echo('Beaming up {}'.format(directory))
    beam_id = scotty.beam_up(directory)
    click.echo('Successfully beamed beam #{}'.format(beam_id))


@main.command()
@click.argument("url")
def set_url(url):
    config = _get_config()

    scotty = Scotty(url)
    scotty.sanity_check()

    config['url'] = url
    _save_config(config)

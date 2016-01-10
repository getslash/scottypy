import logging
import sys
import re
import os
import json
import webbrowser
from getpass import getpass
import click
from . import Scotty, NotOverwriting


_CONFIG_PATH = os.path.expanduser("~/.scotty.conf")
_BEAM_PATH = re.compile(r"^([^@:]+)@([^@:]+):(.*)$")


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
def down(beam_id, dest, url, overwrite, filter):  # pylint: disable=W0622
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


@main.group()
def up():
    pass


@up.command()
@click.argument("directory")
@click.option('--url', default=_get_url, help='Base URL of Scotty')
def local(directory, url):
    logging.basicConfig(format='%(name)s:%(levelname)s:%(message)s', level=logging.DEBUG)

    scotty = Scotty(url)

    click.echo('Beaming up {}'.format(directory))
    beam_id = scotty.beam_up(directory)
    click.echo('Successfully beamed beam #{}'.format(beam_id))


@up.command()
@click.argument("path")
@click.option("--rsa_key", type=click.Path(exists=True, dir_okay=False))
@click.option("--email")
@click.option("--goto", is_flag=True, default=False, help="Open your browser at the beam page")
@click.option('--url', default=_get_url, help='Base URL of Scotty')
def remote(url, path, rsa_key, email, goto):
    scotty = Scotty(url)

    m = _BEAM_PATH.search(path)
    if not m:
        raise click.ClickException("Invalid path. Path should be in the form of user@host:/path/to/directory")

    user, host, directory = m.groups()
    if rsa_key:
        with open(rsa_key, "r") as f:
            rsa_key = f.read()
        password = None
    else:
        password = getpass("Password for {}@{}: ".format(user, host))
    beam_id = scotty.initiate_beam(user, host, directory, password, rsa_key, email)
    click.echo("Successfully initiated beam #{} to {}@{}:{}".format(
        beam_id, user, host, directory))

    beam_url = "{}/#/beam/{}".format(url, beam_id)
    if goto:
        webbrowser.open(beam_url)
    else:
        click.echo(beam_url)


@main.command("tag")
@click.option("-d", "--delete", help="Delete the specified tag", is_flag=True, default=False)
@click.option('--url', default=_get_url, help='Base URL of Scotty')
@click.argument("tag")
@click.argument("beam")
def tag_beam(tag, beam, delete, url):
    scotty = Scotty(url)
    if delete:
        scotty.remove_tag(beam, tag)
    else:
        scotty.add_tag(beam, tag)


@main.command()
@click.argument("url")
def set_url(url):
    config = _get_config()

    scotty = Scotty(url)
    scotty.sanity_check()

    config['url'] = url
    _save_config(config)

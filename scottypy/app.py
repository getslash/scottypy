import logging
import sys
import re
import os
import json
import webbrowser
import capacity
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


def _write_beam_info(beam, directory):
    with open(os.path.join(directory, 'beam.txt'), 'w') as f:
        f.write("""Start: {start}
Host: {host}
Directory: {directory}
Comment: {comment}
""".format(start=beam.start, host=beam.host, directory=beam.directory, comment=beam.comment))


def _link_beam(storage_base, beam, dest):
    if not os.path.isdir(dest):
        os.makedirs(dest)

    for file_ in beam.get_files():
        file_.link(storage_base, dest)

    _write_beam_info(beam, dest)

    click.echo("Created a view of beam {} in {}".format(beam.id, dest))


@main.command()
@click.argument("beam_id_or_tag")
@click.option('--url', default=_get_url, help='Base URL of Scotty')
@click.option('--storage_base', default='/var/scotty', help='Base location of Scotty\'s storage')
@click.option('-d', '--dest', default=None, help='Link destination')
def link(beam_id_or_tag, url, storage_base, dest):
    """Create symbolic links representing a single beam or a set of beams by their tag ID.
    To link a specific beam just use write its id as an argument.
    To link an entire tag specify t:[tag_name] as an argument, replacing [tag_name] with the name of the tag"""
    scotty = Scotty(url)

    if beam_id_or_tag.startswith('t:'):
        tag = beam_id_or_tag[2:]
        if dest is None:
            dest = tag

        for beam in scotty.get_beams_by_tag(tag):
            _link_beam(storage_base, beam, os.path.join(dest, str(beam.id)))
    else:
        beam = scotty.get_beam(beam_id_or_tag)
        if dest is None:
            dest = beam_id_or_tag

        _link_beam(storage_base, beam, dest)


@main.command()
@click.argument("beam_id_or_tag")
@click.option('--url', default=_get_url, help='Base URL of Scotty')
def show(beam_id_or_tag, url):
    """List the files of the given beam or tag"""
    scotty = Scotty(url)

    def _list(beam):
        print("Beam #{}".format(beam.id))
        print("    Host: {}".format(beam.host))
        print("    Directory: {}".format(beam.directory))
        print("    Size: {}".format(beam.size * capacity.byte))
        print("    Files:")
        for file_ in beam.get_files():
            print("        {} ({})".format(file_.file_name, file_.size * capacity.byte))

        print("")

    if beam_id_or_tag.startswith('t:'):
        tag = beam_id_or_tag[2:]
        for beam in scotty.get_beams_by_tag(tag):
            _list(beam)
    else:
        _list(scotty.get_beam(beam_id_or_tag))


def _download_beam(beam, dest, overwrite, filter):
    if not os.path.isdir(dest):
        os.makedirs(dest)

    click.echo("Downloading beam {} to directory {}".format(beam.id, dest))

    for file_ in beam.get_files(filter_=filter):
        click.echo("Downloading {}".format(file_.file_name))
        try:
            file_.download(dest, overwrite=overwrite)
        except NotOverwriting as e:
            click.echo("{} already exists. Use --overwrite to overwrite".format(e.file))

    _write_beam_info(beam, dest)

    click.echo("Downloaded beam {} to directory {}".format(beam.id, dest))


@main.command()
@click.argument("beam_id_or_tag")
@click.option('--dest', default=None, help='Destination directory')
@click.option('--url', default=_get_url, help='Base URL of Scotty')
@click.option('-f', '--filter', default=None, help="Download only files that contain the given string in their name (case insensetive)")
@click.option('--overwrite/--no-overwrite', default=False, help='Overwrite existing files on the disk')
def down(beam_id_or_tag, dest, url, overwrite, filter):  # pylint: disable=W0622
    """Download a single beam or a set of beams by their tag ID.
    To download a specific beam just use write its id as an argument.
    To download an entire tag specify t:[tag_name] as an argument, replacing [tag_name] with the name of the tag"""
    scotty = Scotty(url)

    if beam_id_or_tag.startswith('t:'):
        tag = beam_id_or_tag[2:]
        if dest is None:
            dest = tag

        for beam in scotty.get_beams_by_tag(tag):
            _download_beam(beam, os.path.join(dest, str(beam.id)), overwrite, filter)
    else:
        beam = scotty.get_beam(beam_id_or_tag)
        if dest is None:
            dest = beam_id_or_tag
        _download_beam(beam, dest, overwrite, filter)


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
@click.option("--stored_key", default=None)
def remote(url, path, rsa_key, email, goto, stored_key):
    scotty = Scotty(url)

    m = _BEAM_PATH.search(path)
    if not m:
        raise click.ClickException("Invalid path. Path should be in the form of user@host:/path/to/directory")

    password = None
    user, host, directory = m.groups()
    if rsa_key:
        with open(rsa_key, "r") as f:
            rsa_key = f.read()
    elif stored_key:
        pass
    else:
        password = getpass("Password for {}@{}: ".format(user, host))
    beam_id = scotty.initiate_beam(user, host, directory, password, rsa_key, email, stored_key=stored_key)
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


@main.command()
@click.argument("beam_id")
@click.argument("comment")
@click.option('--url', default=_get_url, help='Base URL of Scotty')
def set_comment(beam_id, url, comment):
    """Set a comment for the specified beam"""
    scotty = Scotty(url)

    beam = scotty.get_beam(beam_id)
    beam.set_comment(comment)

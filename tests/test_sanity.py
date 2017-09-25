import os
import gzip
from contextlib import closing
from slash import parametrize


_LOG = """I can see what you see not
Vision milky, then eyes rot.
When you turn, they will be gone,
Whispering their hidden song.
Then you see what cannot be
Shadows move where light should be.
Out of darkness, out of mind,
Cast down into the Halls of the Blind."""


def _local_beam(scotty, email):
    return scotty.beam_up('build', email=email)


def _remote_beam_password(scotty, email):
    return scotty.initiate_beam('vagrant', '192.168.50.4', '/home/vagrant', password='vagrant', email=email)


def _remote_beam_rsa(scotty, email):
    with open(os.path.expanduser("~/.vagrant.d/insecure_private_key"), "r") as f:
        key = f.read()

    return scotty.initiate_beam('vagrant', '192.168.50.4', '/home/vagrant', rsa_key=key, email=email)


@parametrize('beam_function', [_local_beam, _remote_beam_password, _remote_beam_rsa])
@parametrize('email', [None, 'roeyd@infinidat.com'])
def test_sanity(scotty, beam_function, email):
    beam_id = beam_function(scotty, email)
    scotty.add_tag(beam_id, 'tag/with/slashes')
    assert beam_id in [b.id for b in scotty.get_beams_by_tag('tag/with/slashes')]
    scotty.remove_tag(beam_id, 'tag/with/slashes')
    assert beam_id not in [b.id for b in scotty.get_beams_by_tag('tag/with/slashes')]
    beam = scotty.get_beam(beam_id)
    pact = beam.get_pact()
    pact.wait()
    assert beam.completed


def test_single_file(scotty, tempdir):
    file_name = "something.log"
    path = os.path.join(tempdir, file_name)
    with open(path, "w") as log_file:
        log_file.write(_LOG)

    beam_id = scotty.beam_up(path)
    beam = scotty.get_beam(beam_id)
    files = list(beam.iter_files())
    assert len(files) == 1

    beamed_file = files[0].storage_name
    full_path = os.path.join("/var/scotty", beamed_file)
    assert full_path.endswith(".log.gz"), full_path
    assert file_name in beamed_file
    with closing(gzip.GzipFile(full_path, "r")) as f:
        content = f.read().decode("ASCII") # pylint: disable=no-member

    assert content == _LOG

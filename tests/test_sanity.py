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


def _local_beam(scotty):
    return scotty.beam_up('build')


def _remote_beam_password(scotty):
    return scotty.initiate_beam('vagrant', '192.168.50.4', '/home/vagrant', password='vagrant')


def _remote_beam_rsa(scotty):
    with open(os.path.expanduser("~/.vagrant.d/insecure_private_key"), "r") as f:
        key = f.read()

    return scotty.initiate_beam('vagrant', '192.168.50.4', '/home/vagrant', rsa_key=key)


@parametrize('beam_function', [_local_beam, _remote_beam_password, _remote_beam_rsa])
def test_sanity(scotty, beam_function):
    beam_id = beam_function(scotty)
    scotty.add_tag(beam_id, 'test')
    scotty.remove_tag(beam_id, 'test')
    scotty.get_beam(beam_id)


def test_compressed_file(scotty, tempdir):
    log_path = os.path.join(tempdir, "something.log")
    with open(log_path, "w") as log_file:
        log_file.write(_LOG)

    txt_path = os.path.join(tempdir, "something.txt")
    with open(txt_path, "w") as txt_file:
        txt_file.write(_LOG)

    beam_id = scotty.beam_up(tempdir)
    beam = scotty.get_beam(beam_id)
    assert len(beam.files) == 2

    found_compressed = False
    found_uncompressed = False

    for beamed_file in beam.files:
        full_path = os.path.join("/var/scotty", beamed_file.storage_name)
        if full_path.endswith(".gz"):
            found_compressed = True
            with closing(gzip.GzipFile(full_path, "r")) as f:
                content = f.read().decode("ASCII")
        else:
            found_uncompressed = True
            with open(full_path, "r") as f:
                content = f.read()

        assert content == _LOG

    assert found_uncompressed
    assert found_compressed

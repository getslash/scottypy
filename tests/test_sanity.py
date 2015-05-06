import os
from slash import parametrize


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

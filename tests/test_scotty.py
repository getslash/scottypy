from scottypy.scotty import Scotty

import os
import pytest

COMBADGE_VERSIONS = ['v1', 'v2']

@pytest.fixture()
def scotty_url():
    return "http://scotty-staging.lab.gdc.il.infinidat.com"


@pytest.fixture()
def directory():
    yield os.path.join(os.getcwd(), 'debug.log')


@pytest.fixture()
def scotty(scotty_url):
    return Scotty(url=scotty_url)


def test_scotty_url(scotty, scotty_url):
    assert scotty._url == scotty_url


@pytest.mark.parametrize("combadge_version", COMBADGE_VERSIONS)
def test_prefetch_combadge(scotty, combadge_version):
    scotty.prefetch_combadge(combadge_version=combadge_version)
    import pdb; pdb.set_trace()


def test_get_combadge(scotty):
    pass


@pytest.mark.parametrize("combadge_version", COMBADGE_VERSIONS)
def test_beam_up(scotty, combadge_version):
    directory = os.path.join(os.getcwd(), 'debug.log')
    email = 'damram@infinidat.com'
    beam_id = scotty.beam_up(directory=directory, email=email, combadge_version=combadge_version)
    beam = scotty.get_beam(beam_id)
    assert beam.directory == directory
    assert not beam.deleted

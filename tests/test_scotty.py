from scottypy.scotty import Scotty

import os
import pytest

COMBADGE_VERSIONS = ['v1', 'v2']

@pytest.fixture()
def scotty_url():
    return "http://scotty-staging.lab.gdc.il.infinidat.com"


@pytest.fixture()
def directory(tmpdir):
    with (tmpdir / "debug.log").open("w") as f:
        f.write("")
    return str(tmpdir)


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
def test_beam_up(scotty, combadge_version, directory):
    email = 'damram@infinidat.com'
    beam_id = scotty.beam_up(directory=directory, email=email, combadge_version=combadge_version)
    beam = scotty.get_beam(beam_id)
    assert beam.directory == directory
    assert not beam.deleted


@pytest.fixture
def host():
    return "gdc-qa-io-005"


remote_directories = [
    "/opt/infinidat/qa/logs/5704da68-588b-11ea-8e66-380025a4565f_0/001/vfs_logs/test/uproc/counters.nas--1",
    "/var/log/yum.log",
]


@pytest.mark.parametrize("combadge_version", COMBADGE_VERSIONS)
@pytest.mark.parametrize("remote_directory", remote_directories)
def test_initiate_beam(scotty, combadge_version, host, remote_directory):
    email = 'damram@infinidat.com'
    beam_id = scotty.initiate_beam(user="root", host=host, directory=remote_directory, email=email, combadge_version=combadge_version, stored_key="1")
    beam = scotty.get_beam(beam_id)
    while not beam.completed:
        beam.update()
    assert not beam.error, beam.error

# pylint: disable=redefined-outer-name
import time
import os

import pytest

from scottypy.scotty import Scotty

COMBADGE_VERSIONS = ["v1", "v2"]


@pytest.fixture()
def scotty_url():
    return os.environ.get("SCOTTY_URL", "http://scotty-staging.lab.gdc.il.infinidat.com")


@pytest.fixture()
def directory(tmpdir):
    with (tmpdir / "debug.log").open("w") as f:
        f.write("")
    sub_dir = tmpdir / "sub_dir"
    sub_dir.mkdir()
    with (sub_dir / "sub_debug.log").open("w") as f:
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


@pytest.mark.parametrize("combadge_version", COMBADGE_VERSIONS)
def test_beam_up(scotty, combadge_version, directory):
    email = "damram@infinidat.com"
    beam_id = scotty.beam_up(
        directory=directory, email=email, combadge_version=combadge_version
    )
    beam = scotty.get_beam(beam_id)
    assert beam.directory == directory
    assert not beam.deleted
    ext = "gz" if combadge_version == "v1" else "zst"
    expected_files = [
        file.format(ext=ext)
        for file in ['./debug.log.{ext}', './sub_dir/sub_debug.log.{ext}']
    ]
    assert [file.file_name for file in beam.get_files()] == expected_files


@pytest.mark.parametrize("combadge_version", COMBADGE_VERSIONS)
def test_beam_up_empty_directory(scotty, combadge_version, tmpdir):
    email = "damram@infinidat.com"
    directory = tmpdir
    beam_id = scotty.beam_up(
        directory=directory, email=email, combadge_version=combadge_version
    )
    beam = scotty.get_beam(beam_id)
    assert beam.directory == str(directory)
    assert len(beam.get_files()) == 0


linux_host = "gdc-qa-io-005"
windows_host = "gdc-qa-io-349"

remote_directories = [
    {
        "host": linux_host,
        "path": "/opt/infinidat/qa/logs/5704da68-588b-11ea-8e66-380025a4565f_0/001/vfs_logs/test/uproc/counters.nas--1",
        "expected_num_files": 0,
    },
    {"host": linux_host, "path": "/var/log/yum.log", "expected_num_files": 1},
    {"host": linux_host, "path": "/doesnt_exist", "expected_num_files": 0},
    {"host": windows_host, "path": r"C:\Users\root\Documents\sandbox\debug.log", "expected_num_files": 1},
]


@pytest.mark.parametrize("combadge_version", COMBADGE_VERSIONS)
@pytest.mark.parametrize("remote_directory", remote_directories)
def test_initiate_beam(scotty, combadge_version, remote_directory):
    if remote_directory["host"] == windows_host and combadge_version == "v1":
        raise pytest.skip("combadge v1 doesn't support windows")
    email = "damram@infinidat.com"
    beam_id = scotty.initiate_beam(
        user="root",
        host=remote_directory["host"],
        directory=remote_directory["path"],
        email=email,
        combadge_version=combadge_version,
        stored_key="1",
    )
    beam = scotty.get_beam(beam_id)
    while not beam.completed:
        beam.update()
        time.sleep(1)
    assert not beam.error, beam.error
    assert beam.directory == remote_directory["path"]
    assert len(beam.get_files()) == remote_directory["expected_num_files"]

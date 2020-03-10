# pylint: disable=redefined-outer-name
import contextlib
import datetime
import os
import sys
import urllib.parse
from functools import partial

import pytest
import requests_mock

from scottypy import Scotty
from scottypy.scotty import CombadgeRust, CombadgePython


class APICallLogger:
    def __init__(self):
        self.calls = []

    def log_call(self, request):
        try:
            json = request.json()
        except TypeError:
            json = None
        self.calls.append(dict(url=request.url, params=request.qs, json=json))

    @contextlib.contextmanager
    def isolate(self):
        old_calls = self.calls
        self.calls = []
        yield
        self.calls = old_calls

    def get_single_call_or_raise(self):
        assert len(self.calls) == 1, "Expected one call, got {calls}".format(calls=self.calls)
        return self.calls[0]

    def _assert_urls_equal(self, actual_url, expected_url):
        actual_url_parsed = urllib.parse.urlparse(actual_url)
        expected_url_parsed = urllib.parse.urlparse(expected_url)
        assert actual_url_parsed.scheme == expected_url_parsed.scheme
        assert actual_url_parsed.netloc == expected_url_parsed.netloc
        assert actual_url_parsed.path == expected_url_parsed.path
        assert urllib.parse.parse_qs(actual_url_parsed.query) == urllib.parse.parse_qs(expected_url_parsed.query)
        assert actual_url_parsed.fragment == expected_url_parsed.fragment

    def assert_urls_equal_to(self, expected_urls):
        assert len(expected_urls) == len(self.calls), "Expected {} calls, got {} instead".format(
            len(expected_urls), len(self.calls)
        )
        for call, expected_url in zip(self.calls, expected_urls):
            actual_url = call['url']
            self._assert_urls_equal(actual_url, expected_url)


def combadge(api_call_logger, request, context):
    api_call_logger.log_call(request)
    combadge_version = request.qs.get("combadge_version")[0]
    os_type = request.qs.get("os_type")[0]
    fixtures_folder = os.path.join(os.path.dirname(__file__), "fixtures")
    if combadge_version == "v1":
        file_name = "combadge.py"
    elif combadge_version == "v2" and os_type == "linux":
        file_name = "combadge"
    else:
        raise ValueError("Unknown combadge version {combadge_version}".format(
            combadge_version=combadge_version
        ))
    with open(os.path.join(fixtures_folder, file_name), "rb") as f:
        return f.read()


def beams(api_call_logger, request, context):
    api_call_logger.log_call(request)
    json = request.json()
    return {
        "beam": {
            "id": 666,
            "start": datetime.datetime(year=2020, month=2, day=27).isoformat() + "Z",
            "size": 0,
            "host": json["beam"].get("host"),
            "comment": json["beam"].get("comment"),
            "directory": json["beam"].get("directory"),
            "initiator": json["beam"].get("user"),
            "error": None,
            "combadge_contacted": False,
            "pending_deletion": False,
            "completed": False,
            "deleted": False,
            "pins": [],
            "tags": [],
            "associated_issues": [],
            "purge_time": 0,
        }
    }


@pytest.fixture
def api_call_logger():
    return APICallLogger()


@pytest.fixture
def scotty(api_call_logger):
    url = "http://mock-scotty"
    with requests_mock.Mocker() as m:
        m.get("{url}/combadge".format(url=url), content=partial(combadge, api_call_logger))
        m.get("{url}/info".format(url=url), json={"transporter": "mock-transporter"})
        m.post("{url}/beams".format(url=url), json=partial(beams, api_call_logger))
        yield Scotty(url)


@pytest.fixture
def directory(tmpdir):
    with (tmpdir / "debug.log").open("w") as f:
        f.write("debug debug")
    return str(tmpdir)


def test_prefetch_combadge_v1(scotty):
    scotty.prefetch_combadge("v1")
    assert isinstance(scotty._combadge, CombadgePython)


def test_prefetch_combadge_v2(scotty):
    scotty.prefetch_combadge("v2")
    assert isinstance(scotty._combadge, CombadgeRust)


def test_prefetch_combadge_v1_and_then_v2(scotty):
    scotty.prefetch_combadge("v1")
    assert isinstance(scotty._combadge, CombadgePython)
    scotty.prefetch_combadge("v2")
    assert isinstance(scotty._combadge, CombadgeRust)


@pytest.mark.parametrize("combadge_version", ["v1", "v2"])
def test_beam_up(scotty, directory, combadge_version):
    scotty.beam_up(
        directory=directory, combadge_version=combadge_version,
    )
    _validate_beam_up(combadge_version=combadge_version, directory=directory)


def _validate_beam_up(*, directory, combadge_version):
    combadge_identifier = sys.platform if combadge_version == "v2" else "v1"
    with open(os.path.join(directory, "output")) as f:
        expected = "beam_id=666, path={directory}, transporter_addr=mock-transporter, version={combadge_identifier}".format(
            directory=directory, combadge_identifier=combadge_identifier
        )
        assert f.read().strip() == expected


@pytest.mark.parametrize("combadge_version", ["v1", "v2"])
def test_prefetch_and_then_beam_up_doesnt_download_combadge_again(scotty, directory, combadge_version, api_call_logger):
    with api_call_logger.isolate():
        scotty.prefetch_combadge(combadge_version=combadge_version)
        expected_combadge_url = (
            "http://mock-scotty/"
            "combadge?"
            "combadge_version={combadge_version}"
            "&os_type=linux"
            .format(combadge_version=combadge_version)
        )
        api_call_logger.assert_urls_equal_to([expected_combadge_url])
    with api_call_logger.isolate():
        scotty.beam_up(
            directory=directory, combadge_version=combadge_version,
        )
        api_call_logger.assert_urls_equal_to(["http://mock-scotty/beams"])
        _validate_beam_up(combadge_version=combadge_version, directory=directory)


def test_prefetch_and_then_beam_different_version_downloads_combadge_again(scotty, directory, api_call_logger):
    with api_call_logger.isolate():
        scotty.prefetch_combadge(combadge_version='v1')
        expected_combadge_url = "http://mock-scotty/combadge?combadge_version=v1&os_type=linux"
        api_call_logger.assert_urls_equal_to([expected_combadge_url])
    with api_call_logger.isolate():
        scotty.beam_up(
            directory=directory, combadge_version='v2',
        )
        api_call_logger.assert_urls_equal_to([
            "http://mock-scotty/beams",
            "http://mock-scotty/combadge?combadge_version=v2&os_type=linux",
        ])
        _validate_beam_up(combadge_version='v2', directory=directory)


def test_prefetch_and_then_beam_different_version_twice_downloads_combadge_again_once(scotty, directory, api_call_logger):
    with api_call_logger.isolate():
        scotty.prefetch_combadge(combadge_version='v1')
        expected_combadge_url = "http://mock-scotty/combadge?combadge_version=v1&os_type=linux"
        api_call_logger.assert_urls_equal_to([expected_combadge_url])
    with api_call_logger.isolate():
        scotty.beam_up(
            directory=directory, combadge_version='v2',
        )
        api_call_logger.assert_urls_equal_to([
            "http://mock-scotty/beams",
            "http://mock-scotty/combadge?combadge_version=v2&os_type=linux",
        ])
        _validate_beam_up(combadge_version='v2', directory=directory)

    with api_call_logger.isolate():
        scotty.beam_up(
            directory=directory, combadge_version='v2',
        )
        api_call_logger.assert_urls_equal_to(["http://mock-scotty/beams"])
        _validate_beam_up(combadge_version='v2', directory=directory)


@pytest.mark.parametrize("combadge_version", ["v1", "v2"])
def test_prefetch_and_then_beam_up_without_explicit_version_uses_prefetched(scotty, directory, api_call_logger, combadge_version):
    with api_call_logger.isolate():
        scotty.prefetch_combadge(combadge_version=combadge_version)
        expected_combadge_url = "http://mock-scotty/combadge?combadge_version={combadge_version}&os_type=linux".format(
            combadge_version=combadge_version
        )
        api_call_logger.assert_urls_equal_to([expected_combadge_url])
    with api_call_logger.isolate():
        scotty.beam_up(
            directory=directory
        )
        api_call_logger.assert_urls_equal_to(["http://mock-scotty/beams"])
        _validate_beam_up(combadge_version=combadge_version, directory=directory)


@pytest.mark.parametrize("combadge_version", ["v1", "v2"])
def test_prefetch_and_then_initiate_beam_without_explicit_version_uses_prefetched(scotty, directory, api_call_logger, combadge_version):
    with api_call_logger.isolate():
        scotty.prefetch_combadge(combadge_version=combadge_version)
        expected_combadge_url = "http://mock-scotty/combadge?combadge_version={combadge_version}&os_type=linux".format(
            combadge_version=combadge_version
        )
        api_call_logger.assert_urls_equal_to([expected_combadge_url])
    with api_call_logger.isolate():
        scotty.initiate_beam(
            user="mock-user",
            host="mock-host",
            stored_key="1",
            directory=directory
        )
        assert api_call_logger.get_single_call_or_raise()["json"]["beam"]["combadge_version"] == combadge_version


@pytest.mark.parametrize("combadge_version", ["v1", "v2"])
@pytest.mark.parametrize("directory", ["C:\\Users\\Documents\\test", "/tmp/test"])
def test_initiate_beam(scotty, directory, combadge_version, api_call_logger):
    user = "mock-user"
    host = "mock-host"
    stored_key = "1"
    beam = scotty.initiate_beam(
        user=user,
        host=host,
        directory=directory,
        combadge_version=combadge_version,
        stored_key=stored_key,
        return_beam_object=True,
    )
    assert beam.initiator_id == user
    assert beam.host == host
    assert beam.directory == directory
    assert api_call_logger.get_single_call_or_raise() == dict(
        url="http://mock-scotty/beams",
        params={},
        json={
            "beam": {
                "directory": directory,
                "host": host,
                "user": user,
                "ssh_key": None,
                "stored_key": stored_key,
                "password": None,
                "type": None,
                "auth_method": "stored_key",
                "combadge_version": combadge_version,
            }
        },
    )

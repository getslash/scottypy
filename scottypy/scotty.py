import abc
import errno
import itertools
import json
import logging
import os
import socket
import stat
import subprocess
import sys
import tempfile
import types
import typing
from tempfile import NamedTemporaryFile
from uuid import uuid4

import emport
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from .beam import Beam
from .exc import PathNotExists
from .file import File
from .types import JSON
from .utils import raise_for_status

_SLEEP_TIME = 10
_NUM_OF_RETRIES = (60 // _SLEEP_TIME) * 15
_TIMEOUT = 5
_DEFAULT_COMBADGE_VERSION = "v2"
logger = logging.getLogger("scotty")  # type: logging.Logger


class Combadge:
    @property
    @abc.abstractmethod
    def version(self) -> str:
        pass

    @classmethod
    @abc.abstractmethod
    def from_response(cls, response: requests.Response) -> "Combadge":
        pass

    @abc.abstractmethod
    def remove(self) -> None:
        pass

    @abc.abstractmethod
    def run(self, *, beam_id: int, directory: str, transporter_host: str) -> None:
        pass


class CombadgePython(Combadge):
    version = "v1"  # type: str

    def __init__(self, combadge_module: types.ModuleType):
        self._combadge_module = combadge_module

    @classmethod
    def from_response(cls, response: requests.Response) -> "CombadgePython":
        with NamedTemporaryFile(mode="w", suffix=".py", delete=False) as combadge_file:
            combadge_file.write(response.text)
            combadge_file.flush()
        return cls(emport.import_file(combadge_file.name))

    def remove(self) -> None:
        os.remove(self._combadge_module.__file__)

    def run(self, *, beam_id: int, directory: str, transporter_host: str) -> None:
        self._combadge_module.beam_up(beam_id, directory, transporter_host)  # type: ignore


class CombadgeRust(Combadge):
    version = "v2"  # type: str

    def __init__(self, file_name: str):
        self._file_name = file_name

    @classmethod
    def _generate_random_combadge_name(cls, string_length: int) -> str:
        random_string = str(uuid4())[:string_length]
        return "combadge_{random_string}".format(random_string=random_string)

    @classmethod
    def _get_local_combadge_path(cls) -> str:
        combadge_name = cls._generate_random_combadge_name(string_length=10)
        local_combadge_dir = tempfile.gettempdir()
        return os.path.join(local_combadge_dir, combadge_name)

    @classmethod
    def from_response(cls, response: requests.Response) -> "CombadgeRust":
        local_combadge_path = cls._get_local_combadge_path()
        with open(local_combadge_path, "wb") as combadge_file:
            for chunk in response.iter_content(chunk_size=1024):
                combadge_file.write(chunk)
            st = os.stat(local_combadge_path)
            os.chmod(local_combadge_path, st.st_mode | stat.S_IEXEC)
            return cls(combadge_file.name)

    def remove(self) -> None:
        try:
            os.remove(self._file_name)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

    def run(self, *, beam_id: int, directory: str, transporter_host: str) -> None:
        subprocess.run(
            [
                self._file_name,
                "-b",
                str(beam_id),
                "-p",
                directory,
                "-t",
                transporter_host,
            ],
            check=False,
        )


class Scotty(object):
    """Main class that communicates with Scotty.

    :param str url: The base URL of Scotty."""

    def __init__(self, url: str, retry_times: int = 3, backoff_factor: int = 2):
        self._url = url
        self._session = requests.Session()
        self._session.headers.update(
            {"Accept-Encoding": "gzip", "Content-Type": "application/json"}
        )
        self._session.mount(
            url,
            HTTPAdapter(
                max_retries=Retry(
                    total=retry_times,
                    status_forcelist=[502, 504],
                    backoff_factor=backoff_factor,
                )
            ),
        )
        self._combadge = None  # type: typing.Optional[Combadge]

    def prefetch_combadge(
        self, combadge_version: str = _DEFAULT_COMBADGE_VERSION
    ) -> None:
        """Prefetch the combadge to a temporary file. Future beams will use that combadge
        instead of having to re-download it."""
        self._get_combadge(combadge_version=combadge_version)

    def remove_combadge(self) -> None:
        if self._combadge:
            self._combadge.remove()

    def _get_combadge(self, combadge_version: str) -> "Combadge":
        """Get the combadge from the memory if it has been prefetched. Otherwise, download
        it from Scotty"""
        if self._combadge and self._combadge.version == combadge_version:
            return self._combadge

        response = self._session.get(
            "{}/combadge".format(self._url),
            timeout=_TIMEOUT,
            params={
                "combadge_version": combadge_version,
                "os_type": sys.platform,
            },
        )
        raise_for_status(response)

        if combadge_version == "v1":  # python version
            self._combadge = CombadgePython.from_response(response)
        elif combadge_version == "v2":  # rust version
            self._combadge = CombadgeRust.from_response(response)
        else:
            raise Exception("Wrong combadge type")
        return self._combadge

    @property
    def session(self) -> requests.Session:
        return self._session

    def __del__(self) -> None:
        self._session.close()

    @property
    def url(self) -> str:
        return self._url

    def beam_up(
        self,
        directory: str,
        combadge_version: typing.Optional[str] = None,
        email: typing.Optional[str] = None,
        beam_type: typing.Optional[str] = None,
        tags: typing.Optional[typing.List[str]] = None,
        return_beam_object: bool = False,
    ) -> typing.Union["Beam", int]:
        """Beam up the specified local directory to Scotty.

        :param str directory: Local directory to beam.
        :param str email: Your email. If unspecified, the initiator of the beam will be anonymous.
        :param list tags: An optional list of tags to be associated with the beam.
        :param bool return_beam_object: If set to True, return a :class:`.Beam` instance.

        :return: the beam id."""
        if not os.path.exists(directory):
            raise PathNotExists(directory)
        combadge_version = self._get_combadge_version(version_override=combadge_version)
        directory = os.path.abspath(directory)
        response = self._session.get("{}/info".format(self._url), timeout=_TIMEOUT)
        raise_for_status(response)
        transporter_host = response.json()["transporter"]

        beam = {
            "directory": directory,
            "host": socket.gethostname(),
            "auth_method": "independent",
            "type": beam_type,
            "combadge_version": combadge_version,
            "os_type": sys.platform,
        }  # type: JSON

        if email:
            beam["email"] = email

        if tags:
            beam["tags"] = tags

        response = self._session.post(
            "{}/beams".format(self._url),
            data=json.dumps({"beam": beam}),
            timeout=_TIMEOUT,
        )
        raise_for_status(response)

        beam_data = response.json()
        beam_id = beam_data["beam"]["id"]  # type: int

        combadge = self._get_combadge(combadge_version)
        combadge.run(
            beam_id=beam_id, directory=directory, transporter_host=transporter_host
        )

        if return_beam_object:
            return Beam.from_json(self, beam_data["beam"])
        else:
            return beam_id

    def _get_combadge_version(
        self, version_override: typing.Optional[str] = None
    ) -> str:
        return (
            version_override
            or (self._combadge and self._combadge.version)
            or _DEFAULT_COMBADGE_VERSION
        )

    def initiate_beam(
        self,
        user: str,
        host: str,
        directory: str,
        password: typing.Optional[str] = None,
        rsa_key: typing.Optional[str] = None,
        email: typing.Optional[str] = None,
        beam_type: typing.Optional[str] = None,
        stored_key: typing.Optional[str] = None,
        tags: typing.Optional[typing.List[str]] = None,
        return_beam_object: bool = False,
        combadge_version: typing.Optional[str] = None,
    ) -> typing.Union["Beam", int]:
        """Order scotty to beam the specified directory from the specified host.

        :param str user: The username in the remote machine.
        :param str host: The remote host.
        :param str directory: Remote directory to beam.
        :param str password: Password of the username.
        :param str rsa_key: RSA private key for authentication.
        :param str email: Your email. If unspecified, the initiator of the beam will be anonymous.
        :param str beam_type: ID of the beam type as defined in Scotty.
        :param str stored_key: An ID of a key stored in Scotty.
        :param list tags: An optional list of tags to be associated with the beam.
        :param bool return_beam_object: If set to True, return a :class:`.Beam` instance.
        :param str combadge_version: The combagd version to be used when beaming

        Either `password`, `rsa_key` or `stored_key` should be specified, but only one of them.

        :return: the beam id."""
        combadge_version = self._get_combadge_version(version_override=combadge_version)
        if len([x for x in (password, rsa_key, stored_key) if x]) != 1:
            raise Exception(
                "Either password, rsa_key or stored_key should be specified"
            )

        if rsa_key:
            auth_method = "rsa"
        elif password:
            auth_method = "password"
        elif stored_key:
            auth_method = "stored_key"
        else:
            raise Exception()

        beam = {
            "directory": directory,
            "host": host,
            "user": user,
            "ssh_key": rsa_key,
            "stored_key": stored_key,
            "password": password,
            "type": beam_type,
            "auth_method": auth_method,
            "combadge_version": combadge_version,
        }  # type: JSON

        if tags:
            beam["tags"] = tags

        if email:
            beam["email"] = email

        response = self._session.post(
            "{0}/beams".format(self._url),
            data=json.dumps({"beam": beam}),
            timeout=_TIMEOUT,
        )
        raise_for_status(response)

        beam_data = response.json()

        if return_beam_object:
            return Beam.from_json(self, beam_data["beam"])
        else:
            beam_id = beam_data["beam"]["id"]  # type: int
            return beam_id

    def add_tag(self, beam_id: int, tag: str) -> None:
        """Add the specified tag on the specified beam id.

        :param int beam_id: Beam ID.
        :param str tag: Tag name."""
        response = self._session.post(
            "{0}/beams/{1}/tags/{2}".format(self._url, beam_id, tag), timeout=_TIMEOUT
        )
        raise_for_status(response)

    def remove_tag(self, beam_id: int, tag: str) -> None:
        """Remove the specified tag from the specified beam id.

        :param int beam_id: Beam ID.
        :param str tag: Tag name."""
        response = self._session.delete(
            "{0}/beams/{1}/tags/{2}".format(self._url, beam_id, tag), timeout=_TIMEOUT
        )
        raise_for_status(response)

    def get_beam(self, beam_id: typing.Union[str, int]) -> "Beam":
        """Retrieve details about the specified beam.

        :param int beam_id: Beam ID or tag
        :rtype: :class:`.Beam`"""
        response = self._session.get(
            "{0}/beams/{1}".format(self._url, beam_id), timeout=_TIMEOUT
        )
        raise_for_status(response)

        json_response = response.json()
        return Beam.from_json(self, json_response["beam"])

    def get_files(
        self, beam_id: int, filter_: typing.Optional[str] = None
    ) -> typing.List[File]:
        response = self._session.get(
            "{0}/files".format(self._url),
            params={"beam_id": beam_id, "filter": filter_},
            timeout=_TIMEOUT,
        )
        raise_for_status(response)
        return [File.from_json(self._session, f) for f in response.json()["files"]]

    def get_file(self, file_id: int) -> File:
        """Retrieve details about the specified file.

        :param int file_id: File ID.
        :rtype: :class:`.File`"""
        response = self._session.get(
            "{0}/files/{1}".format(self._url, file_id), timeout=_TIMEOUT
        )
        raise_for_status(response)

        json_response = response.json()
        return File.from_json(self._session, json_response["file"])

    def get_beams_by_tag(self, tag: str) -> typing.List[Beam]:
        """Retrieve the list of beams associated with the specified tag.

        :param str tag: The name of the tag.
        :return: a list of :class:`.Beam` objects.
        """

        response = self._session.get(
            "{0}/beams?tag={1}".format(self._url, tag), timeout=_TIMEOUT
        )
        raise_for_status(response)

        ids = (b["id"] for b in response.json()["beams"])
        return [self.get_beam(id_) for id_ in ids]

    def get_beams_by_issue(self, issue: str) -> typing.List[Beam]:
        """Retrieve the list of beams associated with the specified issue.

        :param str issue: The name of the issue.
        :return: a list of :class:`.Beam` objects.
        """
        beams = []  # type: typing.List[Beam]
        per_page = 50
        for page in itertools.count(1):
            response = self._session.get(
                "{0}/beams?issue={1}&page={2}&per_page={3}".format(
                    self._url, issue, page, per_page
                ),
                timeout=_TIMEOUT,
            )
            raise_for_status(response)

            response_json = response.json()
            ids = (b["id"] for b in response_json["beams"])
            beams.extend(self.get_beam(id_) for id_ in ids)
            if page >= response_json["meta"]["total_pages"]:
                break
        return beams

    def sanity_check(self) -> None:
        """Check if this instance of Scotty is functioning. Raise an exception if something's wrong"""
        response = requests.get("{0}/info".format(self._url))
        raise_for_status(response)
        info = json.loads(response.text)
        assert "version" in info

    def create_tracker(
        self, name: str, tracker_type: str, url: str, config: JSON
    ) -> int:
        data = {
            "tracker": {
                "name": name,
                "type": tracker_type,
                "url": url,
                "config": json.dumps(config),
            }
        }
        response = self._session.post(
            "{}/trackers".format(self._url), data=json.dumps(data), timeout=_TIMEOUT
        )
        raise_for_status(response)
        tracker_id = response.json()["tracker"]["id"]  # type: int
        return tracker_id

    def get_tracker_by_name(self, name: str) -> typing.Optional[JSON]:
        try:
            response = self._session.get(
                "{}/trackers/by_name/{}".format(self._url, name), timeout=_TIMEOUT
            )
            raise_for_status(response)
            tracker = response.json()["tracker"]  # type: JSON
            return tracker
        except requests.exceptions.HTTPError:
            return None

    def get_tracker_id(self, name: str) -> int:
        response = self._session.get(
            "{}/trackers/by_name/{}".format(self._url, name), timeout=_TIMEOUT
        )
        raise_for_status(response)
        tracker_id = response.json()["tracker"]["id"]  # type: int
        return tracker_id

    def create_issue(self, tracker_id: int, id_in_tracker: str) -> int:
        data = {
            "issue": {
                "tracker_id": tracker_id,
                "id_in_tracker": id_in_tracker,
            }
        }
        response = self._session.post(
            "{}/issues".format(self._url), data=json.dumps(data), timeout=_TIMEOUT
        )
        raise_for_status(response)
        issue_id = response.json()["issue"]["id"]  # type: int
        return issue_id

    def delete_issue(self, issue_id: int) -> None:
        response = self._session.delete(
            "{}/issues/{}".format(self._url, issue_id), timeout=_TIMEOUT
        )
        raise_for_status(response)

    def get_issue_by_tracker(
        self, tracker_id: int, id_in_tracker: str
    ) -> typing.Optional[JSON]:
        params = {
            "tracker_id": tracker_id,
            "id_in_tracker": id_in_tracker,
        }
        response = self._session.get(
            "{}/issues/get_by_tracker".format(self._url),
            params=params,
            timeout=_TIMEOUT,
        )
        try:
            raise_for_status(response)
            issue = response.json()["issue"]  # type: JSON
            return issue
        except requests.exceptions.HTTPError:
            return None

    def delete_tracker(self, tracker_id: int) -> None:
        response = self._session.delete(
            "{}/trackers/{}".format(self._url, tracker_id), timeout=_TIMEOUT
        )
        raise_for_status(response)

    def update_tracker(
        self,
        tracker_id: int,
        name: typing.Optional[str] = None,
        url: typing.Optional[str] = None,
        config: typing.Optional[JSON] = None,
    ) -> None:
        data = {}

        if name:
            data["name"] = name

        if url:
            data["url"] = url

        if config:
            data["config"] = json.dumps(config)

        response = self._session.put(
            "{}/trackers/{}".format(self._url, tracker_id),
            data=json.dumps({"tracker": data}),
            timeout=_TIMEOUT,
        )
        raise_for_status(response)

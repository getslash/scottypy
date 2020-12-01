import json
import typing

import dateutil.parser
from pact import Pact

from scottypy.utils import raise_for_status

from .types import JSON

if typing.TYPE_CHECKING:
    from datetime import datetime

    from .file import File
    from .scotty import Scotty


class Beam(object):
    """A class representing a single beam.

    :ivar id: The ID of the beam.
    :ivar initiator_id: The user ID of the beam initiator.
    :ivar start: When was the beam started.
    :ivar deleted: Is the beam deleted.
    :ivar completed: Is the beam completed.
    :ivar pins: A list of user IDs which pin this beam.
    :ivar host: The host from which the files were beamed up.
    :ivar error: A string representing a possible error that occurred during this beam.
    :ivar directory: The path to the directory that was beamed.
    :ivar purge_time: The number of days left for this beam to exist if it has no pinners.
    :ivar size: The total size of the beam in bytes.
    """

    def __init__(
        self,
        scotty: "Scotty",
        id_: int,
        file_ids: typing.List[int],
        initiator_id: int,
        start: "datetime",
        deleted: bool,
        completed: bool,
        pins: typing.List[int],
        host: str,
        error: str,
        directory: str,
        purge_time: int,
        size: int,
        comment: str,
        associated_issues: typing.List[int],
    ):
        self.id = id_
        self._file_ids = file_ids
        self.initiator_id = initiator_id
        self.start = start
        self.deleted = deleted
        self.completed = completed
        self.pins = pins
        self.host = host
        self.error = error
        self.directory = directory
        self.purge_time = purge_time
        self.size = size
        self.associated_issues = associated_issues
        self._scotty = scotty
        self._comment = comment

    @property
    def comment(self) -> str:
        return self._comment

    def update(self) -> None:
        """Update the status of the beam object"""
        response = self._scotty.session.get(
            "{0}/beams/{1}".format(self._scotty.url, self.id)
        )
        raise_for_status(response)
        beam_obj = response.json()["beam"]

        self._file_ids = beam_obj["files"]
        self.deleted = beam_obj["deleted"]
        self.completed = beam_obj["completed"]
        self.pins = beam_obj["pins"]
        self.error = beam_obj["error"]
        self.purge_time = beam_obj["purge_time"]
        self.associated_issues = beam_obj["associated_issues"]
        self.size = beam_obj["size"]
        self._comment = beam_obj["comment"]

    @classmethod
    def from_json(cls, scotty: "Scotty", json_node: JSON) -> "Beam":
        return cls(
            scotty,
            json_node["id"],
            json_node.get("files", []),
            json_node["initiator"],
            dateutil.parser.parse(json_node["start"]),
            json_node["deleted"],
            json_node["completed"],
            json_node["pins"],
            json_node["host"],
            json_node["error"],
            json_node["directory"],
            json_node["purge_time"],
            json_node["size"],
            json_node["comment"],
            json_node["associated_issues"],
        )

    def iter_files(self) -> typing.Iterator["File"]:
        """Iterate the beam files one by one, yielding :class:`.File` objects
        This function might be slow when used with beams containing large number
        of file. Consider using :func:`.get_files` instead."""
        for id_ in self._file_ids:
            yield self._scotty.get_file(id_)

    def get_files(self, filter_: typing.Optional[str] = None) -> typing.List["File"]:
        """Get a list of :class:`.File` instances representing the beam files.

        :ivar filter_: Optional filter string. When given, only files which their name contains the filter will be returned."""
        return self._scotty.get_files(self.id, filter_)

    def set_comment(self, comment: str) -> None:
        data = {"beam": {"comment": comment}}
        response = self._scotty.session.put(
            "{0}/beams/{1}".format(self._scotty.url, self.id), data=json.dumps(data)
        )
        raise_for_status(response)
        self._comment = comment

    def set_issue_association(self, issue_id: str, associated: bool) -> None:
        raise_for_status(
            self._scotty.session.request(
                "POST" if associated else "DELETE",
                "{0}/beams/{1}/issues/{2}".format(self._scotty.url, self.id, issue_id),
            )
        )

    def _check_finish(self) -> bool:
        self.update()
        return self.completed

    def get_pact(self) -> Pact:
        """Get a Pact instance. The pact is finished when the beam has been completed"""
        pact = Pact("Waiting for beam {}".format(self.id))
        pact.until(self._check_finish)
        return pact

    def delete(self) -> None:
        response = self._scotty.session.delete(
            "{0}/beams/{1}".format(self._scotty.url, self.id)
        )
        raise_for_status(response)

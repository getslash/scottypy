import json
import dateutil.parser


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
    def __init__(self, scotty, id_, file_ids, initiator_id, start, deleted, completed, pins, host, error, directory,
                 purge_time, size, comment, associated_issues):
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
    def comment(self):
        return self._comment

    def update(self):
        """Update the status of the beam object"""
        response = self._scotty.session.get("{0}/beams/{1}".format(self._scotty.url, self.id))
        response.raise_for_status()
        beam_obj = response.json()['beam']

        self._file_ids = beam_obj['files']
        self.deleted = beam_obj['deleted']
        self.completed = beam_obj['completed']
        self.pins = beam_obj['pins']
        self.error = beam_obj['error']
        self.purge_time = beam_obj['purge_time']
        self.associated_issues = beam_obj['associated_issues']
        self.size = beam_obj['size']
        self._comment = beam_obj['comment']

    @classmethod
    def from_json(cls, scotty, json_node):
        return cls(
            scotty,
            json_node['id'],
            json_node.get('files', []),
            json_node['initiator'],
            dateutil.parser.parse(json_node['start']),
            json_node['deleted'],
            json_node['completed'],
            json_node['pins'],
            json_node['host'],
            json_node['error'],
            json_node['directory'],
            json_node['purge_time'],
            json_node['size'],
            json_node['comment'],
            json_node['associated_issues'])

    def iter_files(self):
        """Iterate the beam files one by one, yielding :class:`.File` objects
        This function might be slow when used with beams containing large number
        of file. Consider using :func:`.get_files` instead."""
        for id_ in self._file_ids:
            yield self._scotty.get_file(id_)

    def get_files(self, filter_=None):
        """Get a list of :class:`.File` instances representing the beam files.

        :ivar filter_: Optional filter string. When given, only files which their name contains the filter will be returned."""
        return self._scotty.get_files(self.id, filter_)

    def set_comment(self, comment):
        data = {'beam': {'comment': comment}}
        response = self._scotty.session.put(
            "{0}/beams/{1}".format(self._scotty.url, self.id),
            data=json.dumps(data))
        response.raise_for_status()
        self._comment = comment

    def set_issue_association(self, issue_id, associated):
        self._scotty.session.request(
            'POST' if associated else 'DELETE',
            "{0}/beams/{1}/issues/{2}".format(self._scotty.url, self.id, issue_id)).raise_for_status()

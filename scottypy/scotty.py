import dateutil.parser
import emport
import json
import os
import requests
import shutil
import socket
import tempfile
import logging
from datetime import datetime
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from tempfile import NamedTemporaryFile

_CHUNK_SIZE = 1024 ** 2 * 4
_SLEEP_TIME = 10
_NUM_OF_RETRIES = (60 // _SLEEP_TIME) * 15
logger = logging.getLogger("scotty") # type: logging.Logger


epoch = datetime.utcfromtimestamp(0)
def _to_epoch(d):
    return (d - epoch.replace(tzinfo=d.tzinfo)).total_seconds()


class PathNotExists(Exception):
    def __init__(self, path):
        super(PathNotExists, self).__init__("{} does not exist".format(path))


class NotOverwriting(Exception):
    def __init__(self, file_):
        super(NotOverwriting, self).__init__()
        self.file = file_


class File(object):
    """A class representing a single file

    :ivar id: The ID of the file.
    :ivar file_name: The file name.
    :ivar status: A string representing the status of the file.
    :ivar storage_name: The file name in Scotty's file system.
    :ivar size: The size of the file in bytes.
    :ivar url: A URL for downloading the file."""
    def __init__(self, session, id_, file_name, status, storage_name, size, url, mtime):

        self.id = id_
        self._session = session
        self.file_name = file_name
        self.status = status
        self.storage_name = storage_name
        self.size = size
        self.url = url
        self.mtime = mtime

    @classmethod
    def from_json(cls, session, json_node):
        raw_mtime = json_node.get("mtime")
        mtime = None if raw_mtime is None else dateutil.parser.parse(raw_mtime)
        return cls(session, json_node['id'], json_node['file_name'], json_node['status'], json_node['storage_name'],
                   json_node['size'], json_node['url'], mtime)

    def stream_to(self, fileobj):
        """Fetch the file content from the server and write it to fileobj"""
        response = self._session.get(self.url, stream=True)
        response.raise_for_status()

        for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
            fileobj.write(chunk)

    def download(self, directory=".", overwrite=False):
        """Download the file to the specified directory, retaining its name"""
        subdir, file_ = os.path.split(self.file_name)
        subdir = os.path.join(directory, subdir)
        file_ = os.path.join(subdir, file_)

        if file_.endswith(".gz") and not self.url.endswith(".gz"):
            file_ = file_[:-3]

        if not os.path.isdir(subdir):
            os.makedirs(subdir)

        if os.path.isfile(file_) and not overwrite:
            raise NotOverwriting(file_)

        with open(file_, "wb") as f:
            self.stream_to(f)

        if self.mtime is not None:
            mtime = _to_epoch(self.mtime)
            os.utime(file_, (mtime, mtime))

    def link(self, storage_base, dest):
        source_path = os.path.join(storage_base, self.storage_name)
        link_path = os.path.join(dest, self.file_name)
        link_dir = os.path.split(link_path)[0]

        if not os.path.isdir(link_dir):
            os.makedirs(link_dir)

        os.symlink(source_path, link_path)
        if self.mtime is not None:
            mtime = _to_epoch(self.mtime)
            os.utime(link_path, times=(mtime, mtime), follow_symlinks=False)


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
            json_node['files'],
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


class TempDir(object):
    def __init__(self):
        self._path = None

    def __enter__(self):
        self._path = tempfile.mkdtemp()
        return self._path

    def __exit__(self, _1, _2, _3):
        shutil.rmtree(self._path)


class Scotty(object):
    """Main class that communicates with Scotty.

    :param str url: The base URL of Scotty."""
    def __init__(self, url, retry_times=3, backoff_factor=2):
        self._url = url
        self._session = requests.Session()
        self._session.headers.update({
            'Accept-Encoding': 'gzip',
            'Content-Type': 'application/json'})
        self._session.mount(
            url, HTTPAdapter(
                max_retries=Retry(total=retry_times, status_forcelist=[502, 504], backoff_factor=backoff_factor)))
        self._combadge = None

    def prefetch_combadge(self):
        """Prefetch the combadge to a temporary file. Future beams will use that combadge
        instead of having to re-download it."""
        self._combadge = self._get_combadge()

    def _get_combadge(self):
        """Get the combadge from the memory if it has been prefetched. Otherwise, download
        it from Scotty"""
        if self._combadge:
            return self._combadge

        logger.critical("Fetching combadge")
        with NamedTemporaryFile(mode="w", suffix='.py') as combadge_file:
            response = self._session.get("{0}/static/assets/combadge.py".format(self._url))
            response.raise_for_status()
            combadge_file.write(response.text)
            combadge_file.flush()
            return emport.import_file(combadge_file.name)

    @property
    def session(self):
        return self._session

    def __del__(self):
        self._session.close()

    @property
    def url(self):
        return self._url

    def beam_up(self, directory, email=None, beam_type=None):
        """Beam up the specified local directory to Scotty.

        :param str directory: Local directory to beam.
        :param str email: Your email. If unspecified, the initiator of the beam will be anonymous.
        :return: the beam id."""
        if not os.path.exists(directory):
            raise PathNotExists(directory)

        response = self._session.get("{0}/info".format(self._url))
        response.raise_for_status()
        transporter_host = response.json()['transporter']

        beam = {
            'directory': os.path.abspath(directory),
            'host': socket.gethostname(),
            'auth_method': 'independent',
            'type': beam_type
        }

        if email:
            beam['email'] = email

        response = self._session.post("{0}/beams".format(self._url), data=json.dumps({'beam': beam}))
        response.raise_for_status()

        beam_data = response.json()
        beam_id = beam_data['beam']['id']

        self._get_combadge().beam_up(beam_id, directory, transporter_host)

        return beam_id

    def initiate_beam(self, user, host, directory, password=None, rsa_key=None, email=None, beam_type=None, stored_key=None):
        """Order scotty to beam the specified directory from the specified host.

        :param str user: The username in the remote machine.
        :param str host: The remote host.
        :param str directory: Remote directory to beam.
        :param str password: Password of the username.
        :param str rsa_key: RSA private key for authentication.
        :param str email: Your email. If unspecified, the initiator of the beam will be anonymous.
        :param str beam_type: ID of the beam type as defined in Scotty.
        :param str stored_key: An ID of a key stored in Scotty.

        Either `password`, `rsa_key` or `stored_key` should be specified, but only one of them.

        :return: the beam id."""
        if len([x for x in (password, rsa_key, stored_key) if x]) != 1:
            raise Exception("Either password, rsa_key or stored_key should be specified")

        if rsa_key:
            auth_method = 'rsa'
        elif password:
            auth_method = 'password'
        elif stored_key:
            auth_method = 'stored_key'
        else:
            raise Exception()


        beam = {
            'directory': os.path.abspath(directory),
            'host': host,
            'user': user,
            'ssh_key': rsa_key,
            'stored_key': stored_key,
            'password': password,
            'type': beam_type,
            'auth_method': auth_method
        }

        if email:
            beam['email'] = email

        response = self._session.post("{0}/beams".format(self._url), data=json.dumps({'beam': beam}))
        response.raise_for_status()

        beam_data = response.json()
        return beam_data['beam']['id']

    def add_tag(self, beam_id, tag):
        """Add the specified tag on the specified beam id.

        :param int beam_id: Beam ID.
        :param str tag: Tag name."""
        response = self._session.post("{0}/beams/{1}/tags/{2}".format(self._url, beam_id, tag))
        response.raise_for_status()

    def remove_tag(self, beam_id, tag):
        """Remove the specified tag from the specified beam id.

        :param int beam_id: Beam ID.
        :param str tag: Tag name."""
        response = self._session.delete("{0}/beams/{1}/tags/{2}".format(self._url, beam_id, tag))
        response.raise_for_status()

    def get_beam(self, beam_id):
        """Retrieve details about the specified beam.

        :param int beam_id: Beam ID.
        :rtype: :class:`.Beam`"""
        response = self._session.get("{0}/beams/{1}".format(self._url, beam_id))
        response.raise_for_status()

        json_response = response.json()
        return Beam.from_json(self, json_response['beam'])

    def get_files(self, beam_id, filter_):
        response = self._session.get(
            "{0}/files".format(self._url),
            params={"beam_id": beam_id, "filter": filter_})
        response.raise_for_status()
        return [File.from_json(self._session, f) for f in response.json()['files']]

    def get_file(self, file_id):
        """Retrieve details about the specified file.

        :param int file_id: File ID.
        :rtype: :class:`.File`"""
        response = self._session.get("{0}/files/{1}".format(self._url, file_id))
        response.raise_for_status()

        json_response = response.json()
        return File.from_json(self._session, json_response['file'])

    def get_beams_by_tag(self, tag):
        """Retrieve the list of beams associated with the specified tag.

        :param str tag: The name of the tag.
        :return: a list of :class:`.Beam` objects.
        """

        response = self._session.get("{0}/beams?tag={1}".format(self._url, tag))
        response.raise_for_status()

        ids = (b['id'] for b in response.json()['beams'])
        return [self.get_beam(id_) for id_ in ids]

    def sanity_check(self):
        """Check if this instance of Scotty is functioning. Raise an exception if something's wrong"""
        response = requests.get("{0}/info".format(self._url))
        response.raise_for_status()
        info = json.loads(response.text)
        assert 'version' in info

    def create_tracker(self, name, tracker_type, url, config):
        data = {
            'tracker': {
                'name': name,
                'type': tracker_type,
                'url': url,
                'config': json.dumps(config)
            }
        }
        response = self._session.post("{}/trackers".format(self._url), data=json.dumps(data))
        response.raise_for_status()
        return response.json()['tracker']['id']

    def get_tracker_id(self, name):
        response = self._session.get("{}/trackers/by_name/{}".format(self._url, name))
        response.raise_for_status()
        return response.json()['tracker']['id']

    def create_issue(self, tracker_id, id_in_tracker):
        data = {
            'issue': {
                'tracker_id': tracker_id,
                'id_in_tracker': id_in_tracker,
            }
        }
        response = self._session.post("{}/issues".format(self._url), data=json.dumps(data))
        response.raise_for_status()
        return response.json()['issue']['id']

    def delete_issue(self, issue_id):
        response = self._session.delete("{}/issues/{}".format(self._url, issue_id))
        response.raise_for_status()

    def delete_tracker(self, tracker_id):
        response = self._session.delete("{}/trackers/{}".format(self._url, tracker_id))
        response.raise_for_status()

    def update_tracker(self, tracker_id, name=None, url=None, config=None):
        data = {}

        if name:
            data['name'] = name

        if url:
            data['url'] = url

        if config:
            data['config'] = json.dumps(config)

        response = self._session.put(
            "{}/trackers/{}".format(self._url, tracker_id),
            data=json.dumps({'tracker': data}))
        response.raise_for_status()

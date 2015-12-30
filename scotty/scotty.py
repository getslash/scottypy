import os
import requests
import json
import socket
import tempfile
import shutil
import emport
import dateutil.parser
from datetime import datetime
from logging import getLogger
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter


_CHUNK_SIZE = 1024 ** 2 * 4
_SLEEP_TIME = 10
_NUM_OF_RETRIES = (60 // _SLEEP_TIME) * 15
logger = getLogger("scotty")

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
                 purge_time, size):
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
        self._scotty = scotty

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
            json_node['size'])

    def iter_files(self):
        """Iterate the beam files, yielding :class:`.File` objects"""
        for id_ in self._file_ids:
            yield self._scotty.get_file(id_)


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
    def __init__(self, url):
        self._url = url
        self._session = requests.Session()
        self._session.headers.update({
            'Accept-Encoding': 'gzip',
            'Content-Type': 'application/json'})
        self._session.mount(url, HTTPAdapter(max_retries=Retry(total=10, status_forcelist=[502, 504], backoff_factor=3)))

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

        response = self._session.get("{0}/static/assets/combadge.py".format(self._url))
        response.raise_for_status()

        with TempDir() as work_dir:
            combadge_path = os.path.join(work_dir, 'combadge.py')
            with open(combadge_path, 'w') as f:
                f.write(response.text)

            combadge = emport.import_file(combadge_path)
            combadge.beam_up(beam_id, directory, transporter_host)

        return beam_id

    def initiate_beam(self, user, host, directory, password=None, rsa_key=None, email=None):
        """Order scotty to beam the specified directory from the specified host.

        :param str user: The username in the remote machine.
        :param str host: The remote host.
        :param str directory: Remote directory to beam.
        :param str password: Password of the username.
        :param str rsa_key: RSA private key for authentication.
        :param str email: Your email. If unspecified, the initiator of the beam will be anonymous.

        Either `password` or `rsa_key` should be specified, but no both.

        :return: the beam id."""
        if (password and rsa_key) or not (password or rsa_key):
            raise Exception("Either password or rsa_key should be specified")


        beam = {
            'directory': os.path.abspath(directory),
            'host': host,
            'user': user,
            'ssh_key': rsa_key,
            'password': password,
            'auth_method': 'rsa' if rsa_key else 'password'
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

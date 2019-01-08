import os
import dateutil.parser
from datetime import datetime
from .exc import NotOverwriting

_CHUNK_SIZE = 1024 ** 2 * 4
_EPOCH = datetime.utcfromtimestamp(0)


def _to_epoch(d):
    return (d - _EPOCH.replace(tzinfo=d.tzinfo)).total_seconds()


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

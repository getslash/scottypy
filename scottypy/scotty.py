import emport
import json
import os
import requests
import socket
import logging
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from tempfile import NamedTemporaryFile
from .file import File
from .beam import Beam
from .exc import PathNotExists


_SLEEP_TIME = 10
_NUM_OF_RETRIES = (60 // _SLEEP_TIME) * 15
logger = logging.getLogger("scotty") # type: logging.Logger


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

    def beam_up(self, directory, email=None, beam_type=None, tags=None, return_beam_object=False):
        """Beam up the specified local directory to Scotty.

        :param str directory: Local directory to beam.
        :param str email: Your email. If unspecified, the initiator of the beam will be anonymous.
        :param list tags: An optional list of tags to be associated with the beam.
        :param bool return_beam_object: If set to True, return a :class:`.Beam` instance.

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

        if tags:
            beam['tags'] = tags

        response = self._session.post("{0}/beams".format(self._url), data=json.dumps({'beam': beam}))
        response.raise_for_status()

        beam_data = response.json()
        beam_id = beam_data['beam']['id']

        self._get_combadge().beam_up(beam_id, directory, transporter_host)

        if return_beam_object:
            return Beam.from_json(self, beam_data['beam'])
        else:
            return beam_data['beam']['id']

    def initiate_beam(self, user, host, directory, password=None, rsa_key=None, email=None, beam_type=None,
                      stored_key=None, tags=None, return_beam_object=False):
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

        if tags:
            beam['tags'] = tags

        if email:
            beam['email'] = email

        response = self._session.post("{0}/beams".format(self._url), data=json.dumps({'beam': beam}))
        response.raise_for_status()

        beam_data = response.json()

        if return_beam_object:
            return Beam.from_json(self, beam_data['beam'])
        else:
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

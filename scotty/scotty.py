import os
import requests
import json
import socket
import tempfile
import shutil
import emport


class TempDir(object):
    def __init__(self):
        self._path = None

    def __enter__(self):
        self._path = tempfile.mkdtemp()
        return self._path

    def __exit__(self, _1, _2, _3):
        shutil.rmtree(self._path)


class Scotty(object):
    """Main class that communicates with Scotty"""
    def __init__(self, url="http://scotty"):
        self._url = url

    def beam_up(self, directory):
        """Beam up the specified local directory to Scotty. Returns the beam ID"""
        session = requests.Session()
        session.headers.update({
            'Content-Type': 'application/json'})

        response = session.get("{0}/info".format(self._url))
        response.raise_for_status()
        transporter_host = response.json()['transporter']

        beam = {
            'directory': os.path.abspath(directory),
            'host': socket.gethostname(),
            'auth_method': 'independent'
        }

        response = session.post("{0}/beams".format(self._url), data=json.dumps({'beam': beam}))
        response.raise_for_status()

        beam_data = response.json()
        beam_id = beam_data['beam']['id']

        response = session.get("{0}/combadge".format(self._url))
        response.raise_for_status()

        with TempDir() as work_dir:
            combadge_path = os.path.join(work_dir, 'combadge.py')
            with open(combadge_path, 'w') as f:
                f.write(response.text)

            combadge = emport.import_file(combadge_path)
            combadge.beam_up(beam_id, directory, transporter_host)

        return beam_id

    def initiate_beam(self, user, host, directory, password=None, rsa_key=None):
        """Order scotty to beam the specified directory from the specified host.
        Either password or rsa_key should be specified, but not both.
        Returns the Beam ID."""
        if (password and rsa_key) or not (password or rsa_key):
            raise Exception("Either password or rsa_key should be specified")

        session = requests.Session()
        session.headers.update({
            'Content-Type': 'application/json'})

        beam = {
            'directory': os.path.abspath(directory),
            'host': host,
            'user': user,
            'ssh_key': rsa_key,
            'password': password,
            'auth_method': 'rsa' if rsa_key else 'password'
        }

        response = session.post("{0}/beams".format(self._url), data=json.dumps({'beam': beam}))
        response.raise_for_status()

        beam_data = response.json()
        return beam_data['beam']['id']

    def add_tag(self, beam_id, tag):
        """Add the specified tag on the specified beam id"""
        session = requests.Session()
        response = session.post("{0}/beams/{1}/tags/{2}".format(self._url, beam_id, tag))
        response.raise_for_status()

    def remove_tag(self, beam_id, tag):
        """Remove the specified tag from the specified beam id"""
        session = requests.Session()
        response = session.delete("{0}/beams/{1}/tags/{2}".format(self._url, beam_id, tag))
        response.raise_for_status()

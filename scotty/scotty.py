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

    def register_alias(self, beam_id, alias):
        """Register an alias for the specified beam id"""
        session = requests.Session()
        session.headers.update({
            'Content-Type': 'application/json'})

        data = {
            "beam_id": beam_id,
            "alias": alias,
        }
        response = session.post("{0}/aliases".format(self._url), data=json.dumps(data))
        response.raise_for_status()

    def unregister_alias(self, alias):
        """Unregister the specified alias"""
        response = requests.delete("{0}/alias/{1}".format(self._url, alias))
        response.raise_for_status()

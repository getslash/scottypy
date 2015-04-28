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


def beam_up(directory, scotty_url='http://scotty'):
    session = requests.Session()
    session.headers.update({
        'Content-Type': 'application/json'})

    response = session.get("{0}/info".format(scotty_url))
    response.raise_for_status()
    transporter_host = response.json()['transporter']

    beam = {
        'directory': os.path.abspath(directory),
        'host': socket.gethostname(),
        'auth_method': 'independent'
    }

    response = session.post("{0}/beams".format(scotty_url), data=json.dumps({'beam': beam}))
    response.raise_for_status()

    beam_data = response.json()
    beam_id = beam_data['beam']['id']

    response = session.get("{0}/combadge".format(scotty_url))
    response.raise_for_status()

    with TempDir() as work_dir:
        combadge_path = os.path.join(work_dir, 'combadge.py')
        with open(combadge_path, 'w') as f:
            f.write(response.text)

        combadge = emport.import_file(combadge_path)
        combadge.beam_up(beam_id, directory, transporter_host)

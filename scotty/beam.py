import os
import requests
import getpass
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


class UserNotFound(Exception):
    def __init__(self, email, url):
        super(UserNotFound, self).__init__()
        self.email = email
        self.url = url

    def __str__(self):
        return 'Your email address {0} isn\'t registered in {1}. Please go there and log in for the first time'.format(
            self.email, self.url)


def beam_up(directory, scotty_url='http://scotty',
            email="{0}@infinidat.com".format(getpass.getuser())):
    session = requests.Session()
    session.headers.update({
        'X-Authentication-Email': email,
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
    if response.status_code == 403:
        raise UserNotFound(email, scotty_url)
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

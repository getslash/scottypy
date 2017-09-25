import tempfile
import shutil
from slash import fixture
from scottypy import Scotty


@fixture
def scotty():
    return Scotty("http://localhost:8000")


@fixture
def tempdir(this):
    d = tempfile.mkdtemp()
    this.add_cleanup(lambda: shutil.rmtree(d))
    return d

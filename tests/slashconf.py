from slash import fixture
from scotty import Scotty


@fixture
def scotty():
    return Scotty("http://localhost:8000")

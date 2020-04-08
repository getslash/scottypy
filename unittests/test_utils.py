from http import HTTPStatus

import pytest
from requests import HTTPError

from scottypy import utils


class MockResponse:
    def __init__(self, *, status_code, content=b""):
        self.content = content
        self.status_code = status_code


def test_raise_for_status_client_error():
    with pytest.raises(HTTPError, match="409: Client Error: duplicate key"):
        utils.raise_for_status(
            MockResponse(status_code=HTTPStatus.CONFLICT, content=b"duplicate key")
        )


def test_raise_for_status_server_error():
    with pytest.raises(HTTPError, match="500: Server Error: should not be x"):
        utils.raise_for_status(
            MockResponse(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR, content=b"should not be x"
            )
        )


def test_raise_for_status_no_error():
    utils.raise_for_status(MockResponse(status_code=HTTPStatus.OK))

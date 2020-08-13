import asyncio
import logging
import os
from typing import Any, Dict, Optional

import requests

import aiohttp
import yarl
from aiohttp import ClientSession
from tenacity import retry, stop_after_attempt, stop_after_delay

from .exc import HTTPError

logger = logging.getLogger("scotty")  # type: logging.Logger


def raise_for_status(response: requests.Response) -> None:
    if 400 <= response.status_code < 500:
        error_type = "Client"
    elif 500 <= response.status_code < 600:
        error_type = "Server"
    else:
        error_type = ""
    if error_type:
        try:
            content = response.content.decode()
        except UnicodeDecodeError:
            content = "<content could not be decoded>"
        raise requests.HTTPError(
            "{status_code}: {error_type} Error: {content}".format(
                status_code=response.status_code,
                error_type=error_type,
                content=content,
            ),
            response=response,
        )


def fix_path_sep_for_current_platform(file_name: str) -> str:
    return file_name.replace("\\", os.path.sep).replace("/", os.path.sep)


class AsyncRequestHelper:
    def __init__(self):
        self._loop = asyncio.get_event_loop()
        self._session = aiohttp.ClientSession(
            loop=self._loop,
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"Accept-Encoding": "gzip", "Content-Type": "application/json"},
        )

    @retry(stop=(stop_after_delay(5) | stop_after_attempt(3)))
    async def execute_http(
        self,
        url: yarl.URL,
        *,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        method = "GET" if data is None else "POST"
        logger.info("Async Calling {} {}", method, url)
        async with self._session.request(
            method, url, params=params, json=data
        ) as response:
            if response.status != 200:
                raise HTTPError(
                    url=url, code=response.status, text=await response.text()
                )
            return await response.json()

    def __del__(self):
        self._loop.run_until_complete(self._session.close())


_async_request_helper = AsyncRequestHelper()
execute_http = _async_request_helper.execute_http

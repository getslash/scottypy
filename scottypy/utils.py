import os

import requests


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

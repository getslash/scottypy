class PathNotExists(Exception):
    def __init__(self, path: str):
        super(PathNotExists, self).__init__("{} does not exist".format(path))


class NotOverwriting(Exception):
    def __init__(self, file_: str):
        super(NotOverwriting, self).__init__()
        self.file = file_


class HTTPError(Exception):
    def __init__(self, *, url, code, text):
        super().__init__(
            "Server responded {code} when accessing {url}:\n{text}".format(
                code=code, url=url, text=text
            )
        )

class PathNotExists(Exception):
    def __init__(self, path: str):
        super(PathNotExists, self).__init__("{} does not exist".format(path))


class NotOverwriting(Exception):
    def __init__(self, file_: str):
        super(NotOverwriting, self).__init__()
        self.file = file_

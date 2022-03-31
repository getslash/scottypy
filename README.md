# Scotty Client Library

## Notes For Developers

### How to release a new version

- Checkout the master branch
- Update changelog in `README.md` file
- Run the following:

        VERSION=...
        echo "__version__ = \"$VERSION\"" > scottypy/__version__.py
        git commit -am "Bump version to $VERSION"

- Create a release via github (with a new tag)

## ChangeLog

### Unreleased

### 0.27.0

- Add `--version`

### 0.26.0

- Add option to link beam to issue when uploading a beam

### 0.25.2

- Increase timeout to 30 seconds

### 0.25.1

- Fix get_beams_by_issue so that it will use pagination

### 0.25.0

- Use combadge v2 by default (which supports windows hosts)

### 0.24.0

- Add filtering by issue
- Add delete method to beam

### 0.23.1

- Provide more information on exceptions
- Add type hinting
- Fix bug with downloading windows paths on linux

### 0.22.1

- Fix bug with prefetch and then beam up without explicitly setting version

### 0.22.0

- Support python3.8
- Support Rust Combadge (v2)

## Notes

- We used to use gitflow, but it became a bit too much of a hassle, so we switched to a simple master+tag flow. The develop branch was kept for legacy reasons but is not used anymore.

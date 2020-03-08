#!/bin/bash

VERSION=$1
echo "__version__ = \"$VERSION\"" > scottypy/__version__.py
git add scottypy/__version__.py
git commit -m "Bump version to $VERSION"
git flow release start "$VERSION"
git push --set-upstream origin "release/$VERSION"
git flow release finish "$VERSION"
git push origin : --tags

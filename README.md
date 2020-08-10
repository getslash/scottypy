
# Scotty Client Library  
  
## Notes For Developers  
  
### How to release a new version  
  
1. Update changelog in `README.md` file
1. Run the following:
```
VERSION=...
echo "__version__ = \"$VERSION\"" > scottypy/__version__.py
git add scottypy/__version__.py
git commit -m "Bump version to $VERSION"
git flow release start "$VERSION"
git push --set-upstream origin "release/$VERSION"
git flow release finish "$VERSION"
git push origin : --tags
```


## ChangeLog

### 0.24.0

* Add filtering by issue
* Add delete method to beam

### 0.23.1

* Provide more information on exceptions
* Add type hinting
* Fix bug with downloading windows paths on linux

### 0.22.1

* Fix bug with prefetch and then beam up without explicitly setting version

### 0.22.0

* Support python3.8
* Support Rust Combadge (v2)

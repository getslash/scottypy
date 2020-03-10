
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

### 0.22.0

* Support python3.8
* Support Rust Combadge (v2)

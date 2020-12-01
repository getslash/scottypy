default: check


format:
	isort -vb -c -rc scottypy unittests
	black --check scottypy unittests

do_format:
	isort -rc scottypy unittests
	black scottypy unittests

test:
	pytest unittests/

lint:
	MYPYPATH=stubs mypy scottypy --strict
	pylint --rcfile .pylintrc -j $(shell nproc) scottypy unittests

check: format lint test

default: check


format:
	isort --df -rc scottypy unittests
	isort -c -rc scottypy unittests
	black --check --diff scottypy unittests

do_format:
	isort -rc scottypy unittests
	black scottypy unittests

test:
	pytest unittests/

lint:
	MYPYPATH=stubs mypy scottypy --strict --install-types --non-interactive
	pylint --rcfile .pylintrc -j $(shell nproc) scottypy unittests

check: format lint test

# Contributing

Here's how to run all the development stuff.

## Setup Development Environment
* `pyenv global 3.6.8-amd64`
* `pipenv install --dev`

## Testing
* TODO:!
* `pytest -v` in the root directory
* To test coverage run `pipenv run coverage run -m pytest -v`
* Then run `pipenv run coverage report` or `pipenv run coverage html` and browser the coverage (TODO: Figure out a way to make a badge for this??)

## Releasing
Refer to [the python docs on packaging for clarification](https://packaging.python.org/tutorials/packaging-projects/).
* Make sure you've updated `setup.py`
* `python setup.py sdist bdist_wheel` - Create a source distribution and a binary wheel distribution into `dist/`
* `twine upload dist/notion_export_enhancer-x.x.x*` - Upload all `dist/` files to PyPI of a given version
* Make sure to tag the commit you released!

Installation
============


Install
-------

.. _virtual environment: https://virtualenv.pypa.io
.. _from PyPI: https://testpypi.python.org/pypi/eduxfeed
.. _GitHub repository: https://github.com/andrenvk/eduxfeed

| Install preferably using a `virtual environment`_,
| ``python`` and ``pip`` then point to appropriate Python 3 versions.

::

    $ python3.5 -m venv env
    $ # or: virtualenv --python=python3.5 env
    $ . env/bin/activate
    (env) $ # virtual env activated

Let's install the package `from PyPI`_ using pip.

::

    python -m pip install --extra-index-url \
    https://testpypi.python.org/pypi eduxfeed

Or, you can install it manually from a downloaded archive.

::

    python -m pip download --no-deps -i \
    https://testpypi.python.org/pypi eduxfeed
    # downloads e.g. eduxfeed-0.1.0.tar.gz
    tar -xzf eduxfeed-<version>.tar.gz
    cd eduxfeed-<version>
    python setup.py install

You can also install the most recent version directly from `GitHub repository`_.

::

    git clone https://github.com/andrenvk/eduxfeed.git
    cd eduxfeed
    python setup.py install

Now you are really close to start using the app. What to do next? Check out :doc:`usage`.


.. _test:

Test
----

.. _pytest: https://pypi.python.org/pypi/pytest
.. _flexmock: https://pypi.python.org/pypi/flexmock

In case of a manual install, you can also easily test the package and its functionality.

::

    python setup.py test


Or, in case you have already installed `pytest`_ and `flexmock`_, you can test directly.

::

    python -m pytest [OPTIONS]

| However, this only performs offline tests.
| For additional tests using your credentials, specify the config file containing auth keys like this:

::

    AUTH_FILE=<your auth file> python setup.py test

More on that in the section :ref:`auth`.

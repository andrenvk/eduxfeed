Usage
=====

.. _auth:

Credentials
-----------

The auth config file is expected to contain 3 sections: ``edux``, ``api``, ``oauth``::

    [edux]
    username = <CTU username>
    password = <CTU password>

    [api]
    # service app
    username = <client_id>
    password = <client_secret>

    [oauth]
    # web app
    username = <client_id>
    password = <client_secret>
    callback = <callback_url>

Section *edux*. Fill in your CTU username and password, will be used for authorized access to EDUX, to be able to check for updates of EDUX course pages and files. If you don't provide these credentials, the app will work, but no new updates will be found (and thus no new feed items). Just leave the respective values blank (the keys -- the first part of the key-value pairs -- have to be present). This holds also for the other sections, the app will cope with it, but the functionality will be limited (e.g. no automatically subscribed courses for a new user).

Sections *oauth* and *api*. To obtain these keys you have to create a `CTU API application <https://auth.fit.cvut.cz/manager>`_. Create a new project and `activate these scopes <../_static/api_scopes.png>`_: ``cvut:kosapi:read`` and ``cvut:umapi:read``. Then, inside of this project `create two apps <../_static/api_apps.png>`_, a `service app <../_static/api_service.png>`_ used for API access on the backend (section *api*), and a `web app <../_static/api_webapp.png>`_ used for login (section *oauth*). For the web app, you have to set a callback url. It could be localhost or your domain, where the app will be hosted. But make sure, the path part is ``/authorize`` which is what the app expects.

Finally, the config file could look like this (example with missing service app info):

.. code-block:: none

    [edux]
    username = ctuser20
    password = pa$$word
    
    [api]
    username = 
    password = 
    
    [oauth]
    username = 27d45fac-6308-418e-acbc-4fe9a36f92ac
    password = AQbqEx37nard1Klrv0KmRXsThdM3SmsQ
    callback = http://127.0.0.1:5000/authorize

| *Please note: The username and password values are made up and do not work.*
| *Do not make your passwords publicly available, it is your private information.*

Now go and :ref:`test` the application!


Package
-------

| The package exposes only ``init`` and ``update`` functions from their respective modules, see :doc:`src`.
| In addition to ``app`` which represents the web application, can be run directly as ``app.run()``.


Run
---

As simple as:

.. code-block:: none

   Usage: eduxfeed [OPTIONS]

   Options:
    --check   Check config
    --init    Init database
    --run     Start the webapp
    --all     Do steps check-init-run
    --force   Force option even if check fails
    --update  Update database; to be run regularly
    --help    Show this message and exit

Plus, you need to specify AUTH_FILE and DB_DIR environment variables,
pointing to your auth file and target database base directory,
otherwise defaults to 'auth.cfg' and 'db/' in current directory.

#. To start from scratch, check your config with ``--check``
#. Then init the database with ``--init``
#. Now you can start the app with ``--run``
#. Regularly perform database updates with ``--update``

Example usage::

   AUTH_FILE='authfile.cfg' DB_DIR='eduxdb' eduxfeed --run

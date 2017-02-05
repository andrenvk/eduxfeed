from .db import DB_DIR
from .auth import AUTH_FILE

from .auth import auth as _auth
from .init import init as _init
from .update import update as _update
from .appweb import app

import os
import click


@click.command()
@click.option('--check',  is_flag=True, default=False, help='Check config')
@click.option('--init',   is_flag=True, default=False, help='Init database')
@click.option('--run',    is_flag=True, default=False, help='Start the webapp')
@click.option('--all',    is_flag=True, default=False, help='Do steps check-init-run')
@click.option('--force',  is_flag=True, default=False, help='Force option even if check fails')
@click.option('--update', is_flag=True, default=False, help='Update database; to be run regularly')
def run(check, init, run, all, force, update):
    if not (check or init or run or all or update):
        print('Run with --help to see options')
        return
    if (init or run or all or update):
        check = True
    if update:
        init, run, all = False, False, False
    if all:
        init, run = True, True

    check_ok = True
    if check:
        print('CHECK')

        print('\tDB dir: {}'.format(DB_DIR))
        print('\tAuth file: {}'.format(AUTH_FILE))

        exist = os.path.isdir(DB_DIR)
        print('\tDB dir exists: {}'.format(exist))
        if not exist:
            check_ok = False

        exist = os.path.isfile(AUTH_FILE)
        print('\tAuth file exists: {}'.format(exist))

        if exist:
            for section in ('edux', 'api', 'oauth'):
                try:
                    _ = _auth(target=section)
                except:
                    print('\tConfig section "{}":\t{}'.format(section, 'ERROR'))
                    check_ok = False
                else:
                    print('\tConfig section "{}":\t{}'.format(section, 'OK'))
        else:
            check_ok = False
        print('\tCHECK OK:', check_ok)

    print()
    for flag, function, string in [(init, _init, 'INIT'), (run, app.run, 'RUN'), (update, _update, 'UPDATE')]:
        if flag:
            print(string)
            if (check_ok or force):
                function()
            else:
                print('\tFix config or run with --force')
                return
            print()

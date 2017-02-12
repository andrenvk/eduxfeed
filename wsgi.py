import sys
path = '/home/andrenvk/eduxfeed'
if path not in sys.path:
    sys.path.append(path)

from eduxfeed import app as application

import os
import sys

path = '/home/staffnetsys/EntrepriseManager'
if path not in sys.path:
    sys.path.append(path)

from app import app
application = app
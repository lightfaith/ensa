#!/usr/bin/env python3
"""
Global structures are defined here.
"""
from collections import OrderedDict

"""
Default configuration options
"""

config = OrderedDict()
censore_keys = ['db.password']

""" connection settings """
config['db.host'] = ('localhost', str)  # MySQL server hostname/IP
config['db.name'] = ('ensa', str)       # MySQL database name
config['db.username'] = ('ensa', str)   # MySQL username
config['db.password'] = ('', str)       # MySQL password

""" debug settings """
config['debug.command'] = (False, bool)  # show debug info about used commands
config['debug.config'] = (False, bool)   # show debug info about configuration 
config['debug.errors'] = (False, bool)   # show python tracebacks
#config['debug.flow'] = (True, bool)     # show debug info about program flow`
config['debug.query'] = (False, bool)    # show debug info about database queries

""" External commands """
config['external.editor'] = ('vim %s', str) # path to editor
config['interaction.command_modifier'] = ('$', str) # command modifier

"""
Dictionary of all available commands (filled in source/commands.py)
"""
commands = OrderedDict()

"""
Current data
"""
current_ring = None
current_subject = None

"""
Database object
"""
db = None


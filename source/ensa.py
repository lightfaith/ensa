#!/usr/bin/env python3
"""
Global structures are defined here.
"""
from collections import OrderedDict
from source.lib import positive

"""
Default configuration options
"""

config = OrderedDict()
censore_keys = ['db.password']

class Option():
    """

    """
    def __init__(self, default_value, data_type, immutable=False):
        self.__data_type = data_type
        self.value = default_value
        self.immutable = immutable

    @property
    def value(self):
        return self.__value

    @value.setter
    def value(self, v):
        if self.__data_type is bool:
            self.__value = positive(v)
        else:
            try:
                self.__value = self.__data_type(v)
            except:
                log.err('Option error - cannot cast \'%s\' to %s' %
                        (v, self.__data_type))

    def get_text_value(self):
        """
        Returns value suitable for printing.
        """
        result = (str(self.value) if self.__data_type != str
                                 else '\'%s\'' % self.value)
        for old, new in [
                ('\n', '\\n'),
                ('\r', '\\r'),
            ]:
            result = result.replace(old, new)
        return result



""" connection settings """
config['db.file'] = Option('', str, immutable=True)     # SQLite file
config['db.password'] = Option('', str, immutable=True) # DB password, prompted if empty 

""" debug settings """
config['debug.command'] = Option(False, bool)  # show debug info about used commands
config['debug.config'] = Option(False, bool)   # show debug info about configuration
config['debug.errors'] = Option(False, bool)   # show python tracebacks
# config['debug.flow'] = (True, bool)     # show debug info about program flow`
# show debug info about database queries
config['debug.query'] = Option(False, bool)

""" External commands """
config['external.editor'] = Option('vim %s', str)  # path to editor
config['interaction.command_modifier'] = Option('$', str)  # command modifier
config['interaction.default_accuracy'] = Option(0, int)  # default accuracy
# maximum accuracy (for color emphasis) # TODO check when modified
config['interaction.max_accuracy'] = Option(10, int)
# maximum level # TODO needed? # TODO check when modified
config['interaction.max_level'] = Option(10, int)

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
Variables
"""
variables = OrderedDict()

"""
Database object
"""
db = None

"""
Command history
"""
history = []

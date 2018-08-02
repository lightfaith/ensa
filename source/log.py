#!/usr/bin/env python3
"""
Print and logging stuff is here.
"""

import threading
from source.lib import positive
from source.ensa import config
import traceback

"""
Colors
"""
COLOR_NONE        = '\033[00m'
COLOR_BOLD        = "\033[01m"

COLOR_BLACK       = '\033[30m'
COLOR_DARK_RED    = '\033[31m'
COLOR_DARK_GREEN  = '\033[32m'
COLOR_BROWN       = '\033[33m'
COLOR_DARK_BLUE   = '\033[34m'
COLOR_DARK_PURPLE = '\033[35m'
COLOR_DARK_CYAN   = '\033[36m'
COLOR_GREY        = '\033[37m'

COLOR_DARK_GREY   = '\033[90m'
COLOR_RED         = '\033[91m'
COLOR_GREEN       = '\033[92m'
COLOR_YELLOW      = '\033[93m'
COLOR_BLUE        = '\033[94m'
COLOR_PURPLE      = '\033[95m'
COLOR_CYAN        = '\033[96m'
COLOR_WHITE       = '\033[97m'

"""
Colors for MIME types
"""
MIMECOLOR_PLAINTEXT = COLOR_GREEN
MIMECOLOR_HTML = COLOR_GREY
MIMECOLOR_SCRIPT = COLOR_BLUE
MIMECOLOR_CSS = COLOR_DARK_PURPLE
MIMECOLOR_IMAGE = COLOR_PURPLE
MIMECOLOR_MULTIMEDIA = COLOR_CYAN
MIMECOLOR_ARCHIVE = COLOR_BROWN
MIMECOLOR_BINARY = COLOR_DARK_GREY
MIMECOLOR_DATATRANSFER = COLOR_YELLOW
MIMECOLOR_DOCUMENT = COLOR_GREEN
MIMECOLOR_MESSAGE = COLOR_DARK_BLUE

prompt = ''
def set_prompt(key=None, symbol=None):
    global prompt
    if not key or not symbol:
        prompt = COLOR_PURPLE+COLOR_BOLD+'  ) '+COLOR_NONE
    else:
        prompt = COLOR_PURPLE+COLOR_BOLD+'%s%s ' % (key, symbol)+COLOR_NONE
        
set_prompt()

loglock = threading.Lock()

"""
Thread-safe print
"""
def tprint(string='', color=COLOR_NONE, new_line=True, stdout=True):
    lines = []
    lines.append(color+string+COLOR_NONE)
    if stdout:
        with loglock:
            for line in lines:
                print(line, end=('\n' if new_line else ''))
    return lines

def newline(stdout=True):
    lines = []
    lines.append('')
    if stdout:
        with loglock:
            for line in lines:
                print(line)
    return lines

"""
OK, INFO, WARN, ERR, QUESTION
"""
def show_marked(c, color='', string='', new_line=True, stdout=True):
    lines = []
    #lines.append('%s%s%s%s%s%s' % (color, COLOR_BOLD, c, COLOR_NONE, str(string),('\n' if newline else '')))
    lines.append('%s%s%s%s%s' % (color, COLOR_BOLD, c, COLOR_NONE, str(string)))
    if stdout:
        with loglock:
            for line in lines:
                print(line, end=('\n' if new_line else ''))
    return lines

def ok(string='', new_line=True, stdout=True):
    return show_marked('[+] ', COLOR_GREEN, string, new_line, stdout)
    
def info(string='', new_line=True, stdout=True):
    return show_marked('[.] ', COLOR_BLUE, string, new_line, stdout)
    
def warn(string='', new_line=True, stdout=True):
    return show_marked('[!] ', COLOR_YELLOW, string, new_line, stdout)
    
def err(string='', new_line=True, stdout=True):
    return show_marked('[-] ', COLOR_RED, string, new_line, stdout)
 
def question(string='', new_line=True, stdout=True):
    return show_marked('[?] ', COLOR_CYAN, string, new_line, stdout)


"""
Debug functions
"""
def debug_command(string=''):
    if positive(config['debug.command'][0]):
        show_marked('cmd.', COLOR_DARK_GREY, COLOR_DARK_GREY+str(string)+COLOR_NONE)

def debug_config(string=''):
    if positive(config['debug.config'][0]):
        show_marked('cnf.', COLOR_DARK_GREY, COLOR_DARK_GREY+str(string)+COLOR_NONE)

def debug_error(string=''):
    if positive(config['debug.errors'][0]):
        err('See traceback:')
        traceback.print_exc()

def debug_query(string=''):
    if positive(config['debug.query'][0]):
        show_marked('qry.', COLOR_DARK_GREY, COLOR_DARK_GREY+str(string)+COLOR_NONE)

#def debug_flow(string=''):
#    if positive(config['debug.flow'][0]):
#        show_marked('flw.', COLOR_DARK_GREY, COLOR_DARK_GREY+str(string)+COLOR_NONE)



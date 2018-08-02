#!/usr/bin/env python3
"""
General-purpose stuff is defined here.
"""
import os, sys, signal, io, time
from source import ensa
from source import db
from source import log

def positive(x):
    if type(x) in [bytes, bytearray]:
        x = x.decode()
    if type(x) == str:
        x = x.lower()
    if x in ['yes', 'y', '+', '1', 1, 'true', 't', True]:
        return True
    return False

def negative(x):
    if type(x) in [bytes, bytearray]:
        x = x.decode()
    if type(x) == str:
        x = x.lower()
    if x in ['no', 'n', '-', '0', 0, 'false', 'f', False]:
        return True
    return False

def quitstring(x):
    if type(x) != str:
        return False
    x = x.lower()
    if x in ['quit', 'exit', 'q', 'end', ':wq']:
        return True
    return False

def exit_program(signal, frame):
    if signal == -1: # immediate termination due to -h or bad parameter
        sys.exit(0)

    log.newline() # newline
    sys.exit(0 if signal is None else 1)

# run exit program on SIGINT
signal.signal(signal.SIGINT, exit_program)

def reload_config():
    log.info('Loading config file...')
    # read lines from conf file
    with open(os.path.join(os.path.dirname(sys.argv[0]), 'ensa.conf'), 'r') as f:
        for line in f.readlines():
            line = line.strip()
            # skip empty and comments
            if len(line) == 0 or line.startswith('#'):
                continue
            # get keys and values
            k, _, v = line.partition('=')
            k = k.strip()
            v = v.strip()
            if k in ensa.censore_keys:
                log.debug_config('  line: *********')
            else:
                log.debug_config('  line: \'%s\'' % (line))
            # cast to correct type and save into weber.config
            if k in ensa.config.keys():
                if ensa.config[k][1] in (bool, int, float):
                    if ensa.config[k][1] == bool:
                        v = positive(v)
                    ensa.config[k] = (ensa.config[k][1](v), ensa.config[k][1])
                else:
                    ensa.config[k] = (v, str)
            if k in ensa.censore_keys:
                v = '*********'
            log.debug_config('  parsed: %s = %s (%s)' % (k, v, str(type(v))))



def hexdump(data):
    # prints data as with `hexdump -C` command
    result = []
    line_count = 0
    for chunk in chunks(data, 16):
        hexa = ' '.join(''.join(get_colored_printable_hex(b) for b in byte) for byte in [chunk[start:start+2] for start in range(0, 16, 2)])
        
        # add none with coloring - for layout
        if len(hexa)<199:
            hexa += (log.COLOR_NONE+'  '+log.COLOR_NONE)*(16-len(chunk))

        result.append(log.COLOR_DARK_GREEN + '%08x' % (line_count*16) + log.COLOR_NONE +'  %-160s' % (hexa) + ' |' + ''.join(get_colored_printable(b) for b in chunk) + '|')
        line_count += 1
    #if result: # if request matches and response not, 2 headers are printed...
    #    result.insert(0, '{grepignore}-offset-   0 1  2 3  4 5  6 7  8 9  A B  C D  E F   0123456789ABCDEF')
    
    return result



#!/usr/bin/python3
"""
Ensa is collaborative tool for human information management.
"""
import readline
from source import log
from source import lib
from source import ensa
from source import commands
# TODO different db file from argument - but what about binary content?
if not ensa.db or not ensa.db.connect():
    log.err('Cannot connect to DB!')
    lib.exit_program(None, None)

rings = ensa.db.get_rings()
if rings:
    log.info('Welcome! Create new ring using `ra` or choose an existing one with `rs <name>`.')
    ring_lens = commands.get_format_len_ring(rings)
    log.info('Existing rings:')
    for ring in rings:
        log.info('  '+commands.format_ring(*ring, *ring_lens))
else:
    log.info('Welcome! It looks that you do not have any rings created. To do this, use `ra`.')


while True:
    # get command
    try:
        cmd = input(log.prompt).strip()
    except EOFError: # Ctrl+D -> quit
        log.newline()
        lib.exit_program(None, None)
    if len(cmd) == 0:
        continue
    # quit?
    if lib.quitstring(cmd):
        log.warn('Do you really want to quit? ', new_line=False)
        if lib.positive(input()):
            lib.exit_program(None, None)
    # do command
    else:
        commands.run_command(cmd)


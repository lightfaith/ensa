#!/usr/bin/env python3
"""
Commands and config methods are implemented here.
"""

import os, sys, re, traceback, tempfile, subprocess
from source import ensa
from source import lib
from source import log
from source.docs import doc
#from source.protocols import protocols
from source.lib import *
from source.db import Database

"""
Universal class for commands.
"""
class Command():

    def __init__(self, command, apropos, doc_tag, function):
        self.command = command
        self.doc_tag = doc_tag
        self.apropos = apropos
        self.description = doc.get(doc_tag) or ''
        self.function = function

    def run(self, *args):
        return self.function(*args)

    def __repr__(self):
        return 'Command(%s)' % (self.command)

    def __str__(self):
        return 'Command(%s)' % (self.command)


"""
Function to add new command
"""
def add_command(command):
    ensa.commands[command.command.partition(' ')[0]] = command


"""
Function to run commands, apply filters etc.
"""
def run_command(fullcommand):
    modifier = ensa.config['interaction.command_modifier'][0]
    log.debug_command('  Fullcmd: \'%s\'' % (fullcommand))
    parts = list(filter(None, re.split('(~~|~|\%s)' % (modifier), fullcommand)))
    command = parts[0]
    phase = {'~': False, '~~': False, modifier: False}
    
    # test if it is documented
    try:
        if not ensa.commands[command.rstrip('?')].description.strip():
            log.warn('The command has no documentation.')
    except:
        # command does not exist, but it will be dealt in a while
        pass 
    # help or command?
    if command.endswith('?'):
        lines = []
        for k, v in sorted(ensa.commands.items(), key=lambda x:x[0]):
            length = 50
            if k == '': # empty command - just print long description
                continue
            
            if k.startswith(command[:-1]) and len(k)-len(command[:-1])<=1:
                # do colors
                cmd, _, args = v.command.partition(' ')
                # question mark after command?
                more = ''
                if len([x for x in ensa.commands.keys() if x.startswith(cmd)])>1:
                    length += len(log.COLOR_BROWN)+len(log.COLOR_NONE)
                    more = log.COLOR_BROWN+'[?]'+log.COLOR_NONE
                command_colored = '%s%s %s%s%s' % (cmd, more, log.COLOR_BROWN, args, log.COLOR_NONE)
                apropos_colored = '%s%s%s' % (log.COLOR_DARK_GREEN, v.apropos, log.COLOR_NONE)
                lines.append('    %-*s %s' % (length, command_colored, apropos_colored))
        # show description if '??'
        if command.endswith('??'):
            for k, v in ensa.commands.items():
                if k == command[:-2]:
                    lines.append('')
                    lines += ['    '+log.COLOR_DARK_GREEN+line+log.COLOR_NONE for line in v.description.splitlines()]
    else:
        try:
            command, *args = command.split(' ')
            log.debug_command('  Command: \'%s\'' % (command))
            log.debug_command('  Args:    %s' % (str(args)))
            # run command
            lines = ensa.commands[command].run(*args)

        except Exception as e:
            log.err('Cannot execute command \''+command+'\': '+str(e)+'.')
            log.err('See traceback:')
            traceback.print_exc()
            return

    # Lines can be:
    #     a list of strings:
    #         every line matching grep expression or starting with '{grepignore}' will be printed
    #     a list of lists:
    #         every line of inner list matching grep expression or starting with '{grepignore}' will be printed if there is at least one grep matching line WITHOUT '{grepignore}'
    #         Reason: prsh~Set-Cookie will print all Set-Cookie lines along with RRIDs, RRIDs without match are ignored
    result_lines = []
    nocolor = lambda line: re.sub('\033\\[[0-9]+m', '', str(line))
    
    # go through all command parts and modify those lines
    for part in parts[1:]:
        tmp_lines = []
        # special character? set phase
        if part in phase.keys():
            # another phase active? bad command...
            if any(phase.values()):
                log.err('Invalid command.')
                return
            # no phase? set it
            phase[part] = True
            continue
        # no phase and no special character? bad command...
        elif not any(phase.values()):
            log.err('Invalid command (bad regex)!')
            return
        

        # deal with phases
        elif phase['~']:
            # normal grep
            log.debug_command('  grep \'%s\'' % part)
            phase['~'] = False
            for line in lines:
                if type(line) == str:
                    if str(line).startswith('{grepignore}') or part in nocolor(line):
                        tmp_lines.append(line)
                elif type(line) == list:
                    # pick groups if at least one line starts with {grepignore} or matches grep
                    sublines = [l for l in line if str(l).startswith('{grepignore}') or part in nocolor(l)]
                    if [x for x in sublines if not str(x).startswith('{grepignore}') and x.strip()]:
                        tmp_lines.append(sublines)
        elif phase['~~']:
            # regex grep
            log.debug_command('  regex_grep \'%s\'' % part)
            phase['~~'] = False
            for line in lines:
                if type(line) == str:
                    if str(line).startswith('{grepignore}') or re.search(part, nocolor(line.strip())):
                        tmp_lines.append(line)
                elif type(line) == list:
                    # pick groups if at least one line starts with {grepignore} or matches grep
                    sublines = [l for l in line if str(l).startswith('{grepignore}') or re.search(part, nocolor(l.strip()))]
                    if [x for x in sublines if not str(x).startswith('{grepignore}') and x.strip()]:
                        tmp_lines.append(sublines)
        elif phase[modifier]: # TODO line intervals and more features
            # modifying
            log.debug_command('  modification \'%s\'' % part)
            phase[modifier] = False
            # less? 
            if part.endswith('L'):
                less_lines = []
                for line in lines:
                    if type(line) == str:
                        less_lines.append(nocolor(re.sub('^\\{grepignore\\}', '', line)))
                    elif type(line) == list:
                        for subline in line:
                            less_lines.append(nocolor(re.sub('^\\{grepignore\\}', '', subline)))
                with tempfile.NamedTemporaryFile() as f:
                    f.write('\n'.join(less_lines).encode())
                    f.flush()
                    subprocess.call(['less', f.name])
                return

        # use parsed lines for more parsing
        lines = tmp_lines

    # any phase remained? that's wrong
    if any(phase.values()):
        log.err('Invalid command.')
        return
    
    for line in (lines or []):
        if type(line) == str:
            log.tprint(re.sub('^\\{grepignore\\}', '', line))
        elif type(line) == bytes:
            log.tprint(re.sub('^\\{grepignore\\}', '', line.decode()))
        elif type(line) == list:
            for subline in line:
                log.tprint(re.sub('^\\{grepignore\\}', '', subline))

"""
Important command functions
"""
def parse_sequence(sequence): # parses '1,3-5,9' into ['1', '3', '4', '5', '9']
    result = []
    for part in sequence.split(','):
        part = part.strip()
        if part.isdigit():
            result.append(part)
        begin, _, end = part.partition('-')
        if begin.isdigit() and end.isdigit():
            result += [str(x) for x in range(int(begin), int(end)+1)]
    return result

def wizard(questions):
    for q in questions:
        log.question('%s ' % (q), new_line=False)
        yield input()


"""
Format functions
"""

def get_format_len_information(infos):
    return (
        max([0]+[len('%d' % i[0]) for i in infos]),
        max([0]+[len(i[4]) for i in infos]),
        max([0]+[len(i[-1]) for i in infos]),
    )

def get_format_len_time(times):
    return (
        max([0]+[len('%d' % t[0]) for t in times]),
    )

def get_format_len_location(locations):
    return (
        max([0]+[len('%d' % l[0]) for l in locations]),
    )

def format_association(association_id, ring_id, level, accuracy, valid, modified, note, use_modified=True):
    return '%-d  %s (%sacc %d%s%s)' % (
        #id_len,
        association_id,
        note.decode() if note else '',
        'lvl %d, ' % level if level else '',
        accuracy,
        ', mod '+modified.strftime('%Y-%m-%d %H:%M:%S') if use_modified else '',
        ', invalid' if not valid else '',
        )

def format_information(information_id, subject_id, codename, info_type, name, level, accuracy, valid, modified, note, value, id_len, name_len, value_len, use_codename=True, use_modified=True):
    return '%-*d  %s  %*s: %-*s  (%sacc %d%s%s)  %s' % (
        id_len,
        information_id,
        '<%s>' % codename.decode() if use_codename else '',
        name_len,
        name.decode(),
        value_len,
        value.decode(),
        'lvl %d, ' % level if level else '',
        accuracy,
        ', mod '+modified.strftime('%Y-%m-%d %H:%M:%S') if use_modified else '',
        ', invalid' if not valid else '',
        note.decode() if note else '',
        )

def format_location(location_id, name, gps, accuracy, valid, modified, note, id_len, use_modified=True):
    if gps:
        lat, _, lon = gps.decode()[6:-1].partition(' ')
        lat = lat+'N' if float(lat)>0 else lat[1:]+'S'
        lon = lon+'E' if float(lon)>0 else lon[1:]+'W'
        gps = '(%s %s)' % (lat, lon)
    return '%-*d  %s %s (acc %d%s%s) %s' % (
        id_len,
        location_id,
        name.decode(),
        gps if gps else '',
        accuracy,
        ', mod '+modified.strftime('%Y-%m-%d %H:%M:%S') if use_modified else '',
        ', invalid' if not valid else '',
        note.decode() if note else '',
        )

def format_time(time_id, time, accuracy, valid, modified, note, id_len, use_modified=True):
    return '%-*d  %s  (acc %d%s%s) %s' % (
        id_len,
        time_id,
        #time.strftime('%Y-%m-%d %H:%M:%S'),
        time.decode() if time else '',
        accuracy,
        ', mod '+modified.strftime('%Y-%m-%d %H:%M:%S') if use_modified else '',
        ', invalid' if not valid else '',
        note.decode() if note else '',
        )

# # # # ## ## ### #### ###### ############################ ##### #### ### ## ## # # # #

# # # # ## ## ### #### ###### ############################ ##### #### ### ## ## # # # #
# # # # ## ## ### #### ###### ############################ ##### #### ### ## ## # # # #
# # # # ## ## ### #### ###### ############################ ##### #### ### ## ## # # # #
# # # # ## ## ### #### ###### ############################ ##### #### ### ## ## # # # #

# # # # ## ## ### #### ###### ############################ ##### #### ### ## ## # # # #
help_description = """

"""
add_command(Command('', '', 'help', lambda: []))

"""
TEST COMMANDS
"""
def test_function(*args):
    result = []
    print(parse_sequence(args[0]))
    return result
add_command(Command('test', 'do actually tested action', '', test_function))

def prompt_function(*_): # TODO for testing only!
    while True:
        print('> ', end='')
        exec(input())
    return []
add_command(Command('prompt', 'gives python3 shell', '', prompt_function))

"""
ASSOCIATION COMMANDS
"""
def a_function(*_):
    associations = ensa.db.get_associations()
    for association in associations:
        yield format_association(*association, use_modified=True)
add_command(Command('a', 'list associations for this ring', 'a', a_function))
add_command(Command('aa', 'association creation', 'aa', lambda *_: []))

def aaa_function(*args):
    try:
        association_id = args[0]
    except:
        log.err('Main association ID must be specified.')
        return []
    try:
        association_ids = ','.join(parse_sequence(','.join(args[1:])))
        if not association_ids:
            raise AttributeError
    except:
        log.err('Inferior association ID must be specified.')
        return []
    ensa.db.associate_association(association_id, association_ids)
    return []
add_command(Command('aaa <association_id> <association_ids>', 'associate associations to an association', 'aaa', aaa_function))

def aai_function(*args):
    try:
        association_id = args[0]
    except:
        log.err('Association ID must be specified.')
        return []
    try:
        information_ids = ','.join(parse_sequence(','.join(args[1:])))
        if not information_ids:
            raise AttributeError
    except:
        log.err('Information ID must be specified.')
        return []
    ensa.db.associate_information(association_id, information_ids)
    return []
add_command(Command('aai <association_id> <information_ids>', 'associate information entries to an association', 'aai', aai_function))

def aal_function(*args):
    try:
        association_id = args[0]
    except:
        log.err('Association ID must be specified.')
        return []
    try:
        location_ids = ','.join(parse_sequence(','.join(args[1:])))
        if not location_ids:
            raise AttributeError
    except:
        log.err('Location ID must be specified.')
        return []
    ensa.db.associate_location(association_id, location_ids)
    return []
add_command(Command('aal <association_id> <location_ids>', 'associate location entries to an association', 'aal', aal_function))


def aas_function(*args):
    try:
        association_id = args[0]
    except:
        log.err('Association ID must be specified.')
        return []
    try:
        codenames = ','.join(['\'%s\'' % codename for codename in args[1:]])
        if not codenames:
            raise AttributeError
    except:
        log.err('Subject codename must be specified.')
        return []
    ensa.db.associate_subject(association_id, codenames)
    return []
add_command(Command('aas <association_id> <codename>', 'associate subject to an association', 'aas', aas_function))


def aat_function(*args):
    try:
        association_id = args[0]
    except:
        log.err('Association ID must be specified.')
        return []
    try:
        time_ids = ','.join(parse_sequence(','.join(args[1:])))
        if not time_ids:
            raise AttributeError
    except:
        log.err('Time ID must be specified.')
        return []
    ensa.db.associate_time(association_id, time_ids)
    return []
add_command(Command('aat <association_id> <time_ids>', 'associate time entries to an association', 'aat', aat_function))

def aaw_function(*_):
    if not ensa.current_ring:
        log.err('First select a ring with `rs <name>`.')
        return []
    note, level, accuracy, valid, confirm = wizard([
            'Description:',
            'Optional level of importance:',
            'Accuracy of this entry (default 0):',
            'Should the entry be marked as invalid?',
            '... Use provided information to create new association?',
        ])
    if negative(confirm):
        return []
    level = int(level) if level.isdigit() else None
    accuracy = int(accuracy) if accuracy.isdigit() else 0
    valid = not positive(valid)
    association_id = ensa.db.create_association(level, accuracy, valid, note)
    log.info('Created new association with id #%d' % association_id)
    return []
add_command(Command('aaw', 'use wizard to add new association to current ring', 'aaw', aaw_function))


def ad_function(*args):
    try:
        association_id = args[0]
        ensa.db.delete_associations(association_id)
    except:
        log.err('Association ID must be specified.')
        return []
    return []
add_command(Command('ad <association_id>', 'delete whole association', 'ad', ad_function))


def ada_function(*args):
    try:
        association_id = args[0]
    except:
        log.err('Main association ID must be specified.')
        return []
    try:
        ids = ','.join(parse_sequence(','.join(args[1:])))
    except:
        log.err('Inferior association ID must be specified.')
        return []
    ensa.db.dissociate_associations(association_id, ids)
    return []
add_command(Command('ada <association_id> <association_ids>', 'remove associations from an association', 'ada', ada_function))


def adi_function(*args):
    try:
        association_id = args[0]
    except:
        log.err('Association ID must be specified.')
        return []
    try:
        ids = ','.join(parse_sequence(','.join(args[1:])))
    except:
        log.err('Information ID must be specified.')
        return []
    ensa.db.dissociate_informations(association_id, ids)
    return []
add_command(Command('adi <association_id> <information_ids>', 'remove information entries from an association', 'adi', adi_function))


def adl_function(*args):
    try:
        association_id = args[0]
    except:
        log.err('Association ID must be specified.')
        return []
    try:
        ids = ','.join(parse_sequence(','.join(args[1:])))
    except:
        log.err('Location ID must be specified.')
        return []
    ensa.db.dissociate_locations(association_id, ids)
    return []
add_command(Command('adl <association_id> <location_ids>', 'remove locations from an association', 'adl', adl_function))


def adt_function(*args):
    try:
        association_id = args[0]
    except:
        log.err('Association ID must be specified.')
        return []
    try:
        ids = ','.join(parse_sequence(','.join(args[1:])))
    except:
        log.err('Time ID must be specified.')
        return []
    ensa.db.dissociate_times(association_id, ids)
    return []
add_command(Command('adt <association_id> <time_ids>', 'remove times from an association', 'adt', adt_function))



def aga_function(*args):
    ids = ','.join(parse_sequence(','.join(args)))
    if not ids:
        log.err('You must specify an Association ID.')
        return []
    # TODO nested array result
    data = ensa.db.get_associations_by_ids(ids)
    if not data:
        return []
    for association, infos, times, locations, associations in data:
        print('#A'+format_association(*association, use_modified=True))
        info_lens = get_format_len_information(infos)
        time_lens = get_format_len_time(times)
        location_lens = get_format_len_location(locations)
        for info in infos:
            print('    #I'+format_information(*info, *info_lens, use_modified=False))
        for time in times:
            print('    #T'+format_time(*time, *time_lens, use_modified=False))
        for location in locations:
            print('    #L'+format_location(*location, *location_lens, use_modified=False))
        for a in associations:
            print('    #A'+format_association(*a, use_modified=False))
    return []
add_command(Command('aga <association_ids>', 'show associations with specific ID', 'aga', aga_function))
# by id
# by notelike
# by info
# by time
# by place

"""
INFORMATION COMMANDS
"""
# TODO list standard names in help
add_command(Command('i', 'print information overview for current subject', 'i', lambda *_: ['TODO']))
add_command(Command('ia', 'add information to current subject', 'ia', lambda *_: []))

def iac_function(*args):
    try:
        name = args[0].lower()
        parts = ','.join(parse_sequence(','.join(args[1:])))
        if not parts:
            log.err('At least one information ID must be specified.')
            return []
        ensa.db.create_information(Database.INFORMATION_COMPOSITE, name, parts)
    except:
        traceback.print_exc()
        return []
    return []
    
add_command(Command('iac <name> <information_ids>', 'add composite information to current subject', 'iac', iac_function))


def iat_function(*args):
    try:
        name = args[0].lower()
        value = ' '.join(args[1:])
        if not value:
            log.err('Value must be specified.')
            return []
        ensa.db.create_information(Database.INFORMATION_TEXT, name, value)
    except:
        traceback.print_exc()
        return []
    return []
add_command(Command('iat <name> <value>', 'add textual information to current subject', 'iat', iat_function))


def iar_function(*args):
    try:
        name = args[0].lower()
        codename = args[1]
        ensa.db.create_information(Database.INFORMATION_RELATIONSHIP, name, codename)
    except:
        traceback.print_exc()
        return []
    return []

        
add_command(Command('iar <name> <codename>', 'add relationship information towards <codename> to current subject', 'iar', iar_function))


def id_function(*args):
    try:
        information_id = args[0]
    except:
        log.err('ID of information must be specified.')
        return []
    ensa.db.delete_information(information_id)
    return []
add_command(Command('id <information_id>', 'delete information of current subject', 'id', id_function))


add_command(Command('ig', 'get information of current subject', 'ig', lambda *_: ['TODO']))

"""
def igr_function(*_):
    result = []
    infos = ensa.db.get_information(Database.INFORMATION_RELATIONSHIP)
    if not infos:
        return []

    peers = [] # TODO do this in SELECT
    for peer_id in [i[-1] for i in infos]:
        peers.append('%s (#%d)' % (ensa.db.get_subject_codename(peer_id).decode(), peer_id))
    max_id_len = max(len('%d' % i[0]) for i in infos)
    max_name_len = max(len(i[3]) for i in infos)
    max_value_len = max(len(peer) for peer in peers)
    for (information_id, _, __, name, accuracy, valid, modified, note, level, ___), peer in zip(infos, peers):
        result.append('#%-*d  %*s: %-*s  (lvl %d, acc %d, mod %s%s)  %s' % (
            max_id_len,
            information_id,
            max_name_len,
            name.decode(),
            max_value_len,
            peer,
            level,
            accuracy,
            modified.strftime('%Y-%m-%d %H:%M:%S'),
            ', invalid' if not valid else '',
            note.decode() if note else '',
            ))
    return result
add_command(Command('igr', 'get all relationship information for current subject', 'igr', igr_function))
# TODO igrx - cross-reference
"""

def igt_function(*_, no_composite_parts=True):
    result = []
    infos = ensa.db.get_information(Database.INFORMATION_TEXT, no_composite_parts)
    if not infos:
        return []
    info_lens = get_format_len_information(infos)
    result = [format_information(*info, *info_lens, use_codename=False) for info in infos]
    return result
add_command(Command('igt', 'get all textual information for current subject', 'igt', igt_function))
add_command(Command('igtc', 'get all textual information (even composite parts) for current subject', 'igtc', lambda *args: igt_function(args, no_composite_parts=False)))


def ime_function(*args):
    try:
        information_id = args[0]
    except:
        log.err('ID of information must be specified.')
        return []
    # TODO prepare data
    with tempfile.NamedTemporaryFile() as f:
        f.write(r.bytes())
        f.flush()
        subprocess.call((ensa.config['external.editor'][0] % (f.name)).split())
        f.seek(0)
        # read back
        changes = f.read()

    # TODO parse changes
    if changes != r.bytes():
        pass

add_command(Command('ime <information_id>', 'modify information with editor', 'ime', ime_function))

"""
LOCATION COMMANDS
"""
def l_function(*_):
    locations = ensa.db.get_locations()
    if not locations:
        return []
    location_lens = get_format_len_location(locations)
    for location in locations:
        yield format_location(*location, *location_lens, use_modified=True) 
add_command(Command('l', 'list locations for current ring', 'l', l_function))
add_command(Command('la', 'add new location for current ring', 'la', lambda *_: ['TODO']))

def law_function(*_):
    if not ensa.current_ring:
        log.err('First select a ring with `rs <name>`.')
        return []
    name, lat, lon, accuracy, valid, note, confirm = wizard([
            'Name of the place:',
            'Latitude (e.g. 50.079795):',
            'Longitude (e.g. 14.429710):',
            'Accuracy of this entry (default 0):',
            'Should the entry be marked as invalid?',
            'Optional comment:',
            '... Use provided information to create new location?',
        ])
    if negative(confirm):
        return []
    try:
        lat = float(lat)
        lon = float(lon)
    except:
        lat = None
        lon = None
    accuracy = int(accuracy) if accuracy.isdigit() else 0
    valid = not positive(valid)
    location_id = ensa.db.create_location(name, lat, lon, accuracy, valid, note)
    log.info('Created new location with id #%d' % location_id)
    return []
add_command(Command('law', 'use wizard to add new location to current ring', 'law', law_function))

def ld_function(*args):
    try:
        location_ids = ','.join(parse_sequence(','.join(args)))
        ensa.db.delete_locations(location_ids)
    except:
        traceback.print_exc()
        log.err('Correct location ID from this ring must be provided.')
    return []
add_command(Command('ld <location_id>', 'delete location entry from current ring', 'ld', ld_function))

"""
OPTIONS COMMANDS
"""
o_function = lambda *_: ['    %-30s  %s' % (k, (str(v[0] if v[1] != str else '\''+v[0]+'\'').replace('\n', '\\n').replace('\r', '\\r')) if k not in ensa.censore_keys else '*********') for k,v in ensa.config.items()]
o_description = """Active Ensa configuration can be printed with `peo` and `o` command.

Default configuration is located in source/ensa.py.
User configuration can be specified in ensa.conf in Ensa root directory.
Configuration can be changed on the fly using the `os` command.
"""
add_command(Command('o', 'Ensa options (alias for `peo`)', 'o', o_function))

# os
def os_function(*args):
    try:
        key = args[0]
        value = args[1]
    except:
        log.err('Invalid arguments.')
        return []
    typ = str if key not in ensa.config.keys() else ensa.config[key][1]
    if typ == bool:
        value = positive(value)
    ensa.config[key] = (typ(value), typ)
    return []
add_command(Command('os <key> <value>', 'change Ensa configuration', 'os', os_function))

"""
PRINT COMMANDS
"""
add_command(Command('p', 'print', 'p', lambda *_: []))


# pe 
add_command(Command('pe', 'print ensa-related information', 'pe', lambda *_: []))


# peo
add_command(Command('peo', 'print ensa configuration', 'o', o_function))

"""
Quit
"""
add_command(Command('q', 'quit', '', lambda *_: [])) # solved in ensa




"""
RING COMMANDS
"""
def r_function(*_):
    result = ensa.db.get_rings() # TODO count subjects, show if encrypted, show notes, show if selected
    return ['  %s ' % (r[1].decode()) for r in result]
add_command(Command('r', 'print rings', 'r', r_function))

def ra_function(*_):
    name, encrypted, note, confirm = wizard([
            'Name of the ring (e.g. Work):',
            'Should the ring be encrypted (default: no)?',
            'Optional comment:',
            '... Use provided information to create new ring?',
        ])
    if negative(confirm):
        return []
    if not name:
        log.err('Unique name must be specified.')
        return []
    if positive(encrypted):
        # TODO ask for password, bcrypt it and save in memory
        log.err('TODO - encryption')
        return []
    else:
        password = None
    if not note:
        note = None
    result = ensa.db.create_ring(name, password, note)
    if not result:
        log.err('Error while inserting ring into DB.')
        return []
    ensa.current_ring = ensa.db.select_ring(name)
    if ensa.current_ring:
        log.info('Currently working with \'%s\' romg.' % name)
    return []
add_command(Command('ra', 'add new ring', 'ra', ra_function))

def rd_function(*args):
    if not args:
        log.err('Ring name must be specified.')
    try:
        ring_id = ensa.db.select_ring(args[0])
        if not ring_id:
            raise AttributeError
        if ensa.current_ring == ring_id:
            ensa.current_ring = None
            ensa.current_subject = None
            log.set_prompt()
        ensa.db.delete_ring(ring_id)
    except:
        traceback.print_exc()
        log.err('No ring with that name exists.')
        return []
    return []
add_command(Command('rd <ring>', 'delete ring', 'rd', rd_function))

def rs_function(*args):
    try:
        if not args:
            ensa.current_ring = None
            log.info('Currently working outside rings.')
            log.set_prompt()
            return []
        name = args[0]
        ensa.current_ring = ensa.db.select_ring(name)
        if ensa.current_ring:
            ensa.current_subject = None
            log.info('Currently working with \'%s\' ring.' % name)
            log.set_prompt(key=name, symbol=')')
    except:
        log.err('Ring name must be specified.')
        traceback.print_exc()
    return []
add_command(Command('rs <ring>', 'select a ring', 'rs', rs_function))

"""
SUBJECT COMMANDS
"""
def s_function(*_):
    subjects = ensa.db.get_subjects()
    return ['%10s (#%d)  %20s  %s' % (codename.decode(), subject_id, created.strftime('%Y-%m-%d %H:%M:%S'), note.decode() if note else '') for subject_id, codename, created, note in subjects]
add_command(Command('s', 'list subjects in the current ring', 's', s_function))

def sa_function(*args): # simple subject creation, `saw` for wizard
    try:
        codename = args[0]
    except:
        log.err('You must specify codename.')
        return []
    ensa.db.create_subject(codename)
    if ensa.current_subject:
        log.set_prompt(key='%s/%s' % (ensa.db.get_ring_name(ensa.current_ring).decode(), codename), symbol=']')
        log.info('Currently working with \'%s\' subject.' % codename)
    return []
        
add_command(Command('sa <codename>', 'add new subject in the current ring', 'sa', sa_function))

# TODO `saw`

def sd_function(*args):
    if not args:
        log.err('Subject name must be specified.')
    try:
        subject_id = ensa.db.select_subject(args[0])
        if not subject_id:
            raise AttributeError
        if ensa.current_subject == subject_id:
            ensa.current_subject = None
            log.set_prompt(key=ensa.db.get_ring_name(ensa.current_ring).decode(), symbol=')')
        ensa.db.delete_subject(subject_id)
    except:
        traceback.print_exc()
        log.err('No ring with that name exists.')
        return []
    return []
    
add_command(Command('sd <codename>', 'delete subject from the current ring', 'sd', sd_function))

def ss_function(*args):
    try:
        codename = args[0]
        ensa.current_subject = ensa.db.select_subject(codename)
        if ensa.current_subject:
            log.info('Currently working with \'%s\' subject.' % codename)
            log.set_prompt(key='%s/%s' % (ensa.db.get_ring_name(ensa.current_ring).decode(), codename), symbol=']')
    except:
        log.err('Subject codename must be specified.')
        traceback.print_exc()
    return []
add_command(Command('ss <subject>', 'select a subject', 'ss', ss_function))


"""
TIME COMMANDS
"""
def t_function(*_):
    times = ensa.db.get_times()
    if not times:
        return []
    time_lens = get_format_len_time(times)
    for time in times:
        yield format_time(*time, *time_lens, use_modified=True) 
add_command(Command('t', 'list time entries for current ring', 't', t_function))
add_command(Command('la', 'add new location for current ring', 'la', lambda *_: ['TODO']))

def taw_function(*_):
    if not ensa.current_ring:
        log.err('First select a ring with `rs <name>`.')
        return []
    date, time, accuracy, valid, note, confirm = wizard([
            'Date (YYYY-mm-dd):',
            'Time (HH:MM:SS):',
            'Accuracy of this entry (default 0):',
            'Should the entry be marked as invalid?',
            'Optional comment:',
            '... Use provided information to create new time?',
        ])
    if negative(confirm):
        return []
    accuracy = int(accuracy) if accuracy.isdigit() else 0
    valid = not positive(valid)
    time_id = ensa.db.create_time(date, time, accuracy, valid, note)
    log.info('Created new time entry with id #%d' % time_id)
    return []
add_command(Command('taw', 'use wizard to add new time entry to current ring', 't', taw_function))

def td_function(*args):
    try:
        time_ids = ','.join(parse_sequence(','.join(args)))
        ensa.db.delete_times(time_ids)
    except:
        traceback.print_exc()
        log.err('Correct time ID from this ring must be provided.')
    return []
add_command(Command('td <time_id>', 'delete time entry from current ring', 'td', td_function))


















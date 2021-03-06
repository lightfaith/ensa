#!/usr/bin/env python3
"""
Commands and config methods are implemented here.
"""

import os
import pdb
import sys
import re
import traceback
import tempfile
import subprocess
from source import ensa
from source import lib
from source import log
from source.docs import doc
from source.pdf import *
from source.map import *
# from source.protocols import protocols
from source.lib import *
from source.db import Database
from datetime import datetime
import dateutil.parser

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
    ensa.history.append(fullcommand)
    """only comment or nothing? skip"""
    if fullcommand.startswith('#') or not fullcommand.strip():
        return

    modifier = ensa.config['interaction.command_modifier'].value
    regex_modifier = (modifier   # TODO there must be better way
                      if modifier not in '^$\\*.+{('
                      else r'\%s' % modifier)
    log.debug_command('  Fullcmd: \'%s\'' % (fullcommand))

    """
    replace variables / create new
    """
    variable_setting = False
    """ first check if we are setting"""
    if re.match(r'^%s[a-z_][a-z0-9_]* ?= ?.+' % regex_modifier, fullcommand):
        variable_setting = True
    """ now replace variables (ignore first variable if setting)"""
    while True:  # TODO loop probably not needed
        variable_matches = re.findall(r'(%s[a-z0-9_]+)' % regex_modifier,
                                      fullcommand[(1 if variable_setting
                                                   else 0):])
        if not variable_matches:
            break
        for m in sorted(variable_matches, key=lambda x: len(x), reverse=True):
            name = m[1:]
            value = str(ensa.variables.get(name))
            # pdb.set_trace()
            if value:
                fullcommand = ((modifier if variable_setting else '')
                               + re.sub(regex_modifier + name,
                                        value,
                                        fullcommand[(1 if variable_setting
                                                     else 0):]))
            else:
                log.err('Non-existent variable used!')
                return []
        if variable_matches:
            log.debug_command('  Fullcmd with variables: \'%s\''
                              % (fullcommand))
    """ finally, set a variable if desired """
    if variable_setting:
        variable, _, value = fullcommand.partition('=')
        variable = variable.strip()[1:]
        value = value.strip()
        ensa.variables[variable] = value
        log.info('$%s = %s' % (variable, value))
        return []

    """split fullcommand into parts"""
    parts = list(filter(None, re.split(r'(~~|~|%s)' % (regex_modifier),
                                       fullcommand)))
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
        for k, v in sorted(ensa.commands.items(), key=lambda x: x[0]):
            length = 50
            if k == '':  # empty command - just print long description
                continue

            if k.startswith(command[:-1]) and len(k)-len(command[:-1]) <= 1:
                # do colors
                cmd, _, args = v.command.partition(' ')
                # question mark after command?
                more = ''
                if len([x for x in ensa.commands.keys() if x.startswith(cmd)]) > 1:
                    length += len(log.COLOR_BROWN)+len(log.COLOR_NONE)
                    more = log.COLOR_BROWN+'[?]'+log.COLOR_NONE
                command_colored = '%s%s %s%s%s' % (
                    cmd, more, log.COLOR_BROWN, args, log.COLOR_NONE)
                apropos_colored = '%s%s%s' % (
                    log.COLOR_DARK_GREEN, v.apropos, log.COLOR_NONE)
                lines.append('    %-*s %s' %
                             (length, command_colored, apropos_colored))
        # show description if '??'
        if command.endswith('??'):
            for k, v in ensa.commands.items():
                if k == command[:-2]:
                    lines.append('')
                    lines += ['    '+log.COLOR_DARK_GREEN+line +
                              log.COLOR_NONE for line in v.description.splitlines()]
    else:
        try:
            command, *args = command.split(' ')
            args = tuple(filter(None, args))
            log.debug_command('  Command: \'%s\'' % (command))
            log.debug_command('  Args:    %s' % (str(args)))
            # run command
            lines = ensa.commands[command].run(*args)

        except Exception as e:
            traceback.print_exc()
            log.err('Cannot execute command \''+command+'\': '+str(e)+'.')
            log.debug_error()
            return

    # Lines can be:
    #     a list of strings:
    #         every line matching grep expression or starting with '{grepignore}' will be printed
    #     a list of lists:
    #         every line of inner list matching grep expression or starting with '{grepignore}' will be printed if there is at least one grep matching line WITHOUT '{grepignore}'
    result_lines = []
    def nocolor(line): return re.sub('\033\\[[0-9]+m', '', str(line))

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
                    sublines = [l for l in line if str(l).startswith(
                        '{grepignore}') or part in nocolor(l)]
                    if [x for x in sublines if (not str(x).startswith('{grepignore}') or part in nocolor(x)) and x.strip()]:
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
                    sublines = [l for l in line if str(l).startswith(
                        '{grepignore}') or re.search(part, nocolor(l.strip()))]
                    if [x for x in sublines if (not str(x).startswith('{grepignore}') or part in nocolor(x)) and x.strip()]:
                        tmp_lines.append(sublines)
        elif phase[modifier]:  # TODO line intervals and more features
            # modifying
            log.debug_command('  modification \'%s\'' % part)
            phase[modifier] = False
            # less?
            if part.endswith('L'):
                less_lines = []
                for line in lines:
                    if type(line) == str:
                        less_lines.append(
                            nocolor(re.sub('^\\{grepignore\\}', '', line)))
                    elif type(line) == list:
                        for subline in line:
                            less_lines.append(
                                nocolor(re.sub('^\\{grepignore\\}', '', subline)))
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
    if type(lines) not in (tuple, list):
        lines = []
    for line in lines:
        if type(line) == str:
            log.tprint(re.sub('^\\{grepignore\\}', '', line))
        elif type(line) == bytes:
            log.tprint(re.sub('^\\{grepignore\\}', '', line))
        elif type(line) == list:
            for subline in line:
                log.tprint(re.sub('^\\{grepignore\\}', '', subline))


"""
Important command functions
"""


# parses '1,3-5,9' into ['1', '3', '4', '5', '9']
def parse_sequence(sequence):
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
        line = input()
        ensa.history.append(line)
        yield line


"""
Format functions
"""


def get_format_len_information(infos):
    return (
        max([0]+[len('%d' % i[0]) for i in infos]),
        max([0]+[2 + len('%s' % i[2]) for i in infos]),
        max([0]+[len(i[4]) for i in infos]),
        max([0]+[(len(i[-1])
                  if i[3] != Database.INFORMATION_COMPOSITE
                  else len(','.join([str(x) for x in i[-1]])) + 2) for i in infos]),
    )


def get_format_len_ring(rings):
    return (
        max([0]+[len('%s' % r[1]) for r in rings]),

    )


def get_format_len_time(times):
    return (
        max([0]+[len('%d' % t[0]) for t in times]),
        # max([0]+[len('%s' % t[1]) for t in times]),
    )


def get_format_len_location(locations):
    return (
        max([0]+[len('%d' % l[0]) for l in locations]),
    )


def format_ring(ring_id, name, reference_time_id, note, name_len):
    reference_time = ensa.db.get_time(
        reference_time_id, force_no_current_ring=True)[1]
    return '%*s  %-15s%s' % (
        name_len,
        name,
        '(ref: %s)' % reference_time,
        ' # %s' % note if note else '',
    )


def format_association(association_id, ring_id, level, accuracy, valid, modified, note, use_modified=True):
    color = log.COLOR_NONE
    if not valid:
        color = log.COLOR_DARK_RED
    else:
        if accuracy >= 0.75*ensa.config['interaction.max_accuracy'].value:
            color = log.COLOR_GREEN
        elif accuracy <= 0.25*ensa.config['interaction.max_accuracy'].value:
            color = log.COLOR_BROWN
    return '%s%-d  %s (%sacc %d%s%s)%s' % (
        color,
        # id_len,
        association_id,
        note if note else '',
        'lvl %d, ' % level if level else '',
        accuracy,
        (', mod ' + datetime_to_str(modified)) if use_modified else '',
        ', invalid' if not valid else '',
        log.COLOR_NONE,
    )


def format_information(information_id, subject_id, codename, info_type, name, level, accuracy, valid, modified, note, active, value, id_len, codename_len, name_len, value_len, keywords=None, use_codename=True, use_modified=True):
    color = log.COLOR_NONE
    if not valid:
        color = log.COLOR_DARK_RED
    elif not active:
        color = log.COLOR_GREY
    else:
        if accuracy >= 0.75*ensa.config['interaction.max_accuracy'].value:
            color = log.COLOR_GREEN
        elif accuracy <= 0.25*ensa.config['interaction.max_accuracy'].value:
            color = log.COLOR_BROWN
    return '%s%-*d %s %*s  %*s: %-*s  (%sacc %2d%s%s%s)  %s%s' % (
        color,
        id_len,
        information_id,
        '*' if os.path.isfile('files/binary/%d' % information_id) else ' ',
        codename_len,
        '<%s>' % codename if use_codename else '',
        name_len,
        name,
        value_len,
        ('{%s}' % ','.join(str(x) for x in value)
         if info_type == Database.INFORMATION_COMPOSITE
         else value),
        'lvl %d, ' % level if level else '',
        accuracy,
        (', mod ' + datetime_to_str(modified)) if use_modified else '',
        ', inactive' if not active else '',
        ', invalid' if not valid else '',
        (('# '+note) if note else '') if keywords is None else (', '.join(keywords)),
        log.COLOR_NONE,
    )


def format_location(location_id, name, lat, lon, accuracy, valid, modified, note, id_len, use_modified=True):
    # if gps:
    #    lat, _, lon = gps[6:-1].partition(' ')
    '''
    lat = '%c%d %d\' %.3f "' % (('N' if lat > 0 else 'S',)
                               + lib.degree_to_dms(lat))
    lon = '%c%d %d\' %.3f"' % (('E' if lon > 0 else 'W',)
                               + lib.degree_to_dms(lon))
    '''
    try:
        if type(lat) == str:
            lat = float(lat)
        if type(lon) == str:
            lon = float(lon)
        lat = '%.6f\u00b0 %c' % (abs(lat), 'N' if lat > 0 else 'S')
        lon = '%.6f\u00b0 %c' % (abs(lon), 'E' if lon > 0 else 'W')
        # lat = lat+'N' if float(lat)>0 else lat[1:]+'S'
        # lon = lon+'E' if float(lon)>0 else lon[1:]+'W'
        gps = '(%s %s)' % (lat, lon)
    except:
        lat = ''
        lon = ''
        gps = ''
    color = log.COLOR_NONE
    if not valid:
        color = log.COLOR_DARK_RED
    else:
        if accuracy >= 0.75*ensa.config['interaction.max_accuracy'].value:
            color = log.COLOR_GREEN
        elif accuracy <= 0.25*ensa.config['interaction.max_accuracy'].value:
            color = log.COLOR_BROWN
    return '%s%-*d  %s %s (acc %d%s%s) %s%s' % (
        color,
        id_len,
        location_id,
        name,
        gps if gps else '',
        accuracy,
        (', mod ' + datetime_to_str(modified)) if use_modified else '',
        ', invalid' if not valid else '',
        ('# '+note) if note else '',
        log.COLOR_NONE,
    )


def format_time(time_id, time, accuracy, valid, modified, note, id_len, use_modified=True):
    if type(time) == str:
        time = datetime_from_str(time)
    color = log.COLOR_NONE
    if not valid:
        color = log.COLOR_DARK_RED
    else:
        if accuracy >= 0.75*ensa.config['interaction.max_accuracy'].value:
            color = log.COLOR_GREEN
        elif accuracy <= 0.25*ensa.config['interaction.max_accuracy'].value:
            color = log.COLOR_BROWN
    return '%s%-*d  %s  (acc %d%s%s) %s%s' % (
        color,
        id_len,
        time_id,
        #dateutil.parser.parse(time).strftime('%Y-%m-%d %H:%M:%S'),
        datetime_to_str(time),
        # datetime.strptime(time).strftime('%Y-%m-%d %H:%M:%S'),
        # time if time else '',
        accuracy,
        (', mod ' + datetime_to_str(modified)) if use_modified else '',
        ', invalid' if not valid else '',
        ('# '+note) if note else '',
        log.COLOR_NONE,
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
    # DUMP written commands, including empty newlines
    # TODO set up proper command for this
    for command in ensa.history:
        print(command)
    return result


add_command(Command('test', 'do actually tested action', '', test_function))


def prompt_function(*_):  # TODO for testing only!
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
    if len(associations) == 1:
        ensa.variables['last'] = associations[0][0]
    return [format_association(*association, use_modified=True)
            for association in associations]


add_command(Command('a', 'list associations for this ring', 'a', a_function))
add_command(Command('aa', 'association creation', 'aa', lambda *_: []))


def aaa_function(*args):
    try:
        association_id = args[0]
    except:
        log.err('Main association ID must be specified.')
        return []
    try:
        association_ids = parse_sequence(','.join(args[1:]))
        if not association_ids:
            raise AttributeError
    except:
        log.err('Inferior association ID must be specified.')
        return []
    ensa.db.associate_association(association_id, association_ids)
    ensa.variables['last'] = association_id
    return []


add_command(Command('aaa <association_id> <association_ids>',
                    'associate associations to an association', 'aaa', aaa_function))


def aai_function(*args):
    try:
        association_id = args[0]
    except:
        log.err('Association ID must be specified.')
        return []
    try:
        information_ids = parse_sequence(','.join(args[1:]))
        if not information_ids:
            raise AttributeError
    except:
        log.err('Information ID must be specified.')
        return []
    ensa.db.associate_information(association_id, information_ids)
    ensa.variables['last'] = association_id
    return []


add_command(Command('aai <association_id> <information_ids>',
                    'associate information entries to an association', 'aai', aai_function))


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
    ensa.variables['last'] = association_id
    return []


add_command(Command('aal <association_id> <location_ids>',
                    'associate location entries to an association', 'aal', aal_function))


def aas_function(*args):
    try:
        association_id = args[0]
    except:
        log.err('Association ID must be specified.')
        return []
    try:
        # codenames = ','.join(['\'%s\'' % codename for codename in args[1:]])
        codenames = args[1:]
        if not codenames:
            raise AttributeError
    except:
        log.err('Subject codename must be specified.')
        return []
    ensa.db.associate_subject(association_id, codenames)
    ensa.variables['last'] = association_id
    return []


add_command(Command('aas <association_id> <codename>',
                    'associate subject to an association', 'aas', aas_function))


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
    ensa.variables['last'] = association_id
    return []


add_command(Command('aat <association_id> <time_ids>',
                    'associate time entries to an association', 'aat', aat_function))


def aaw_function(*_):
    if not ensa.current_ring:
        log.err('First select a ring with `rs <name>`.')
        return []
    note, level, accuracy, valid, confirm = wizard([
        'Description:',
        'Optional level of importance:',
        'Accuracy of this entry (default 0):',
        'Is the entry valid?',
        '... Use provided information to create new association?',
    ])
    if negative(confirm):
        return []
    level = int(level) if level.isdigit() else None
    accuracy = int(accuracy) if accuracy.isdigit() else 0
    valid = not negative(valid)
    association_id = ensa.db.create_association(level, accuracy, valid, note)
    if association_id:
        ensa.variables['last'] = association_id
        log.info('Created new association with id #%d' % association_id)
    return []


add_command(Command(
    'aaw', 'use wizard to add new association to current ring', 'aaw', aaw_function))


def ad_function(*args):
    try:
        association_id = args[0]
        ensa.db.delete_associations(association_id)
    except:
        log.err('Association ID must be specified.')
        return []
    return []


add_command(Command('ad <association_id>',
                    'delete whole association', 'ad', ad_function))


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


add_command(Command('ada <association_id> <association_ids>',
                    'remove associations from an association', 'ada', ada_function))


def adi_function(*args):
    try:
        association_id = args[0]
    except:
        log.err('Association ID must be specified.')
        return []
    try:
        ids = parse_sequence(','.join(args[1:]))
        if not ids:
            raise ValueError
    except:
        log.err('Information ID must be specified.')
        return []
    ensa.db.dissociate_informations(association_id, ids)
    return []


add_command(Command('adi <association_id> <information_ids>',
                    'remove information entries from an association', 'adi', adi_function))


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


add_command(Command('adl <association_id> <location_ids>',
                    'remove locations from an association', 'adl', adl_function))


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


add_command(Command('adt <association_id> <time_ids>',
                    'remove times from an association', 'adt', adt_function))


def ag_function(*args, data_function=lambda *_: [], id_type=0, prepend_times=False, hide_details=False, use_modified=True):

    if id_type == 0:  # ID sequence, parse it
        ids = ','.join(parse_sequence(','.join(args)))
    # elif id_type == 1:  # list of words, join it with ',' - tuple is dealt with by DB methods
    #    ids = ','.join('\'%s\'' % arg for arg in args)
    elif id_type == 2:  # string, join it with ' '
        ids = ' '.join(args)
    # elif id_type == 3:  # keep it as tuple
    #    ids = args
    else:
        ids = args
    if not ids:
        log.err('Identifier must be specified.')
        return []
    result = []
    # data = ensa.db.get_associations_by_ids(ids)
    data = data_function(ids)
    if not data:
        return []
    if len(data) == 1:
        ensa.variables['last'] = data[0][0][0]
    for association, infos, times, locations, associations in data:
        aresult = []

        time = '%s  ' % times[0][1] if times and prepend_times else ''
        aresult.append(('{grepignore}%s#A' % time) +
                       format_association(*association, use_modified=use_modified))
        if not hide_details:
            info_lens = get_format_len_information(infos)
            time_lens = get_format_len_time(times)
            location_lens = get_format_len_location(locations)
            for info in infos:
                aresult.append('    #I'+format_information(*info,
                                                           *info_lens, use_modified=False))
            for time in times:
                aresult.append('    #T'+format_time(*time, *
                                                    time_lens, use_modified=False))
            for location in locations:
                aresult.append('    #L'+format_location(*location,
                                                        *location_lens, use_modified=False))
            for a in associations:
                aresult.append(
                    '    #A'+format_association(*a, use_modified=False))
        result.append(aresult)
    return result


add_command(Command('ag', 'show associations', 'ag', lambda *_: []))
add_command(Command('aga <association_ids>', 'show associations with specific ID', 'aga', lambda *args: ag_function(*
                                                                                                                    args, data_function=lambda ids: ensa.db.get_associations_by_ids(ids), prepend_times=False)))
add_command(Command('agl <location_ids>', 'show associations with specific location', 'aga', lambda *args: ag_function(*
                                                                                                                       args, data_function=lambda ids: ensa.db.get_associations_by_location(ids), prepend_times=False)))
add_command(Command('agt <time_ids>', 'show associations with specific time entry', 'agt', lambda *args: ag_function(*
                                                                                                                     args, data_function=lambda ids: ensa.db.get_associations_by_time(ids), prepend_times=False)))
add_command(Command('agi <information_ids>', 'show associations with specific information', 'agi',
                    lambda *args: ag_function(*args, data_function=lambda ids: ensa.db.get_associations_by_information(ids), prepend_times=False)))
add_command(Command('ags <codenames>', 'show associations for specific subject', 'ags', lambda *args: ag_function(*args,
                                                                                                                  data_function=lambda codenames: ensa.db.get_associations_by_subject(codenames), id_type=1, prepend_times=False)))
add_command(Command('agn <string>', 'show associations matching description', 'agn', lambda *args: ag_function(*
                                                                                                               args, data_function=lambda string: ensa.db.get_associations_by_note(string), id_type=2, prepend_times=False)))


add_command(Command('am', 'modify association', 'im', lambda *args: []))


def ame_function(*args):
    try:
        association_id = args[0]
    except:
        log.err('Association ID must be specified.')
        return []
    # get values
    data = ensa.db.get_association(association_id)
    if not data:
        return []
    mapped = dict(zip([None, 'level', 'accuracy', 'valid', 'note'], [
                  (x if type(x) == bytearray else x) if x else '' for x in data]))
    # print(mapped)
    # write into file
    with tempfile.NamedTemporaryFile() as f:
        for k in sorted(filter(None, mapped.keys())):
            f.write(('%s: %s\n' % (k, mapped[k])).encode())
        f.flush()
        subprocess.call((ensa.config['external.editor'].value % (f.name)).split())
        f.seek(0)
        # retrieve changes
        changes = f.read().decode()
    change_occured = False
    for line in changes.splitlines():
        k, _, v = line.partition(': ')
        if k not in mapped.keys():  # ingore unknown keys
            continue
        try:
            v = type(mapped[k])(v.strip())
        except:
            if type(mapped[k]) == int and not v.strip():
                v = 0
            else:
                raise
        if mapped[k] != v:
            # print('value of', k, '-', v, type(v), 'does not match the original', mapped[k], type(mapped[k]))
            change_occured = True
            # check validity and save valid changes
            if k == 'accuracy':
                if type(v) == int or v.isdigit():
                    mapped[k] = int(v)
                else:
                    log.err('Accuracy must be a number.')
                    change_occured = False
                    break
            elif k == 'valid':
                mapped[k] = positive(v)
            elif k == 'level':
                if type(v) == int or v.isdigit():
                    mapped[k] = int(v)
                elif v == '':
                    mapped[k] = None
                else:
                    log.err('Level must be empty or a number.')
                    change_occured = False
                    break
            elif k == 'note':
                mapped[k] = v if v else None
    if change_occured:
        # update DB
        del mapped[None]
        mapped['association_id'] = association_id
        # print(mapped)
        ensa.db.update_association(**mapped)
        log.info('Association %s successfully changed.' % association_id)
    else:
        log.info('No change has been done.')
    return []


add_command(Command('ame <association_id>',
                    'modify association with editor', 'ame', ame_function))


def ama_function(*args):
    try:
        association_ids = ','.join(parse_sequence(args[0]))
    except:
        log.err('Association ID must be specified.')
        return []
    try:
        value = int(args[1])
    except:
        log.err('Value must be a number.')
        return []
    ensa.db.update_association_metadata(association_ids, accuracy=value)
    log.info('Accuracy updated.')
    return []


add_command(Command('ama <association_ids> <value>',
                    'modify association accuracy', 'ama', ama_function))


def aml_function(*args):
    try:
        association_ids = ','.join(parse_sequence(args[0]))
    except:
        log.err('Association ID must be specified.')
        return []
    try:
        value = int(args[1])
    except:
        value = None
    ensa.db.update_association_metadata(association_ids, level=value)
    log.info('Level updated.')
    return []


add_command(Command(
    'aml <association_ids> [<value>]', 'modify association level', 'aml', aml_function))


def amd_function(*args):
    try:
        association_ids = ','.join(parse_sequence(args[0]))
    except:
        log.err('Association ID must be specified.')
        return []
    try:
        value = ' '.join(args[1:])
    except:
        log.err('Value must be defined.')
        return []
    ensa.db.update_association_metadata(association_ids, note=value)
    log.info('Note updated.')
    return []


add_command(Command('amd <association_id> <value>',
                    'modify association description', 'amd', amd_function))


def amv_function(*args):
    try:
        association_ids = ','.join(parse_sequence(args[0]))
    except:
        log.err('Association ID must be specified.')
        return []
    try:
        value = '1' if positive(args[1]) else '0'
    except:
        log.err('Value must be defined.')
        return []
    ensa.db.update_association_metadata(association_ids, valid=value)
    log.info('Validity updated.')
    return []


add_command(Command('amv <association_ids> <value>',
                    'modify association validity', 'amv', amv_function))


def amaw_function(*args):
    try:
        association_ids = [x for x in parse_sequence(args[0])]
        associations = [x for x in ensa.db.get_associations()
                        if str(x[0]) in association_ids]
        association_ids = [str(x[0]) for x in associations]
        # association_lens = get_format_len_association(associations)
    except:
        log.err('Association ID must be specified.')
        return []
    for association_id, association in zip(association_ids, associations):
        # log.info(format_association(*association, *association_lens, use_modified=True))
        log.info(format_association(*association, use_modified=True))
        while True:
            value, = wizard(['   Accuracy for this entry:'])
            try:
                value = int(value)
                break
            except:
                log.err('Accuracy must be a number.')
        old = association[3]
        if old != value:
            ensa.db.update_association_metadata(association_id, accuracy=value)
    return []


add_command(Command('amaw <association_ids>',
                    'use wizard to modify association accuracy', 'amaw', amaw_function))


def amlw_function(*args):
    try:
        association_ids = [x for x in parse_sequence(args[0])]
        associations = [x for x in ensa.db.get_associations()
                        if str(x[0]) in association_ids]
        association_ids = [str(x[0]) for x in associations]
        # association_lens = get_format_len_association(associations)
    except:
        log.err('Association ID must be specified.')
        return []
    for association_id, association in zip(association_ids, associations):
        # log.info(format_association(*association, *association_lens, use_modified=True))
        log.info(format_association(*association, use_modified=True))
        while True:
            value, = wizard(['   Level for this entry:'])
            if not value:
                value = None
                break
            else:
                try:
                    value = int(value)
                    break
                except:
                    log.err('Level must be a number or empty.')

        old = association[2]
        if old != value:
            ensa.db.update_association_metadata(association_id, level=value)
    return []


add_command(Command('amlw <association_ids>',
                    'use wizard to modify association level', 'amlw', amlw_function))


def amdw_function(*args):
    try:
        association_ids = [x for x in parse_sequence(args[0])]
        associations = [x for x in ensa.db.get_associations()
                        if str(x[0]) in association_ids]
        association_ids = [str(x[0]) for x in associations]
        # association_lens = get_format_len_association(associations)
    except:
        log.err('Association ID must be specified.')
        return []
    for association_id, association in zip(association_ids, associations):
        # log.info(format_association(*association, *association_lens, use_modified=True))
        log.info(format_association(*association, use_modified=True))
        value, = wizard(['   Note for this entry:'])
        if not value:
            value = None
        old = association[6]
        if old != value:
            ensa.db.update_association_metadata(association_id, note=value)
    return []


add_command(Command('amdw <association_ids>',
                    'use wizard to modify association description', 'amdw', amdw_function))


def amvw_function(*args):
    try:
        association_ids = [x for x in parse_sequence(args[0])]
        associations = [x for x in ensa.db.get_associations()
                        if str(x[0]) in association_ids]
        association_ids = [str(x[0]) for x in associations]
        # association_lens = get_format_len_association(associations) # TODO
    except:
        log.debug_error()
        log.err('Association ID must be specified.')
        return []
    for association_id, association in zip(association_ids, associations):
        # log.info(format_association(*association, *association_lens, use_modified=True))
        log.info(format_association(*association, use_modified=True))
        value, = wizard(['   Should this entry be valid?'])
        value = positive(value)
        old = positive(association[4])
        print(old, value)
        if value ^ old:
            print('changing')
            ensa.db.update_association_metadata(association_id, valid=value)
    return []


add_command(Command('amvw <association_ids>',
                    'use wizard to modify association validity', 'amvw', amvw_function))


"""
INFORMATION COMMANDS
"""
# TODO list standard names in help
add_command(Command(
    'i', 'print information overview for current subject', 'i', lambda *_: ['TODO']))
add_command(
    Command('ia', 'add information to current subject', 'ia', lambda *_: []))


def iab_function(*args):
    try:
        if len(args) == 3:
            """add new information"""
            name = args[0].lower()
            value = args[1]
            filename = args[2]
            information_id = ensa.db.create_information(
                Database.INFORMATION_TEXT,
                name,
                value)
        elif len(args) == 2:
            """add content to existing information"""
            information_id = int(args[0])
            filename = args[1]
        else:
            raise AttributeError
        with open('files/uploads/%s' % filename, 'rb') as f:
            pass
        ensa.db.add_binary(information_id, filename)

        ensa.variables['last'] = information_id
        return information_id
    except:
        log.debug_error()
        return None
    return None


add_command(Command('iab (<id>|<name> <value>) <filename>',
                    'add binary information from uploads/ folder to current subject',
                    'iab',
                    iab_function))


def iac_function(*args):
    try:
        name = args[0].lower()
        parts = parse_sequence(','.join(args[1:]))
        if not parts:
            log.err('At least one information ID must be specified.')
            return []
        information_id = ensa.db.create_information(
            Database.INFORMATION_COMPOSITE, name, parts)
        ensa.variables['last'] = information_id
    except:
        log.debug_error()
        return []
    return []


add_command(Command('iac <name> <information_ids>',
                    'add composite information to current subject', 'iac', iac_function))


def iat_function(*args):
    try:
        name = args[0].lower()
        value = ' '.join(args[1:])
        if not value:
            log.err('Value must be specified.')
            return []
        information_id = ensa.db.create_information(Database.INFORMATION_TEXT,
                                                    name,
                                                    value)
        ensa.variables['last'] = information_id
        return []
    except:
        log.debug_error()
        return []


add_command(Command('iat <name> <value>',
                    'add textual information to current subject',
                    'iat',
                    iat_function))


def iak_function(*args):
    if not ensa.current_subject:
        log.err('You must choose a subject with `ss` command.')
    try:
        information_ids = parse_sequence(args[0])
    except:
        log.err('Information ID must be specified.')
        return []
    keywords = args[1:]
    if not keywords:
        log.err('A keyword must be specified.')
        return []
    for keyword in keywords:
        ensa.db.add_keyword(information_ids, keyword)
    # ensa.variables['last'] = information_id
    return []


add_command(Command('iak <information_ids> <keywords>',
                    'add keywords to information', 'iak', iak_function))


def id_function(*args):
    try:
        information_id = args[0]
    except:
        log.err('ID of information must be specified.')
        return []
    ensa.db.delete_information(information_id)  # TODO range
    return []


add_command(Command('id <information_id>',
                    'delete information of current subject', 'id', id_function))


def idk_function(*args):
    try:
        information_id = args[0]
    except:
        log.err('Information ID must be specified.')
    try:
        keywords = ','.join(['\'%s\'' % x for x in args[1:]])
    except:
        keywords = None
    ensa.db.delete_keywords(information_id, keywords)


add_command(Command('idk <information_id> [<keyword>]',
                    'delete keywords from information', 'idk', idk_function))

'''
def igb_function(*args, no_composite_parts=True):
    result = []
    infos = ensa.db.get_informations(Database.INFORMATION_BINARY,
                                     no_composite_parts)
    if not infos:
        return []
    """use info id as last if only one is found"""
    if len(infos) == 1:
        ensa.variables['last'] = infos[0][0]
    info_lens = get_format_len_information(infos)
    result = [format_information(
        *info, *info_lens, use_codename=(ensa.current_subject is None)) for info in infos]
    return result
add_command(Command(
    'igb', 'get all binary information for current subject/ring', 'igb', igb_function))
add_command(Command('igbc', 'get all binary information (even composite parts) for current subject/ring',
            'igbc', lambda *args: igb_function(args, no_composite_parts=False)))
'''


def ig_function(*args, info_type=Database.INFORMATION_ALL, no_composite_parts=True):
    result = []
    infos = ensa.db.get_informations(info_type, no_composite_parts)
    if not infos:
        return []
    """use info id as last if only one is found"""
    if len(infos) == 1:
        ensa.variables['last'] = infos[0][0]
    info_lens = get_format_len_information(infos)
    result = [format_information(
        *info, *info_lens, use_codename=(ensa.current_subject is None)) for info in infos]
    return result


add_command(Command('ig', 'get all information for current subject/ring',
                    'ig', lambda *args: ig_function(*args)))
add_command(Command('iga', 'get all information including composite parts for current subject/ring',
                    'igc', lambda *args: ig_function(*args, no_composite_parts=False)))
# TODO igc - composite, igca - composite with values (tree)
add_command(Command('igt', 'get all textual information for current subject/ring',
                    'igt', lambda *args: ig_function(*args, info_type=Database.INFORMATION_TEXT)))
add_command(Command('igta', 'get all textual information including composite parts for current subject/ring',
                    'igtc', lambda *args: ig_function(args, info_type=Database.INFORMATION_TEXT, no_composite_parts=False)))


def igk_function(*args):
    result = []
    infos = ensa.db.get_informations()
    if not infos:
        return []
    if len(infos) == 1:
        ensa.variables['last'] = infos[0][0]
    keywords = ensa.db.get_keywords_for_informations(
        ','.join([str(x[0]) for x in infos]))
    info_lens = get_format_len_information(infos)
    result = [format_information(*info, *info_lens, keywords=sorted(x[1] for x in keywords if x[0]
                                                                    == info[0]), use_codename=(ensa.current_subject is None)) for info in infos]
    return result


add_command(Command(
    'igk', 'get all information with keywords for current subject', 'igk', igk_function))


def igbk_all_function(*args):
    keywords = ','.join(['\'%s\'' % x for x in args])
    if not keywords:
        log.err('Keyword must be specified.')
        return []
    infos = ensa.db.get_informations_for_keywords_and(keywords)
    if not infos:
        return []
    if len(infos) == 1:
        ensa.variables['last'] = infos[0][0]
    info_lens = get_format_len_information(infos)
    result = [format_information(
        *info, *info_lens, use_codename=(ensa.current_subject is None)) for info in infos]
    return result


add_command(Command('igbk= <keyword>',
                    'get information having all keywords', 'igbk=', igbk_all_function))


def igbk_or_function(*args):
    keywords = ','.join(['\'%s\'' % x for x in args])
    if not keywords:
        log.err('Keyword must be specified.')
        return []
    infos = ensa.db.get_informations_for_keywords_or(keywords)
    if not infos:
        return []
    if len(infos) == 1:
        ensa.variables['last'] = infos[0][0]
    info_lens = get_format_len_information(infos)
    result = [format_information(
        *info, *info_lens, use_codename=(ensa.current_subject is None)) for info in infos]
    return result


add_command(Command('igbk <keyword>',
                    'get information having any of keywords', 'igbk', igbk_or_function))


add_command(Command('im', 'modify information', 'im', lambda *args: []))


def ime_function(*args):
    try:
        information_id = args[0]
    except:
        log.err('ID of information must be specified.')
        return []
    # get values
    data = ensa.db.get_information(information_id)
    if not data:
        return []
    # add labels
    if data[2] == ensa.db.INFORMATION_TEXT:
        value_column = 'value'
        '''
        elif data[2] == ensa.db.INFORMATION_BINARY:
            value_column = 'path'
        '''
    # elif data[2] == ensa.db.INFORMATION_COMPOSITE: # TODO composite without edit support?
    #    value_column = 'compounds'
    else:
        value_column = 'ERROR'
    mapped = dict(zip([None, 'subject', None, 'name', 'level', 'accuracy', 'valid', 'note', value_column], [
                  (x if type(x) == bytearray else x) if x is not None else '' for x in data]))
    # write into file
    with tempfile.NamedTemporaryFile() as f:
        for k in sorted(filter(None, mapped.keys())):
            f.write(('%s: %s\n' % (k, mapped[k])).encode())
        f.flush()
        subprocess.call((ensa.config['external.editor'].value % (f.name)).split())
        f.seek(0)
        # retrieve changes
        changes = f.read().decode()
    change_occured = False
    for line in changes.splitlines():
        k, _, v = line.partition(': ')
        if k not in mapped.keys():  # ingore unknown keys
            continue
        try:
            v = type(mapped[k])(v.strip())
        except:
            if type(mapped[k]) == int and not v.strip():
                v = 0
            else:
                raise
        if mapped[k] != v:
            # print('value of', k, '-', v, type(v), 'does not match the original', mapped[k], type(mapped[k]))
            change_occured = True
            # check validity and save valid changes
            if k == 'accuracy':
                if type(v) == int or v.isdigit():
                    mapped[k] = int(v)
                else:
                    mapped[k] = 0
                    # log.err('Accuracy must be a number.')
                    # change_occured = False
                    # break
            elif k == 'valid':
                mapped[k] = positive(v)
            elif k == 'level':
                if type(v) == int or v.isdigit():
                    mapped[k] = int(v)
                elif v == '':
                    mapped[k] = None
                else:
                    log.err('Level must be empty or a number.')
                    change_occured = False
                    break
            elif k in ['name', 'value']:
                if v:
                    mapped[k] = v
                else:
                    log.err('%s must be defined.' % (k.title()))
                    change_occured = False
                    break
            elif k == 'note':
                mapped[k] = v if v else None
            # TODO composite
            elif k == 'subject':
                if v:
                    subject_id = ensa.db.select_subject(v)
                    if subject_id:
                        mapped['subject_id'] = subject_id
                    else:
                        log.err('No such subject exists in current ring.')
                        change_occured = False
                        break
                else:
                    log.err('Subject must be specified.')
                    change_occured = False
                    break
    if change_occured:
        # update DB
        del mapped[None]
        mapped['information_id'] = information_id
        if 'subject_id' not in mapped.keys():
            mapped['subject_id'] = ensa.current_subject
        # print(mapped)
        ensa.db.update_information(**mapped)
        log.info('Information %s successfully changed.' % information_id)
    else:
        log.info('No change has been done.')
    return []


add_command(Command('ime <information_id>',
                    'modify information with editor', 'ime', ime_function))


def ima_function(*args):
    try:
        information_ids = ','.join(parse_sequence(args[0]))
    except:
        log.err('Information ID must be specified.')
        return []
    try:
        value = int(args[1])
    except:
        log.err('Value must be a number.')
        return []
    ensa.db.update_information_metadata(information_ids, accuracy=value)
    log.info('Accuracy updated.')
    return []


add_command(Command('ima <information_ids> <value>',
                    'modify information accuracy', 'ima', ima_function))


def iml_function(*args):
    try:
        information_ids = ','.join(parse_sequence(args[0]))
    except:
        log.err('Information ID must be specified.')
        return []
    try:
        value = int(args[1])
    except:
        value = None
    ensa.db.update_information_metadata(information_ids, level=value)
    log.info('Level updated.')
    return []


add_command(Command(
    'iml <information_ids> [<value>]', 'modify information level', 'iml', iml_function))


def imn_function(*args):
    try:
        information_ids = ','.join(parse_sequence(args[0]))
    except:
        log.err('Information ID must be specified.')
        return []
    try:
        value = ' '.join(args[1:])
    except:
        log.err('Value must be defined.')
        return []
    ensa.db.update_information_metadata(information_ids, note=value)
    log.info('Note updated.')
    return []


add_command(Command('imn <information_id> <value>',
                    'modify information note', 'imn', imn_function))


def imr_function(*args):
    try:
        information_ids = parse_sequence(args[0])
    except:
        log.err('Information ID must be specified.')
        return []
    value = positive(args[1])

    if len(information_ids) == 1:
        ensa.variables['last'] = information_ids[0]
    ensa.db.set_active(information_ids, 
                       ensa.variables['reference_time_id'], 
                       value)
    log.info('Activity updated.')
    return []

add_command(Command('imr <information_ids> <value>',
                    'modify information active state for current reference time', 
                    'imr', 
                    imr_function))


def imv_function(*args):
    try:
        information_ids = ','.join(parse_sequence(args[0]))
    except:
        log.err('Information ID must be specified.')
        return []
    try:
        value = '1' if positive(args[1]) else '0'
    except:
        log.err('Value must be defined.')
        return []
    ensa.db.update_information_metadata(information_ids, valid=value)
    log.info('Validity updated.')
    return []


add_command(Command('imv <information_ids> <value>',
                    'modify information validity', 'imv', imv_function))


def imaw_function(*args):
    try:
        information_ids = [x for x in parse_sequence(args[0])]
        informations = [x for x in ensa.db.get_informations()
                        if str(x[0]) in information_ids]
        information_ids = [str(x[0]) for x in informations]
        information_lens = get_format_len_information(informations)
    except:
        log.err('Information ID must be specified.')
        return []
    for information_id, information in zip(information_ids, informations):
        log.info(format_information(*information, *
                                    information_lens, use_modified=True))
        while True:
            value, = wizard(['   Accuracy for this entry:'])
            try:
                value = int(value)
                break
            except:
                log.err('Accuracy must be a number.')
        old = information[6]
        if old != value:
            ensa.db.update_information_metadata(information_id, accuracy=value)
    return []


add_command(Command('imaw <information_ids>',
                    'use wizard to modify information accuracy', 'imaw', imaw_function))


def imlw_function(*args):
    try:
        information_ids = [x for x in parse_sequence(args[0])]
        informations = [x for x in ensa.db.get_informations()
                        if str(x[0]) in information_ids]
        information_ids = [str(x[0]) for x in informations]
        information_lens = get_format_len_information(informations)
    except:
        log.err('Information ID must be specified.')
        return []
    for information_id, information in zip(information_ids, informations):
        log.info(format_information(*information, *
                                    information_lens, use_modified=True))
        while True:
            value, = wizard(['   Level for this entry:'])
            if not value:
                value = None
                break
            else:
                try:
                    value = int(value)
                    break
                except:
                    log.err('Level must be a number or empty.')

        old = information[5]
        if old != value:
            ensa.db.update_information_metadata(information_id, level=value)
    return []


add_command(Command('imlw <information_ids>',
                    'use wizard to modify information level', 'imlw', imlw_function))


def imnw_function(*args):
    try:
        information_ids = [x for x in parse_sequence(args[0])]
        informations = [x for x in ensa.db.get_informations()
                        if str(x[0]) in information_ids]
        information_ids = [str(x[0]) for x in informations]
        information_lens = get_format_len_information(informations)
    except:
        log.err('Information ID must be specified.')
        return []
    for information_id, information in zip(information_ids, informations):
        log.info(format_information(*information, *
                                    information_lens, use_modified=True))
        value, = wizard(['   Note for this entry:'])
        if not value:
            value = None
        old = information[9]
        if old != value:
            ensa.db.update_information_metadata(information_id, note=value)
    return []


add_command(Command('imnw <information_ids>',
                    'use wizard to modify informatio note', 'imnw', imnw_function))


def imvw_function(*args):
    try:
        information_ids = [x for x in parse_sequence(args[0])]
        informations = [x for x in ensa.db.get_informations()
                        if str(x[0]) in information_ids]
        information_ids = [str(x[0]) for x in informations]
        information_lens = get_format_len_information(informations)  # TODO
    except:
        log.debug_error()
        log.err('Information ID must be specified.')
        return []
    for information_id, information in zip(information_ids, informations):
        log.info(format_information(*information, *
                                    information_lens, use_modified=True))
        value, = wizard(['   Should this entry be valid?'])
        value = positive(value)
        old = positive(information[7])
        print(old, value)
        if value ^ old:
            print('changing')
            ensa.db.update_information_metadata(information_id, valid=value)
    return []


add_command(Command('imvw <information_ids>',
                    'use wizard to modify information validity', 'imvw', imvw_function))

"""
KEYWORD COMMANDS
"""
# other keyword methods are under Information


def k_function(*args):
    result = [x[0] for x in ensa.db.get_keywords()]
    if len(result) == 1:
        ensa.variables['last'] = result[0]
    return result


add_command(
    Command('k', 'list keywords in current ring/subject', 'k', k_function))


"""
LOCATION COMMANDS
"""


def l_function(*_):
    locations = ensa.db.get_locations()
    if not locations:
        return []
    location_lens = get_format_len_location(locations)
    if len(locations) == 1:
        ensa.variables['last'] = locations[0][0]
    '''
    # visualization testing # TODO move
    labels = [location[1] for location in locations]
    coords = [location[2:4] for location in locations]
    get_map(coords, labels).savefig(
        'files/tmp/map.png', bbox_inches='tight', pad_inches=0)
    '''
    return [format_location(*location, *location_lens, use_modified=True)
            for location in locations]


add_command(Command('l', 'list locations for current ring', 'l', l_function))
add_command(Command('la', 'add new location for current ring',
                    'la', lambda *_: ['TODO']))


def law_function(*_):
    if not ensa.current_ring:
        log.err('First select a ring with `rs <name>`.')
        return []
    name, lat, lon, accuracy, valid, note, confirm = wizard([
        'Name of the place:',
        'Latitude (e.g. -50.079795):',
        'Longitude (e.g. -14.429710):',
        'Accuracy of this entry (default 0):',
        'Is the entry valid?',
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
    valid = not negative(valid)
    location_id = ensa.db.create_location(
        name, lat, lon, accuracy, valid, note)
    if location_id:
        ensa.variables['last'] = location_id
        log.info('Created new location with id #%d' % location_id)
    else:
        log.err('Adding new location failed.')
    return []


add_command(Command('law',
                    'use wizard to add new location to current ring',
                    'law',
                    law_function))


def ld_function(*args):
    try:
        location_ids = ','.join(parse_sequence(','.join(args)))
        ensa.db.delete_locations(location_ids)
    except:
        log.debug_error()
        log.err('Correct location ID from this ring must be provided.')
    return []


add_command(Command('ld <location_id>',
                    'delete location entry from current ring',
                    'ld',
                    ld_function))


add_command(Command('lm', 'modify location', 'lm', lambda *args: []))


def lme_function(*args):
    try:
        location_id = args[0]
    except:
        log.err('Location ID must be specified.')
        return []
    # get values
    data = ensa.db.get_location(location_id)
    if not data:
        return []
    '''
    lat, _, lon = data[2].partition('(')[2].partition(
        ' ') if data[2] else (None, None, None)
    if lon:
        lon = lon[:-1]
    data = data[:2]+(lat, lon)+data[3:]
    '''
    # add labels
    mapped = dict(zip([None, 'name', 'lat', 'lon', 'accuracy', 'valid', 'note'], [
                  (x if type(x) == bytearray else x) if x else '' for x in data]))
    # print(mapped)
    # write into file
    with tempfile.NamedTemporaryFile() as f:
        for k in sorted(filter(None, mapped.keys())):
            f.write(('%s: %s\n' % (k, mapped[k])).encode())
        f.flush()
        subprocess.call((ensa.config['external.editor'].value % (f.name)).split())
        f.seek(0)
        # retrieve changes
        changes = f.read().decode()
    change_occured = False
    for line in changes.splitlines():
        k, _, v = line.partition(': ')
        if k not in mapped.keys():  # ingore unknown keys
            continue
        try:
            v = type(mapped[k])(v.strip())
        except:
            if type(mapped[k]) == int and not v.strip():
                v = 0
            else:
                raise
        if mapped[k] != v:
            # print('value of', k, '-', v, type(v), 'does not match the original', mapped[k], type(mapped[k]))
            change_occured = True
            # check validity and save valid changes
            if k == 'accuracy':
                if type(v) == int or v.isdigit():
                    mapped[k] = int(v)
                else:
                    mapped[k] = 0
                    # log.err('Accuracy must be a number.')
                    # change_occured = False
                    # break
            elif k == 'valid':
                mapped[k] = positive(v)
            elif k == 'name':
                if v:
                    mapped[k] = v
                else:
                    log.err('%s must be defined.' % (k.title()))
                    change_occured = False
                    break
            elif k in ['lat', 'lon']:
                try:
                    v = float(v)
                    mapped[k] = v
                except:
                    log.err('Latitude and longitude must be numbers.')
                    change_occured = False
                    break
            elif k == 'note':
                mapped[k] = v if v else None
    if change_occured:
        # update DB
        del mapped[None]
        if type(mapped['lat']) == float:
            mapped['lat'] = str(mapped['lat'])
        if type(mapped['lon']) == float:
            mapped['lon'] = str(mapped['lon'])
        mapped['location_id'] = location_id
        ensa.db.update_location(**mapped)
        log.info('Location %s successfully changed.' % location_id)
    else:
        log.info('No change has been done.')
    return []


add_command(Command('lme <location_id>',
                    'modify location with editor', 'lme', lme_function))


def lma_function(*args):
    try:
        location_ids = ','.join(parse_sequence(args[0]))
    except:
        log.err('Location ID must be specified.')
        return []
    try:
        value = int(args[1])
    except:
        log.err('Value must be a number.')
        return []
    ensa.db.update_location_metadata(location_ids, accuracy=value)
    log.info('Accuracy updated.')
    return []


add_command(Command('lma <location_ids> <value>',
                    'modify location accuracy', 'lma', lma_function))


def lmn_function(*args):
    try:
        location_ids = ','.join(parse_sequence(args[0]))
    except:
        log.err('Location ID must be specified.')
        return []
    try:
        value = ' '.join(args[1:])
    except:
        log.err('Value must be defined.')
        return []
    ensa.db.update_location_metadata(location_ids, note=value)
    log.info('Note updated.')
    return []


add_command(Command('lmn <location_ids> <value>',
                    'modify location note', 'lmn', lmn_function))


def lmv_function(*args):
    try:
        location_ids = ','.join(parse_sequence(args[0]))
    except:
        log.err('Location ID must be specified.')
        return []
    try:
        value = '1' if positive(args[1]) else '0'
    except:
        log.err('Value must be defined.')
        return []
    ensa.db.update_location_metadata(location_ids, valid=value)
    log.info('Validity updated.')
    return []


add_command(Command('lmv <location_ids> <value>',
                    'modify location validity', 'lmv', lmv_function))


def lmaw_function(*args):
    try:
        location_ids = [x for x in parse_sequence(args[0])]
        locations = [x for x in ensa.db.get_locations() if str(x[0])
                     in location_ids]
        location_ids = [str(x[0]) for x in locations]
        location_lens = get_format_len_location(locations)
    except:
        log.err('Location ID must be specified.')
        return []
    for location_id, location in zip(location_ids, locations):
        log.info(format_location(*location, *location_lens, use_modified=True))
        while True:
            value, = wizard(['   Accuracy for this entry:'])
            try:
                value = int(value)
                break
            except:
                log.err('Accuracy must be a number.')
        old = location[3]
        if old != value:
            ensa.db.update_location_metadata(location_id, accuracy=value)
    return []


add_command(Command('lmaw <location_ids>',
                    'use wizard to modify location accuracy', 'lmaw', lmaw_function))


def lmnw_function(*args):
    try:
        location_ids = [x for x in parse_sequence(args[0])]
        locations = [x for x in ensa.db.get_locations() if str(x[0])
                     in location_ids]
        location_ids = [str(x[0]) for x in locations]
        location_lens = get_format_len_location(locations)
    except:
        log.err('Location ID must be specified.')
        return []
    for location_id, location in zip(location_ids, locations):
        log.info(format_location(*location, *location_lens, use_modified=True))
        value, = wizard(['   Note for this entry:'])
        if not value:
            value = None
        old = location[5]
        if old != value:
            ensa.db.update_location_metadata(location_id, note=value)
    return []


add_command(Command('lmnw <location_ids>',
                    'use wizard to modify location note', 'lmnw', lmnw_function))


def lmvw_function(*args):
    try:
        location_ids = [x for x in parse_sequence(args[0])]
        locations = [x for x in ensa.db.get_locations() if str(x[0])
                     in location_ids]
        location_ids = [str(x[0]) for x in locations]
        location_lens = get_format_len_location(locations)
    except:
        log.err('Location ID must be specified.')
        return []
    for location_id, location in zip(location_ids, locations):
        log.info(format_location(*location, *location_lens, use_modified=True))
        value, = wizard(['   Should this entry be valid?'])
        value = positive(value)
        old = positive(location[4])
        if value ^ old:
            ensa.db.update_location_metadata(location_id, valid=value)
    return []


add_command(Command('lmvw <location_ids>',
                    'use wizard to modify location validity', 'lmvw', lmvw_function))


"""
OPTIONS COMMANDS
"""
o_function = lambda *_: ['    %-30s  %s' % (k, (str(v[0] if v[1] != str else '\''+v[0]+'\'').replace(
    '\n', '\\n').replace('\r', '\\r')) if k not in ensa.censore_keys else '*********') for k, v in ensa.config.items()]
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
    try:
        ensa.config[key].value = value
    except:
        key = key if key.startswith('@') else '@%s' % key
        ensa.config[key] = ensa.Option(value, str)
    return []


add_command(Command('os <key> <value>',
                    'change Ensa configuration', 'os', os_function))

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
add_command(Command('q', 'quit', '', lambda *_: []))  # solved in ensa


"""
RING COMMANDS
"""


def r_function(*args):
    rings = ensa.db.get_rings(name=(args[0] if args else None))
    """use ring name as last if only result"""
    if len(rings) == 1:
        ensa.variables['last'] = rings[0][1]
    # TODO count subjects, show if encrypted, show notes, show if selected
    ring_lens = get_format_len_ring(rings)
    return [format_ring(*ring, *ring_lens) for ring in rings]


add_command(Command('r [<name>]', 'print rings', 'r', r_function))


def ra_function(*args):

    wizard_questions = [
        'Name of the ring (e.g. Work):',
        'Optional comment:',
        'Reference time (YYYY-mm-dd HH:MM:SS) or \'now\':',
        'Description of reference time entry:',
        '... Use provided information to create new ring?',
    ]
    """ name given in args?"""
    if args:
        name = args[0]
        wizard_questions = wizard_questions[1:]
        note, reference_time, rt_description, confirm = wizard(wizard_questions)
    else:
        name, note, reference_time, rt_description, confirm = wizard(wizard_questions)
    if negative(confirm):
        return []
    if not name:
        log.err('Unique name must be specified.')
        return []
    if not note:
        note = None

    if reference_time == 'now':
        reference_time = datetime_to_str(datetime.now())
    date, _, time = reference_time.partition(' ')

    result = ensa.db.create_ring(name, note)
    if not result:
        log.err('Error while inserting ring into DB.')
        return []
    ensa.variables['last'] = result
    
    ensa.current_ring, _ = ensa.db.select_ring(name)
    
    time_id = ensa.db.create_time(date, time, accuracy=10, 
                                  valid=True, note=rt_description)
    print('Created time id:', time_id)
    ensa.variables['reference_time_id'] = time_id
    ensa.variables['reference_time'] = datetime_from_str(ensa.db.get_time(time_id)[1])
    ensa.db.set_ring_reference_time_id(time_id)
    
    '''
    if ensa.current_reference_date == 'now':
        ensa.current_reference_date = time.strftime('%Y-%m-%d')
    else:
        ensa.current_reference_date = datetime.strptime(
            ensa.current_reference_date, '%Y-%m-%d')
    '''
    if ensa.current_ring:
        log.info('Currently working with \'%s\' ring.' % name)
        log.set_prompt()
    return []


add_command(Command('ra', 'add new ring', 'ra', ra_function))


def rd_function(*args):
    if not args:
        log.err('Ring name must be specified.')
    try:
        ring_id, _ = ensa.db.select_ring(args[0])
        if not ring_id:
            raise AttributeError
        if ensa.current_ring == ring_id:
            ensa.current_ring = None
            ensa.current_subject = None
            ensa.current_reference_date = None
            log.set_prompt()
        ensa.db.delete_ring(ring_id)
    except:
        log.debug_error()
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
        ensa.current_ring, ref_time_id = ensa.db.select_ring(
            name)

        ensa.variables['reference_time_id'] = ref_time_id
        ensa.variables['reference_time'] = datetime_from_str(
            ensa.db.get_time(ref_time_id)[1])
        '''
        if ensa.current_reference_date == 'now':
            ensa.current_reference_date = time.strftime('%Y-%m-%d')
        else:
            ensa.current_reference_date = datetime.strptime(
                ensa.current_reference_date, '%Y-%m-%d')
        '''
        if ensa.current_ring:
            ensa.variables['last'] = ensa.current_ring
            ensa.current_subject = None
            log.info('Currently working with \'%s\' ring.' % name)
            log.set_prompt()
    except:
        log.err('Ring name must be specified.')
        log.debug_error()
    return []


add_command(Command('rs <ring>', 'select a ring', 'rs', rs_function))

"""rms - ring modify - standardize"""


def rms_function(*_):
    ensa.db.standardize()
    return []


add_command(Command('rm', 'ring modification', 'rm', lambda *_: []))
add_command(Command('rms', 'standardize ring data', 'rms', rms_function))

'''
def rmr_function(*args):
    try:
        reference_date = args[0].lower()
    except:
        log.err('Reference id must be defined.')
        return []
    try:
        _ = datetime.strptime(reference_date, '%Y-%m-%d')
    except:
        traceback.print_exc()
        if reference_date != 'now':
            log.err('Reference date must be \'now\' or in YYYY-mm-dd format.')
            return []
    ensa.db.set_ring_reference_date(reference_date)
    ensa.current_reference_date = reference_date
    if ensa.current_reference_date == 'now':
        ensa.current_reference_date = datetime_to_str(only_date=True)
    else:
        ensa.current_reference_date = datetime.strptime(
            ensa.current_reference_date, '%Y-%m-%d')
    return []


add_command(Command('rmr <now|YYYY-mm-dd>',
                    'set reference date for current ring', 'rmr', rmr_function))
'''

"""
SUBJECT COMMANDS
"""


def s_function(*args):
    codename = args[0] if args else None
    subjects = ensa.db.get_subjects(codename=codename)
    """ save codename if only one match"""
    if len(subjects) == 1:
        ensa.variables['last'] = subjects[0][0]
    return ['%10s (#%d)  %20s  %s'  # TODO format_subject
            % (codename, subject_id, created, note if note else '')
            for subject_id, codename, created, note in subjects]


add_command(Command('s', 'list subjects in the current ring', 's', s_function))


def sa_function(*args):
    try:
        codename = args[0]
    except:
        log.err('You must specify codename.')
        return []
    subject_id = ensa.db.create_subject(codename)
    # ensa.variables['last'] = str(subject_id)
    ensa.variables['last'] = codename
    if ensa.current_subject:
        log.set_prompt()
        log.info('Currently working with \'%s\' subject.' % codename)
    return []


add_command(Command('sa <codename>',
                    'add new subject in the current ring', 'sa', sa_function))


def sawo_function(*_):
    i = {}
    (codename, logo_name, i['name'], i['identifier'], i['business'], i['website'], i['account']) = wizard([
        'Codename for the subject:',
        'Name of logo image (in files/uploads/):',
        'Organization name:',
        'Identifier:',
        'Business type:',
        'Website:',
        'Banking account number:',
    ])
    if not codename:
        log.err('Codename must be specified.')
        return []
    codename_id = ensa.db.create_subject(codename)
    info_codename_id = [i[0] for i in ensa.db.get_informations(
    ) if i[4] == 'codename' and i[11] == codename][0]
    ensa.db.add_keyword(info_codename_id, 'organization')

    if not codename_id:
        log.err('Subject could not be created.')
        return []

    if logo_name:
        try:
            ensa.db.add_binary(info_codename_id, logo_name)
        except:
            traceback.print_exc()

    if ensa.current_subject:
        log.set_prompt()
        log.info('Currently working with \'%s\' subject.' % codename)

    information_ids = []
    for name, value in i.items():
        if value:
            information_ids.append(ensa.db.create_information(
                Database.INFORMATION_TEXT, name, value))
    ensa.db.add_keyword(filter(None, information_ids), 'general')
    # addresses
    log.newline()
    while True:
        i = {}
        add_address, = wizard(['Add address entry?'])
        if not positive(add_address):
            break
        (location_name, i['country'], i['province'], i['city'], i['street'],
         i['street_number'], i['postal'], valid, lat, lon) = wizard([
             'Bureau name:',
             'Country:',
             'Province:',
             'City:',
             'Street:',
             'Street number:',
             'Postal code:',
             'Is the address currently valid?',
             'Latitude (e.g. -50.079795):',
             'Longitude (e.g. -14.429710):',
         ])
        valid = positive(valid)
        information_ids = filter(None,
                                 [ensa.db.create_information(Database.INFORMATION_TEXT,
                                                             name,
                                                             value,
                                                             valid=valid)
                                  for name, value in i.items() if value])
        if information_ids:
            address_id = ensa.db.create_information(
                Database.INFORMATION_COMPOSITE,
                'address',
                information_ids,
                valid=valid)
        try:
            lat = float(lat)
        except:
            lat = None
        try:
            lon = float(lon)
        except:
            lon = None
        location_id = ensa.db.create_location('%s\'s address (%s)'
                                              % (codename.title(), location_name),
                                              lat,
                                              lon,
                                              valid=valid)
        association_id = ensa.db.create_association(valid=valid,
                                                    note='%s\'s address'
                                                    % codename.title())
        ensa.db.associate_information(association_id, address_id)
        ensa.db.associate_location(association_id, location_id)
    
    """ employees """
    while True:
        employee, = wizard([
            'Employee codename:',
        ])
        if not employee:
            break
        employee_id = ensa.db.select_subject(employee)
        if not employee_id:
            log.err('No such subject exists.')
            continue

        position, start, end = wizard([
            'Position:',
            'Start date (YYYY-mm-dd):',
            'End date (YYYY-mm-dd):',
        ])
        employment_id = ensa.db.create_association(
            note=('%s-%s employee' % (codename, employee)), level=10, accuracy=10)
        ensa.db.associate_subject(employment_id, codename)
        ensa.current_subject = employee_id
        job_id = ensa.db.create_information(
            Database.INFORMATION_TEXT, 'position', position, level=10, accuracy=10)
        ensa.db.associate_information(employment_id, job_id)

        if start:
            start_time = ensa.db.create_time(
                start, '00:00:00', note='%s\'s start date as employee of %s' % (employee, codename))
            if start_time:
                ensa.db.associate_time(employment_id, start_time)
            else:
                log.err('Start date is wrong.')
        if end:
            # TODO compare with reference date
            #valid = (datetime.strptime(end, '%Y-%m-%d') >= datetime.now())
            end_time = ensa.db.create_time(
                end, '00:00:00', note='%s\'s end date as employee of %s' % (employee, codename))
            if end_time:
                ensa.db.associate_time(employment_id, end_time)
            else:
                log.err('End date is wrong.')
        '''
        else:
            valid, = wizard(['Is the employment still valid?'])
            valid = not negative(valid)
        ensa.db.update_association_metadata(employment_id, valid=valid)
        '''

    # business partners (organizations)
    # TODO

    ensa.variables['last'] = codename
    ensa.current_subject = codename_id


def sawp_function(*_):
    # general info
    i = {}
    (codename, portrait_name, i['firstname'], i['middlename'], i['lastname'],
     i['sex'], i['birth_year'], i['birth_month'], i['birth_day'], i['race'],
     i['religion'], i['politics'], i['orientation']) = wizard([
         'Codename for the subject:',
         'Name of portrait photo (in files/uploads/):',
         'First name:',
         'Middle name:',
         'Last name:',
         'Sex:',
         'Year of birth:',
         'Month of birth:',
         'Day of birth:',
         'Race:',
         'Religion:',
         'Politics:',
         'Orientation:',
     ])

    if not codename:
        log.err('Codename must be specified.')
        return []
    subject_id = ensa.db.create_subject(codename)
    if not subject_id:
        log.err('Subject could not be created.')
        return []

    if ensa.current_subject:
        log.set_prompt()
        log.info('Currently working with \'%s\' subject.' % codename)

    info_codename_id = [i[0] for i in ensa.db.get_informations(
    ) if i[4] == 'codename' and i[11] == codename][0]
    ensa.db.add_keyword(info_codename_id, 'person')
    if portrait_name:
        try:
            ensa.db.add_binary(info_codename_id, portrait_name)
        except:
            traceback.print_exc()

    if i['sex'].lower() in ('m', 'male', 'boy', 'man'):
        i['sex'] = 'male'
    if i['sex'].lower() in ('f', 'female', 'girl', 'woman'):
        i['sex'] = 'female'
    if not i['sex'] in ('', 'male', 'female'):
        log.err('Sex must be either male or female.')

    information_ids = []
    for name, value in i.items():
        if value:
            information_ids.append(ensa.db.create_information(
                Database.INFORMATION_TEXT, name, value))
    ensa.db.add_keyword(filter(None, information_ids), 'general')

    # address
    log.newline()
    while True:
        i = {}
        add_address, = wizard(['Add address entry?'])
        if not positive(add_address):
            break
        (i['country'], i['province'], i['city'], i['street'],
         i['street_number'], i['postal'], valid, lat, lon) = wizard([
             'Country:',
             'Province:',
             'City:',
             'Street:',
             'Street number:',
             'Postal code:',
             'Is the address currently valid?',
             'Latitude (e.g. -50.079795):',
             'Longitude (e.g. -14.429710):',
         ])
        valid = positive(valid)
        information_ids = filter(None,
                                 [ensa.db.create_information(Database.INFORMATION_TEXT,
                                                             name,
                                                             value,
                                                             valid=valid)
                                  for name, value in i.items() if value])
        if information_ids:
            address_id = ensa.db.create_information(
                Database.INFORMATION_COMPOSITE,
                'address',
                # ','.join(str(x) for x in information_ids),
                information_ids,
                valid=valid)
        try:
            lat = float(lat)
        except:
            lat = None
        try:
            lon = float(lon)
        except:
            lon = None
        location_id = ensa.db.create_location('%s\'s home'
                                              % codename.title(),
                                              lat,
                                              lon,
                                              valid=valid)
        association_id = ensa.db.create_association(valid=valid,
                                                    note='%s\'s home'
                                                    % codename.title())
        ensa.db.associate_information(association_id, address_id)
        ensa.db.associate_location(association_id, location_id)

    # likes, dislikes, skills, traits
    for category, question in (
            ('nickname', 'Nickname for %s:' % codename),
            ('identifier', 'Unique %s\'s identifier:' % codename),
            ('likes', '%s likes:' % codename.title()),
            ('dislikes', '%s dislikes:' % codename.title()),
            ('skill', '%s\'s skill:' % codename.title()),
            ('trait', '%s\'s trait:' % codename.title()),
            ('asset', '%s\'s asset:' % codename.title()),
            ('medical', '%s\'s medical condition:' % codename.title()),
            ('quotation', '%s\'s quotation:' % codename.title()),
    ):
        log.newline()
        while True:
            value, = wizard([
                question,
            ])
            if value:
                ensa.db.create_information(
                    Database.INFORMATION_TEXT, category, value)
            else:
                break
    """job"""
    while True:
        organization, = wizard(['Organization codename:'])
        if not organization:
            break
        organization_id = ensa.db.select_subject(organization)
        if not organization_id:
            log.err('No such subject exists.')
            continue
        position, start, end = wizard(
            [
                'What is %s\'s position?' % (codename),
                'Start date (YYYY-mm-dd):',
                'End date (YYYY-mm-dd):',
            ])
        employment_id = ensa.db.create_association(
            note=('%s-%s employee' % (organization, codename)), level=10, accuracy=10)
        job_id = ensa.db.create_information(
            Database.INFORMATION_TEXT, 'position', position, level=10, accuracy=10)
        ensa.db.associate_subject(employment_id, organization)
        ensa.db.associate_information(employment_id, job_id)

        if start:
            start_time = ensa.db.create_time(
                start, '00:00:00', note='%s\'s start date as employee of %s' % (codename, organization))
            if start_time:
                ensa.db.associate_time(employment_id, start_time)
            else:
                log.err('Start date is wrong.')
        if end:
            end_time = ensa.db.create_time(
                end, '00:00:00', note='%s\'s end date as employee of %s' % (codename, organization))
            if end_time:
                ensa.db.associate_time(employment_id, end_time)
            else:
                log.err('End date is wrong.')

    """relationships"""
    log.newline()
    while True:
        acq, = wizard(['Who does the subject has a relationship with?'])
        if not acq:
            break
        acq_id = ensa.db.select_subject(acq)
        if not acq_id:
            log.err('No such subject exists.')
            continue
        valid, relationship, level, accuracy,  = wizard(
            [
                'Is the relationship still valid?',
                'Who is %s to %s?' % (codename, acq),
                'What is the relationship level?',
                'How accurate is the relationship definition?',
            ])
        # TODO universal (sister -> sibling)
        valid = not negative(valid)
        association_id = ensa.db.create_association(level=level,
                                                    accuracy=accuracy,
                                                    valid=valid,
                                                    note=('%s-%s %s'
                                                          % (codename,
                                                             acq,
                                                             relationship)))
        ensa.db.associate_subject(association_id, [codename, acq])
    ensa.variables['last'] = codename
    ensa.db.standardize()
    return []


add_command(Command('saw', 'subject wizards', 'saw', lambda *_: []))
add_command(
    Command('sawo', 'use wizard to create an Organization subject', 'sawo', sawo_function))
add_command(
    Command('sawp', 'use wizard to create a Person subject', 'sawp', sawp_function))


"""subject - add credentials"""


def sac_function(*args):
    try:
        username = args[0]
        password = args[1]
    except:
        log.err('Parameters are wrong.')
        return []
    try:
        system = args[2]
    except:
        system = None
    username_id = ensa.db.create_information(
        Database.INFORMATION_TEXT, 'username', username)
    password_id = ensa.db.create_information(
        Database.INFORMATION_TEXT, 'password', password)
    if system:
        system_id = ensa.db.create_information(
            Database.INFORMATION_COMPOSITE, system, [username_id, password_id])
        ensa.db.add_keyword(system_id, 'credentials')
        ensa.variables['last'] = system_id

    return []


add_command(Command('sac <username> <password> [<system>]',
                    'add credentials to current subject', 'sac', sac_function))

"""subject - add relationship"""


def sar_function(*args):
    try:
        acquaintance = args[0]
        relationship = args[1]
    except:
        log.err('Invalid parameters.')
        return []
    try:
        accuracy = int(args[2])
    except:
        accuracy = ensa.config['interaction.default_accuracy'].value
    try:
        level = int(args[3])
    except:
        level = 10
    # TODO universal (sister -> sibling)
    codename = ensa.db.get_subject_codename(ensa.current_subject)
    as_note = '%s-%s %s' % (acquaintance, codename, relationship)
    association_id = ensa.db.create_association(
        accuracy=accuracy,
        level=level,
        valid=True,
        note=as_note)
    ensa.db.associate_subject(association_id, [codename,
                                               acquaintance])
    ensa.variables['last'] = association_id
    return []


add_command(Command('sar <codename> <relationship> [<accuracy> [<level>]]',
                    'add relationship to a subject', 'sar', sar_function))

# TODO add address
# TODO add job
# TODO add organization membership


def sd_function(*args):
    if not args:
        log.err('Subject name must be specified.')
    try:
        subject_id = ensa.db.select_subject(args[0])
        if not subject_id:
            raise AttributeError
        if ensa.current_subject == subject_id:
            ensa.current_subject = None
            log.set_prompt()
        ensa.db.delete_subject(subject_id)
    except:
        log.debug_error()
        log.err('No ring with that name exists.')
        return []
    return []


add_command(Command('sd <codename>',
                    'delete subject from the current ring', 'sd', sd_function))


def sr_function(*_):
    ensa.db.standardize()
    if not ensa.current_subject:
        log.err('A subject must be selected.')
        return []
    codename = ensa.db.get_subject_codename(ensa.current_subject)

    """determine report type"""
    # pdb.set_trace()
    info_codename_id = [
        i for i in ensa.db.get_informations() if i[4] == 'codename'][0][0]
    keywords = [x[1]
                for x in ensa.db.get_keywords_for_informations(info_codename_id)]
    supported = {
        'person': person_report,
    }

    report_created = False
    for report_type, function in supported.items():
        if report_type in keywords:
            log.info('Generating %s report for %s...' %
                     (report_type.title(), codename))
            filename = 'files/tmp/%s_%s.pdf' % (
                ensa.db.get_ring_name(ensa.current_ring), codename)
            function(codename, filename)
            report_created = True
            log.info('Report is saved as %s.' % filename)
        break
    if not report_created:
        log.err('Only %s reports are supported.' % '|'.join(supported.keys()))
    return []


add_command(Command('sr <codename>',
                    'generate report of current subject', 'sr', sr_function))


def ss_function(*args):
    if not args:
        ensa.current_subject = None
        log.info('Currently working outside subject.')
        log.set_prompt()
        return []
    try:
        codename = args[0]
        ensa.current_subject = ensa.db.select_subject(codename)
        if ensa.current_subject:
            log.info('Currently working with \'%s\' subject.' % codename)
            log.set_prompt()
            ensa.variables['last'] = codename
    except:
        log.err('Subject codename must be specified.')
        log.debug_error()
    return []


add_command(Command('ss <codename>', 'select a subject', 'ss', ss_function))


"""
TIME COMMANDS
"""


def t_function(*_):
    times = ensa.db.get_times()
    if len(times) == 1:
        ensa.variables['last'] = times[0][0]
    if not times:
        return []
    time_lens = get_format_len_time(times)
    return [format_time(*time, *time_lens, use_modified=True)
            for time in times]


add_command(Command('t', 'list time entries for current ring', 't', t_function))


def taw_function(*_):
    if not ensa.current_ring:
        log.err('First select a ring with `rs <name>`.')
        return []
    date, time, accuracy, valid, note, as_reference, confirm = wizard([
        'Date (YYYY-mm-dd):',
        'Time (HH:MM:SS):',
        'Accuracy of this entry (default 0):',
        'Is the entry valid?',
        'Optional comment:',
        'Use this time as reference?',
        '... Use provided information to create new time?',
    ])
    if negative(confirm):
        return []
    accuracy = int(accuracy) if accuracy.isdigit() else 0
    valid = not negative(valid)
    time_id = ensa.db.create_time(date, time, accuracy, valid, note)
    if positive(as_reference):
        ensa.variables['reference_time_id'] = time_id
        ensa.variables['reference_time'] = ensa.db.get_time(time_id)[1]
    ensa.variables['last'] = time_id
    if time_id:
        log.info('Created new time entry with id #%d' % time_id)
    return []


add_command(Command('ta',
                    'add time entry to current ring',
                    'ta',
                    lambda *_: []))  # TODO?
add_command(Command('taw',
                    'use wizard to add new time entry to current ring',
                    't',
                    taw_function))


def td_function(*args):
    try:
        time_ids = ','.join(parse_sequence(','.join(args)))
        ensa.db.delete_times(time_ids)
    except:
        log.debug_error()
        log.err('Correct time ID from this ring must be provided.')
    return []


add_command(Command('td <time_id>',
                    'delete time entry from current ring',
                    'td',
                    td_function))


add_command(Command('tl', 'timelines', 'tl', lambda *_: []))


def tli_function(*args):
    return ag_function(*args, data_function=lambda ids: ensa.db.get_timeline_by_information(ids), prepend_times=True, hide_details=True, use_modified=False)


add_command(Command('tli <information_ids>',
                    'show timelines for given informations', 'tli', tli_function))


def tliv_function(*args):
    return ag_function(*args, data_function=lambda ids: ensa.db.get_timeline_by_information(ids), prepend_times=True, use_modified=False)


add_command(Command('tliv <information_ids>',
                    'show timelines for given informations (verbose)', 'tli', tliv_function))


def tll_function(*args):
    return ag_function(*args, data_function=lambda ids: ensa.db.get_timeline_by_location(ids), prepend_times=True, hide_details=True, use_modified=False)


add_command(Command('tll <location_ids>',
                    'show timelines for given locations', 'tll', tll_function))


def tllv_function(*args):
    return ag_function(*args, data_function=lambda ids: ensa.db.get_timeline_by_location(ids), prepend_times=True, use_modified=False)


add_command(Command('tllv <location_ids>',
                    'show timelines for given locations (verbose)', 'tll', tllv_function))


def tls_function(*args):
    return ag_function(*args, data_function=lambda codenames: ensa.db.get_timeline_by_subject(codenames), id_type=1, prepend_times=True, hide_details=True, use_modified=False)


add_command(Command('tls <codename>',
                    'show timelines for given subjects', 'tls', tls_function))


def tlsv_function(*args):
    return ag_function(*args, data_function=lambda codenames: ensa.db.get_timeline_by_subject(codenames), id_type=1, prepend_times=True, use_modified=False)


add_command(Command('tlsv <codename>',
                    'show timelines for given subjects (verbose)', 'tls', tlsv_function))


def tlt_function(*args, hide_details=False, use_modified=True):
    # supported: t-t, d-, d-d, dt-, dt-t, dt-d, dt-dt
    if len(args) in (3, 4):
        """ first is always dt """
        start_args = args[:2]
        end_args = args[2:]
    elif len(args) == 2:
        """ t-t, d-d or dt-; try parse start, decide by returned type """
        test_start_type, test_start = datetime_from_str(
            ' '.join(args), 
            also_return_type=True)
        if test_start_type == 'dt':
            start_args = args
            end_args = (datetime_to_str(),)
        else:
            start_args = args[:1]
            end_args = args[1:]
    elif len(args) == 1:
        """ always start; use 'now' as end """
        start_args = args
        end_args = (datetime_to_str(),)
    
    print('start args', start_args)
    print('end args', end_args)

    start_type, start = datetime_from_str(' '.join(start_args), also_return_type=True)
    end_type, end = datetime_from_str(' '.join(end_args), also_return_type=True)
    
    print(start_type, start)
    print(end_type, end)
    '''
    if (start_type, end_type) not in [
        ('t', 't'),
        ('d', None),
        ('d', 'd'),
        ('dt', None),
        ('dt', 't'),
        ('dt', 'd'),
        ('dt', 'dt'),
    ]:
        log.err('%s-%s date range format is not supported.' % (start_type, end_type))
        return []
    ''' 
    # print(start)
    # print(end)
    return ag_function(start,
                       end,
                       data_function=lambda dates:
                       ensa.db.get_timeline_by_range(*dates), id_type=3,
                       prepend_times=True,
                       hide_details=hide_details,
                       use_modified=use_modified)


add_command(Command('tlt <start> [<end>]', 'show timelines for given date range',
                    'tlt', lambda *args: tlt_function(*args, hide_details=True, use_modified=False)))
add_command(Command('tltv <start> [<end>]', 'show timelines for given date range (verbose)',
                    'tltv', lambda *args: tlt_function(*args, use_modified=False)))


add_command(Command('tm', 'modify time', 'tm', lambda *args: []))


def tme_function(*args):
    try:
        time_id = args[0]
    except:
        log.err('Time ID must be specified.')
        return []
    # get values
    data = ensa.db.get_time(time_id)
    if not data:
        return []
    '''
    d, _, t = data[1].partition(' ')
    data = data[:1]+(d, t)+data[2:]
    '''
    # add labels
    '''
    mapped = dict(zip([None, 'date', 'time', 'accuracy', 'valid', 'note'], [
                  (x if type(x) == bytearray else x) if x else '' for x in data]))
    '''
    mapped = dict(zip([None, 'datetime', 'accuracy', 'valid', 'note'], [
                  (x if type(x) == bytearray else x) if x else '' for x in data]))
    # print(mapped)
    # write into file
    with tempfile.NamedTemporaryFile() as f:
        for k in sorted(filter(None, mapped.keys())):
            f.write(('%s: %s\n' % (k, mapped[k])).encode())
        f.flush()
        subprocess.call((ensa.config['external.editor'].value % (f.name)).split())
        f.seek(0)
        # retrieve changes
        changes = f.read().decode()
    change_occured = False
    # ingore unknown keys
    for line in changes.splitlines():
        # import pdb
        # pdb.set_trace()
        k, _, v = line.partition(': ')
        # ingore unknown keys
        if k not in mapped.keys():
            continue
        try:
            v = type(mapped[k])(v.strip())
        except:
            if type(mapped[k]) == int and not v.strip():
                v = 0
            else:
                raise
        if mapped[k] != v:
            # print('value of', k, '-', v, type(v), 'does not match the original', mapped[k], type(mapped[k]))
            change_occured = True
            # check validity and save valid changes
            if k == 'accuracy':
                if type(v) == int or v.isdigit():
                    mapped[k] = int(v)
                else:
                    mapped[k] = 0
                    # log.err('Accuracy must be a number.')
                    # change_occured = False
                    # break
            elif k == 'valid':
                mapped[k] = positive(v)
            elif k == 'name':
                if v:
                    mapped[k] = v
                else:
                    log.err('%s must be defined.' % (k.title()))
                    change_occured = False
                    break
            elif k == 'datetime':
                date_time = datetime_from_str(v)
                if not date_time:
                    log.err('Datetime is invalid.')
                    change_occured = False
                    break
                mapped[k] = datetime_to_str(date_time)
                '''
            elif k == 'date': # TODO edit
                if not v:
                    mapped[k] = '0000-00-00'
                else:
                    try:
                        _ = datetime.strptime(v, '%Y-%m-%d')
                        mapped[k] = v
                    except:
                        log.err('Date must be of YYYY-mm-dd format.')
                        log.debug_error()
                        change_occured = False
                        break
            elif k == 'time': # TODO edit
                if not v:
                    mapped[k] = '00:00:00'
                else:
                    try:
                        _ = datetime.strptime(v, '%H:%M:%S')
                        mapped[k] = v
                    except:
                        try:
                            _ = datetime.strptime(v, '%H:%M')
                            mapped[k] = v
                        except:
                            log.err('Time must be of HH:MM or HH:MM:SS format.')
                            log.debug_error()
                            change_occured = False
                            break
                '''
            elif k == 'note':
                mapped[k] = v if v else None
    if change_occured:
        # update DB
        del mapped[None]
        mapped['time_id'] = time_id
        #mapped['datetime'] = '%s %s' % (mapped['date'], mapped['time'])
        #del mapped['date']
        #del mapped['time']
        # print(mapped)
        ensa.db.update_time(**mapped)
        log.info('Time entry %s successfully changed.' % time_id)
        if int(time_id) == ensa.variables['reference_time_id']:
            ensa.variables['reference_time'] = mapped['datetime']
        
        log.set_prompt()
    else:
        log.info('No change has been done.')
    return []


add_command(Command('tme <time_id>',
                    'modify time entry with editor', 'tme', tme_function))


def tma_function(*args):
    try:
        time_ids = ','.join(parse_sequence(args[0]))
    except:
        log.err('Time ID must be specified.')
        return []
    try:
        value = int(args[1])
    except:
        log.err('Value must be a number.')
        return []
    ensa.db.update_time_metadata(time_ids, accuracy=value)
    log.info('Accuracy updated.')
    return []


add_command(Command('tma <location_ids> <value>',
                    'modify time accuracy', 'tma', tma_function))


def tmn_function(*args):
    try:
        time_ids = ','.join(parse_sequence(args[0]))
    except:
        log.err('Time ID must be specified.')
        return []
    try:
        value = ' '.join(args[1:])
    except:
        log.err('Value must be defined.')
        return []
    ensa.db.update_time_metadata(time_ids, note=value)
    log.info('Note updated.')
    return []


add_command(Command('tmn <time_ids> <value>',
                    'modify time note', 'tmn', tmn_function))


def tmv_function(*args):
    try:
        time_ids = ','.join(parse_sequence(args[0]))
    except:
        log.err('Time ID must be specified.')
        return []
    try:
        value = '1' if positive(args[1]) else '0'
    except:
        log.err('Value must be defined.')
        return []
    ensa.db.update_time_metadata(time_ids, valid=value)
    log.info('Validity updated.')
    return []


add_command(Command('tmv <time_ids> <value>',
                    'modify time validity', 'tmv', tmv_function))


def tmaw_function(*args):
    try:
        time_ids = [x for x in parse_sequence(args[0])]
        times = [x for x in ensa.db.get_times() if str(x[0]) in time_ids]
        time_ids = [str(x[0]) for x in times]
        time_lens = get_format_len_time(times)
    except:
        log.err('Time ID must be specified.')
        return []
    for time_id, time in zip(time_ids, times):
        log.info(format_time(*time, *time_lens, use_modified=True))
        while True:
            value, = wizard(['   Accuracy for this entry:'])
            try:
                value = int(value)
                break
            except:
                log.err('Accuracy must be a number.')
        old = time[2]
        if old != value:
            ensa.db.update_time_metadata(time_id, accuracy=value)
    return []


add_command(Command('tmaw <time_ids>',
                    'use wizard to modify time accuracy', 'tmaw', tmaw_function))


def tmnw_function(*args):
    try:
        time_ids = [x for x in parse_sequence(args[0])]
        times = [x for x in ensa.db.get_times() if str(x[0]) in time_ids]
        time_ids = [str(x[0]) for x in times]
        time_lens = get_format_len_time(times)
    except:
        log.err('Time ID must be specified.')
        return []
    for time_id, time in zip(time_ids, times):
        log.info(format_time(*time, *time_lens, use_modified=True))
        value, = wizard(['   Note for this entry:'])
        if not value:
            value = None
        old = time[4]
        if old != value:
            ensa.db.update_time_metadata(time_id, note=value)
    return []


add_command(Command('tmnw <time_ids>',
                    'use wizard to modify time note', 'tmnw', tmnw_function))


def tmvw_function(*args):
    try:
        time_ids = [x for x in parse_sequence(args[0])]
        times = [x for x in ensa.db.get_times() if str(x[0]) in time_ids]
        time_ids = [str(x[0]) for x in times]
        time_lens = get_format_len_time(times)
    except:
        log.err('Time ID must be specified.')
        return []
    for time_id, time in zip(time_ids, times):
        log.info(format_time(*time, *time_lens, use_modified=True))
        value, = wizard(['   Should this entry be valid?'])
        value = positive(value)
        old = positive(time[3])
        if value ^ old:
            ensa.db.update_time_metadata(time_id, valid=value)
    return []


add_command(Command('tmvw <time_ids>',
                    'use wizard to modify time validity', 'tmvw', tmvw_function))


def v_function():
    try:
        max_key_len = max(len(k) for k, v in ensa.variables.items())
    except:
        return []
    for key, value in ensa.variables.items():
        print('    %*s: %s' % (max_key_len, key, value))


add_command(Command('v',
                    'show variables',
                    'v',
                    v_function))

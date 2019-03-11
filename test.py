#!/usr/bin/python3
"""
This file contains unit tests.
Ensa is run as external command, state is assessed with lambda.
"""
import subprocess
import re
import sys

class Test:
    @staticmethod
    def run_command(command, payload=''):
        p = subprocess.Popen(command,
                             shell=True,
                             stdin=subprocess.PIPE if payload else None,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        (out, err) = p.communicate(input=payload.encode())
        return (p.returncode, out, err)
    
    def __init__(self, name, commands, error_message, validator, arguments):
        self.name = name 
        self.payload = '\n'.join(commands)
        self.error_message = ('(%s)' % error_message) if error_message else ''
        self.validator = validator
        self.arguments = arguments
        
    def run(self):
        print('\033[34m%50s\033[0m: ' % self.name, end='')
        sys.stdout.flush()
        r, o, e = Test.run_command('./ensa', self.payload)
        o = o.decode()
        e = e.decode()
        #print(o.splitlines())
        #for line in o.splitlines():
        #    print(line)
        if self.validator(r, o, e, self.arguments):
            print('\033[32;1mOK\033[0m')
        else:
            print('\033[31;1mFAIL\033[0m %s' % self.error_message)
            print('    Command: echo -e \'%s\' | ./ensa' 
                  % self.payload.replace('\n', '\\n'))
            for line in e.splitlines():
                print('   ', line)

""" ring manipulation """ 
ring_tests = [
    Test('create ring',
         ['ra', 'TEST', 'test comment', 'y', 'r $last'],
         '',
         lambda r,o,e,args: 
         len([l for l in o.splitlines() if re.search(r'^ *TEST', l)]) == 1,
         {}),
    Test('select ring',
         ['rs TEST'],
         '',
         lambda r,o,e,args: o.splitlines()[-2].startswith('\x1b[95m\x1b[01mTEST) '),
         {}),
    Test('change ring date',
         ['rs TEST', 'rr 1971-01-01', 'r TEST'],
         '',
         lambda r,o,e,args: 
         [re.search(r'^ *TEST *\(ref: 1971-01-01\)', l) for l in o.splitlines()],
         {}),
]

""" subject manipulation """ 
subject_tests = [
    Test('create subject',
         ['rs TEST', 'sa trump', 's $last'],
         '',
         lambda r,o,e,args: 
         len([l for l in o.splitlines() if re.search(r'^ *trump \(#', l)]) == 1,
         {}),
    Test('create subject with wizard',
         ['rs TEST', 'sawp', 'babis', 'Andrej', '', 'Babis', 'male', 
          '1968', '', '', 'caucasian', 'atheist', 'ANO', 'heterosexual',
          'y', 'Czech Republic', '', 'Prague', '', '', '', 'y', 'n',
          'Bures', '', 'money', 'power', '', 'Pirates of the Carribean', '', 
          'denial', '', 'rich', '', 'Stork\'s nest', ''],
         '',
         lambda r,o,e,args: 
         lambda r,o,e,args: o.splitlines()[-2].startswith('\x1b[95m\x1b[01mTEST/babis] '),
         {}),
    Test('select subject',
         ['rs TEST', 'ss trump'],
         '',
         lambda r,o,e,args: 
         lambda r,o,e,args: o.splitlines()[-2].startswith('\x1b[95m\x1b[01mTEST/trump] '),
         {}),

]

""" information and keyword manipulation """
info_tests = [
    Test('add textual information with keyword, get it',
         ['rs TEST', 'ss trump', 'iat firstname Donald', 
          'iak $last KEYWORD', 'git $last'],
         '',
         lambda r,o,e,args: 
         lambda r,o,e,args:
         len([l for l in o.splitlines() 
              if re.search(r'^[0-9]+ +<trump> +firstname: Donald ', l)]) == 1,
         {}),
    Test('get textual information by keyword',
         ['rs TEST', 'ss trump', 'igbk KEYWORD', 'igt $last'],
         '',
         lambda r,o,e,args: 
         lambda r,o,e,args:
         len([l for l in o.splitlines() 
              if re.search(r'^[0-9]+ +<trump> +firstname: Donald ', l)]) == 1,
         {}),
    Test('remove keyword',
         ['rs TEST', 'ss trump', 'igbk KEYWORD', 'idk $last', 'igbk KEYWORD'],
         '',
         lambda r,o,e,args: 
         lambda r,o,e,args:
         len([l for l in o.splitlines() 
              if re.search(r'^[0-9]+ +<trump> +firstname: Donald ', l)]) == 0,
         {}),
    Test('modify information accuracy',
         ['rs TEST', 'ss trump', 'igt', 'ima $last 7', 'igt'],
         '',
         lambda r,o,e,args: 
         lambda r,o,e,args:
         len([l for l in o.splitlines() 
              if re.search(r'acc +7, ', l)]) == 1,
         {}),
    Test('modify information level',
         ['rs TEST', 'ss trump', 'igt', 'iml $last 6', 'igt'],
         '',
         lambda r,o,e,args: 
         lambda r,o,e,args:
         len([l for l in o.splitlines() 
              if re.search(r'(lvl +6, ', l)]) == 1,
         {}),
    Test('modify information note',
         ['rs TEST', 'ss trump', 'igt', 'imn $last LOL', 'igt'],
         '',
         lambda r,o,e,args: 
         lambda r,o,e,args:
         len([l for l in o.splitlines() 
              if re.search(r'# LOL', l)]) == 1,
         {}),
    Test('modify information validity',
         ['rs TEST', 'ss trump', 'igt', 'imv $last 0', 'igt'],
         '',
         lambda r,o,e,args: 
         lambda r,o,e,args:
         len([l for l in o.splitlines() 
              if re.search(r'invalid)', l)]) == 1,
         {}),
    Test('remove textual information',
         ['rs TEST', 'ss trump', 'idt firstname', 'igt'],
         '',
         lambda r,o,e,args: 
         lambda r,o,e,args:
         len([l for l in o.splitlines() 
              if re.search(r'^[0-9]+ +<trump> +firstname: ', l)]) == 0,
         {}),

]

""" test cleanup (delete ring, validate on delete cascade etc.) """ 
cleanup = [
    Test('delete subject',
         ['rs TEST', 'sd babis', 's'],
         '',
         lambda r,o,e,args: 
         len([l for l in o.splitlines() if re.search(r'^ *babis \(', l)]) == 0,
         {}),
    Test('delete ring',
         ['rd TEST'],
         '',
         lambda r,o,e,args: 
         len([l for l in o.splitlines() if re.search(r'^ *TEST', l)]) == 0,
         {}),
    
]

enabled_tests = [
    ring_tests,
    subject_tests,
    info_tests,
    cleanup,
]

for tests in enabled_tests:
    for test in tests:
        test.run()
    print()

#########

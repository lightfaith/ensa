#!/usr/bin/env python3
import time
from datetime import datetime
import os
import pdb
import sqlite3 as sqlite
from threading import Lock
#from pysqlcipher3 import dbapi2 as sqlite
from source import log
from source import ensa
from source import lib


class Database():
    INFORMATION_ALL = -1
    INFORMATION_TEXT = 0
    INFORMATION_BINARY = 1
    INFORMATION_COMPOSITE = 2

    def __init__(self):
        self.cnx = None
        self.cur = None
        self.lock = Lock()

    def connect(self, password):
        #lib.reload_config()
        """
        try to connect to the database
        """
        db_exists = True
        try:
            with open(ensa.config['db.file'].value, 'r') as f:
                pass
        except:
            db_exists = False

        try:
            self.cnx = sqlite.connect(ensa.config['db.file'].value, check_same_thread=False)
            self.cur = self.cnx.cursor()
            self.query("PRAGMA key='%s'" % password)
            self.query("PRAGMA foreign_keys=ON")
            if not db_exists:
                log.info('Cannot locate database file, creating new one...')
                with open('files/schema.sql', 'r') as f:
                    for q in f.read().split(';'):
                        self.query(q)
            return True
        except Exception as e:
            traceback.print_exc()
            #print(str(e))
            return False

    def query(self, command, parameters=None):
        with self.lock:
            log.debug_query(command)
            try:
                #self.cur.execute(command, parameters or tuple())
                self.cur.execute(command, parameters or tuple())
                self.cnx.commit()
            except Exception as e:  # mysql.connector.errors.OperationalError:
                print(str(e))
            #    self.connect()
            #    self.cur.execute(command, parameters or tuple())

            if command.upper().startswith('SELECT '):
                #return self.cur.fetchall()
                return list(self.cur.fetchall())
            return []

    def ring_ok(self, ring):
        if not ring:
            log.err('First select a ring with `rs <name>`.')
            return False
        return True

    def subject_ok(self, subject):
        if not subject:
            log.err('First select a subject with `ss <codename>`.')
            return False
        return True
###########################################
# Ring methods
###########################################

    def get_rings(self, name=None):
        if name:
            result = self.query(("SELECT ring_id, name, "
                                 "       reference_time_id, note "
                                 "FROM Ring "
                                 "WHERE name LIKE '%"+name+"%'"))
        else:
            result = self.query("SELECT ring_id, name, "
                                "       reference_time_id, note "
                                "FROM Ring")
        return result

    def create_ring(self, name, note):
        try:
            self.query(("INSERT INTO Ring(name, note) "
                        "VALUES(:n, :note)"),
                       {'n': name,
                        'note': note})
            return name
        except:
            log.debug_error()
            return ''

    def select_ring(self, name):
        result = self.query(("SELECT ring_id, reference_time_id "
                             "FROM Ring "
                             "WHERE name = :n"),
                            {'n': name})
        if result:
            return result[0]
        log.err('There is no such ring.')
        return None

    def get_ring_name(self, ring_id):
        result = self.query(("SELECT name "
                             "FROM Ring "
                             "WHERE ring_id = :r"),
                            {'r': ring_id})
        if result:
            return result[0][0]
        log.err('There is no such ring.')
        return None

    def delete_ring(self, ring_id):
        self.query(("DELETE FROM Ring "
                    "WHERE ring_id = :r"),
                   {'r': ring_id})

    def set_ring_reference_time_id(self, reference_time_id, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return
        self.query(("UPDATE Ring "
                    "SET reference_time_id = :rtid "
                    "WHERE ring_id = :r"),
                   {'rtid': reference_time_id,
                    'r': ensa.current_ring})

    def standardize(self, ring=None):
        ring = ring or ensa.current_ring
        if not ring:
            log.err('Choose a ring first.')
            return
        """
        This function is designed to ensure data are standardized,
        e.g. address has Location entry, birth date is Time entry (if possible)
        etc.
        """
        """ address without location """
        # sawp and sawo should control that, otherwise we cannot guess
        # the name properly...
        """ convert birth_* and others to Time entry """
        informations = self.get_informations(ring=ring)
        events = ['birth', 'death']  # TODO more

        for subject_id in set([i[1] for i in informations]):
            codename = self.get_subject_codename(subject_id, ring=ring)
            for event in events:
                # find id and value of y, m, d for an event
                try:
                    y = [i for i in informations if i[1] ==
                         subject_id and i[4] == '%s_year' % event][0]
                except:
                    y = None
                try:
                    m = [i for i in informations if i[1] == subject_id and i[4]
                         == '%s_month' % event][0]
                except:
                    m = None
                try:
                    d = [i for i in informations if i[1] ==
                         subject_id and i[4] == '%s_day' % event][0]
                except:
                    d = None

                as_note = '%s\'s %s' % (codename.title(), event)
                """create if possible"""
                if y and m and d and not [x for x in self.get_associations(ring=ring)
                                          if x[6] == as_note]:
                    accuracy = min(x[6] for x in (y, m, d))
                    valid = all(x[7] for x in (y, m, d))
                    time_id = self.create_time(
                        '%04d-%02d-%02d' % (int(y[11]),
                                            int(m[11]), int(d[11])),
                        '00:00', accuracy=accuracy, valid=valid, 
                        note=as_note, ring=ring)
                    as_id = self.create_association(
                        accuracy=accuracy, valid=valid, note=as_note, ring=ring)
                    self.associate_subject(as_id, codename, ring=ring)
                    self.associate_time(as_id, time_id, ring=ring)
                    """delete information entries"""
                    if ensa.current_subject != subject_id:
                        ensa.current_subject = subject_id
                    self.delete_information(y[0])
                    self.delete_information(m[0])
                    self.delete_information(d[0])


###########################################
# Subject methods
###########################################

    def create_subject(self, codename, note=None, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return None
        try:
            self.query(("INSERT INTO Subject(ring_id, codename, created, note) "
                        "VALUES(:r, :c, :d, :n)"),
                       {'r': ring,
                        'c': codename,
                        'd': datetime.now(),
                        'n': note})
            #subject_id = self.query("SELECT LAST_INSERT_ID()")[0][0]
            subject_id = self.query(("SELECT subject_id "
                                     "FROM Subject "
                                     "ORDER BY subject_id DESC LIMIT 1"))[0][0]
            if not subject_id:
                log.err('Cannot retrieve the new subject ID.')
                return None
            ensa.current_subject = subject_id
            self.create_information(Database.INFORMATION_TEXT,
                                    'codename',
                                    codename,
                                    accuracy=10,
                                    level=None,
                                    valid=True,
                                    note=None)
            return subject_id
        except:
            log.debug_error()
            return None

    def get_subjects(self, codename=None, sort='codename', ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return []
        if codename:
            codename_condition = "AND codename like '%" + codename + "%' "
        else:
            codename_condition = " "
        result = self.query(("SELECT subject_id, codename, created, note "
                             "FROM Subject "
                             "WHERE ring_id = :r " + codename_condition +
                             "ORDER BY :s"),
                            {'r': ring,
                             's': sort})
        return result

    def select_subject(self, codename, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return None
        result = self.query(("SELECT subject_id "
                             "FROM Subject "
                             "WHERE codename = :c "
                             "      AND ring_id = :r"),
                            {'c': codename,
                             'r': ring})
        if result:
            return result[0][0]
        log.err('There is no such subject in this ring.')
        return None

    def get_subject_codename(self, subject_id, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return None
        result = self.query(("SELECT codename "
                             "FROM Subject "
                             "WHERE subject_id = :s "
                             "      AND ring_id = :r"),
                            {'s': subject_id,
                             'r': ring})
        if result:
            return result[0][0]
        log.err('There is no such subject in this ring.')
        return None

    def delete_subject(self, subject_id, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return
        self.query(("DELETE FROM Subject "
                    "WHERE subject_id = :s "
                    "      AND ring_id = :r"),
                   {'s': subject_id,
                    'r': ring})

    def update_subject(self, subject_id, note, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return
        self.query(("UPDATE Subject "
                    "SET note = :n "
                    "WHERE subject_id = :s "
                    "      AND ring_id = :r"),
                    {'n': note,
                     's': subject_id, 
                     'r': ring})
###########################################
# Information methods
###########################################

    def information_cleanup(self, *args):
        if not args or 'composites' in args:
            self.query(("DELETE FROM Information "
                        "WHERE type = :t "
                        "      AND information_id NOT IN "
                        "          (SELECT information_id "
                        "           FROM Composite)"),
                       {'t': Database.INFORMATION_COMPOSITE, })
        if not args or 'keywords' in args:
            self.query(("DELETE FROM Keyword "
                        "WHERE keyword_id NOT IN "
                        "      (SELECT keyword_id FROM IK)"))

    def create_information(self,
                           info_type,
                           name,
                           value,
                           accuracy=ensa.config['interaction.default_accuracy'].value,
                           level=None,
                           valid=True,
                           note=None,
                           active=True,
                           subject=None):
        subject = subject or ensa.current_subject
        if not self.subject_ok(subject):
            return None
        try:
            self.query(("INSERT INTO Information(subject_id, type, name, "
                        "            accuracy, level, valid, modified, note) "
                        "VALUES(:s, :t, :n, :a, :l, :v, :m, :note)"),
                       {'s': ensa.current_subject,
                        't': info_type,
                        'n': name,
                        'a': accuracy,
                        'l': level,
                        'v': valid,
                        'm': datetime.now(),
                        'note': note})
            #information_id = self.query("SELECT LAST_INSERT_ID()")[0][0]
            information_id = self.query(("SELECT information_id "
                                         "FROM Information "
                                         "ORDER BY information_id DESC LIMIT 1"
                                         ))[0][0]

            if info_type == Database.INFORMATION_TEXT:
                self.query(("INSERT INTO Text(information_id, value) "
                            "VALUES(:i, :v)"),
                           {'i': information_id,
                            'v': value})

            elif info_type == Database.INFORMATION_COMPOSITE:
                if type(value) in (filter, tuple, list):
                    value = ','.join(str(v) for v in value)
                self.query(("INSERT INTO Composite(information_id, part_id) "
                            "SELECT :i, information_id "
                            "FROM Information "
                            "WHERE information_id IN ("+value+") "
                            "      AND subject_id = :s"),
                           {'i': information_id,
                            's': subject})
                self.information_cleanup('composites')

            """ set active/inactive """
            self.add_active(information_id, 
                            ensa.variables['reference_time_id'], 
                            active)

            return information_id
        except:
            log.debug_error()
            return None

    def add_binary(self, information_id, filename, subject=None):
        """
        adds binary content to an existing information entry
        """
        subject = subject or ensa.current_subject
        """move file from uploads/ to binary/, rename properly"""
        os.rename('files/uploads/%s' % filename,
                  'files/binary/%d' % information_id)
        """add extension as keyword"""
        extension = filename.rpartition('.')[2].lower()
        ensa.db.add_keyword(information_id,
                            'extension:%s' % extension, subject=subject)
        """try to guess file type"""
        if extension in ('jpg', 'png', 'bmp', 'gif'):
            ensa.db.add_keyword(information_id, 'image', subject=subject)
        if extension in ('doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
                         'pps', 'ppsx', 'pdf', 'odt', 'txt'):
            ensa.db.add_keyword(information_id, 'document', subject=subject)
        # TODO more

    def delete_information(self, information_id, subject=None):
        subject = subject or ensa.current_subject
        # test if can delete
        try:
            subject_id, info_type = self.query(("SELECT subject_id, type "
                                                "FROM Information "
                                                "WHERE information_id = :i"),
                                               {'i': information_id})[0]
            if subject_id != subject:
                raise AttributeError
        except:
            log.debug_error()
            log.err('That information does not belong to current subject.')
            return
        self.query(("DELETE FROM Information "
                    "WHERE information_id = :i"),
                   {'i': information_id})
        if os.path.isfile('files/binary/%s' % information_id):
            os.remove('files/binary/%d' % information_id)
        log.info('Information deleted.')

    def get_informations(self, info_type=None, no_composite_parts=False, ring=None, subject=None, force_no_current_subject=False, reference_time=None):
        ring = ring or ensa.current_ring
        subject = subject or ensa.current_subject
        reference_time = (lib.datetime_from_str(self.get_time(reference_time, force_no_current_ring=True)[1])
                          if reference_time
                          else ensa.variables['reference_time'])
        print(reference_time)
        # if not self.subject_ok(subject):
        #    return []
        if info_type is None:
            info_type = Database.INFORMATION_ALL
        result = []
        if subject and not force_no_current_subject:
            if no_composite_parts:
                """ by subject, no components """
                infos_nodata = self.query((
                    "SELECT I.information_id, I.subject_id, S.codename, "
                    "       I.type, I.name, I.level, I.accuracy, I.valid, "
                    "       I.modified, I.note "
                    "FROM Subject S INNER JOIN Information I "
                    "     ON S.subject_id = I.subject_id "
                    "WHERE I.subject_id = :s "
                    "      AND I.information_id NOT IN "
                    "          (SELECT part_id FROM Composite) "
                    "ORDER BY I.name"), {'s': subject})
            else:
                """ by subject, all """
                infos_nodata = self.query((
                    "SELECT I.information_id, I.subject_id, S.codename, "
                    "       I.type, I.name, I.level, I.accuracy, I.valid, "
                    "       I.modified, I.note "
                    "FROM Subject S INNER JOIN Information I "
                    "     ON S.subject_id = I.subject_id "
                    "WHERE I.subject_id = :s "
                    "ORDER BY I.name"), {'s': subject})
        else:
            if no_composite_parts:
                """ all in ring, no components """
                infos_nodata = self.query((
                    "SELECT I.information_id, I.subject_id, S.codename, "
                    "       I.type, I.name, I.level, I.accuracy, I.valid, "
                    "       I.modified, I.note "
                    "FROM Subject S INNER JOIN Information I "
                    "     ON S.subject_id = I.subject_id "
                    "WHERE S.ring_id = :r "
                    "      AND I.information_id NOT IN "
                    "          (SELECT part_id FROM Composite) "
                    "ORDER BY I.name"), {'r': ring})
            else:
                """ all in ring, all """
                infos_nodata = self.query((
                    "SELECT I.information_id, I.subject_id, S.codename, "
                    "       I.type, I.name, I.level, I.accuracy, I.valid, "
                    "       I.modified, I.note "
                    "FROM Subject S INNER JOIN Information I "
                    "     ON S.subject_id = I.subject_id "
                    "WHERE S.ring_id = :r "
                    "ORDER BY I.name"), {'r': ring})

        infos = []
        for info in infos_nodata:
            """ get active/inactive """
            active_times = self.query(("SELECT T.time, A.active "
                                       "FROM Time T INNER JOIN Active A"
                                       "     ON T.time_id = A.time_id "
                                       "WHERE A.information_id = :i "
                                       "ORDER BY T.time"),
                                      {'i': info[0]})
            is_active = False
            for time, active in active_times:
                if lib.datetime_from_str(time) <= reference_time:
                    is_active = bool(active)
                else:
                    break

            """ get value """
            if info[3] in [Database.INFORMATION_ALL,
                           Database.INFORMATION_TEXT]:
                value = self.query(("SELECT value "
                                    "FROM Text "
                                    "WHERE information_id = :i"),
                                   {'i': info[0]})[0][0]
                '''
                elif info[3] in [Database.INFORMATION_ALL, 
                                 Database.INFORMATION_BINARY]:
                    value = '[binary]'
                '''
            elif info[3] in [Database.INFORMATION_ALL,
                             Database.INFORMATION_COMPOSITE]:
                value = [row[0] for row in self.query((
                    "SELECT part_id "
                    "FROM Composite "
                    "WHERE information_id = :i"), {'i': info[0]})]
            else:
                value = 'ERROR'

            to_add = [is_active]
            if (info_type == Database.INFORMATION_ALL
                    or info_type == info[3]):
                to_add = [is_active, value]
            infos.append(tuple(list(info) + to_add))
        #for info in infos:
        #    print(info)
        return infos

    def get_information(self, information_id, subject=None):
        subject = subject or ensa.current_subject
        try:
            info = self.query(
                ("SELECT I.information_id, S.codename, I.type, I.name, "
                 "       I.level, I.accuracy, I.valid, I.note "
                 "FROM Subject S INNER JOIN Information I "
                 "     ON S.subject_id = I.subject_id "
                 "WHERE I.subject_id = :s "
                 "      AND I.information_id = :i"),
                {'s': subject, 'i': information_id})[0]
        except:
            log.err('There is no such information.')
            log.debug_error()
            return []

        if info[2] in [Database.INFORMATION_ALL,
                       Database.INFORMATION_TEXT]:
            value = self.query(("SELECT value "
                                "FROM Text "
                                "WHERE information_id = :i"),
                               {'i': info[0]})[0][0]
            '''
            elif info[2] in [Database.INFORMATION_ALL, 
                             Database.INFORMATION_BINARY]:
                value = b'[binary]'
            '''
        elif info[2] in [Database.INFORMATION_ALL,
                         Database.INFORMATION_COMPOSITE]:
            value = ' '.join(row[0] for row in self.query((
                "SELECT part_id "
                "FROM Composite "
                "WHERE information_id = :i"), {'i': information_id}))
        else:
            value = 'ERROR'
        return tuple(list(info)+[value])

    def update_information(self, subject=None, **kwargs):
        subject = subject or ensa.current_subject
        if not self.subject_ok(subject):
            return
        try:
            args = {k: kwargs[v] for k, v in {
                's': 'subject_id',
                'n': 'name',
                'l': 'level',
                'a': 'accuracy',
                'v': 'valid',
                'note': 'note',
                'i': 'information_id'}.items()}
            args.update({'d': datetime.now()})
            self.query(("UPDATE Information "
                        "SET modified = :d, subject_id = :s, name = :n, "
                        "    level = :l, accuracy = :a, valid = :v, "
                        "    note = :note "
                        "WHERE information_id = :i AND subject_id = :s"), args)
            if 'value' in kwargs.keys():
                self.query(("UPDATE Text "
                            "SET value = :v "
                            "WHERE information_id = :i "
                            "      AND information_id IN"
                            "          (SELECT information_id "
                            "           FROM Information "
                            "           WHERE subject_id = :s)"),
                           {'v': kwargs['value'],
                            'i': kwargs['information_id'],
                            's': subject})
            # elif 'path' in kwargs.keys():# TODO binary
            # elif 'compounds' in kwargs.keys(): # TODO composite without edit support?
        except:
            log.debug_error()
            log.err("Information update failed.")

    def update_information_metadata(self,
                                    information_ids,
                                    accuracy=None,
                                    level=None,
                                    valid=None,
                                    note=None,
                                    subject=None):
        subject = subject or ensa.current_subject
        if not self.subject_ok(subject):
            return
        if accuracy is not None:
            self.query(("UPDATE Information "
                        "SET modified = :m, accuracy = :a "
                        "WHERE subject_id = :s "
                        "      AND information_id IN ("+information_ids+")"),
                       {'m': datetime.now(),
                        'a': accuracy,
                        's': subject})
        elif valid is not None:
            self.query(("UPDATE Information "
                        "SET modified = :m, valid = :v "
                        "WHERE subject_id = :s "
                        "      AND information_id IN ("+information_ids+")"),
                       {'m': datetime.now(),
                        'v': valid,
                        's': subject})
        elif note:
            self.query(("UPDATE Information "
                        "SET modified = :m, note = :n "
                        "WHERE subject_id = :s "
                        "      AND information_id IN ("+information_ids+")"),
                       {'m': datetime.now(),
                        'n': note,
                        's': subject})
        else:  # only level remains
            self.query(("UPDATE Information "
                        "SET modified = :m, level = :l "
                        "WHERE subject_id = :s "
                        "      AND information_id IN ("+information_ids+")"),
                       {'m': datetime.now(),
                        'l': level,
                        's': subject})

###########################################
# Active methods
###########################################
    def add_active(self, information_id, time_id, active):
        self.query(("INSERT INTO Active(information_id, time_id, active) "
                    "VALUES(:i, :t, :a)"),
                   {'i': information_id,
                    't': time_id,
                    'a': active})

    def set_active(self, information_ids, time_id, active):
        if type(information_ids) == int:
            information_ids = str(information_ids)
        if type(information_ids) in (filter, tuple, list):
            information_ids = ','.join(str(x) for x in information_ids)
        self.query(("UPDATE Active "
                    "SET active = :a "
                    "WHERE information_id IN (" + information_ids + ") "
                    "      AND time_id = :t "),
                   {'t': time_id,
                    'a': active})
###########################################
# Location methods
###########################################


    def create_location(self,
                        name,
                        lat,
                        lon,
                        accuracy=0,
                        valid=True,
                        note=None, 
                        ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return None
        try:
            self.query(("INSERT INTO Location(name, lat, lon, accuracy, valid, "
                        "                     ring_id, modified, note) "
                        "VALUES(:n, :lat, :lon, :a, :v, :r, :m, :note)"),
                       {'n': name,
                        'lat': lat,
                        'lon': lon,
                        'a': accuracy,
                        'v': valid,
                        'r': ring,
                        'm': datetime.now(),
                        'note': note})
            location_id = self.query("SELECT location_id "
                                     "FROM Location "
                                     "ORDER BY location_id DESC LIMIT 1")[0][0]
            return location_id
        except:
            log.debug_error()
            return None

    def get_locations(self, sort='name', ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return []
        result = self.query(("SELECT location_id, name, lat, lon, "
                             "       accuracy, valid, modified, note "
                             "FROM Location "
                             "WHERE ring_id = :r "
                             "ORDER BY name"), # TODO use sort here when it works
                            {'r': ring,
                             's': sort})
        #print(result)
        return result

    def delete_locations(self, location_ids, ring=None):
        ring = ring or ensa.current_ring
        if type(location_ids) == int:
            location_ids = str(location_ids)
        if type(location_ids) in (filter, tuple, list):
            location_ids = ','.join(str(x) for x in location_ids)
        if self.ring_ok(ring):
            self.query(("DELETE FROM Location "
                        "WHERE location_id IN ("+location_ids+") "
                        "      AND ring_id = :r"),
                       {'r': ring})

    def get_location(self, location_id, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return []
        try:
            info = self.query(("SELECT location_id, name, lat, lon, "
                               "       accuracy, valid, note "
                               "FROM Location "
                               "WHERE location_id = :l "
                               "      AND ring_id = :r"),
                              {'l': location_id,
                               'r': ring})[0]
        except:
            log.err('There is no such location.')
            log.debug_error()
            return []
        return info

    def update_location(self, ring=None, **kwargs):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return
        try:
            args = {k: kwargs[v] for k, v in {
                'l': 'location_id',
                'lat': 'lat',
                'lon': 'lon',
                'n': 'name',
                'a': 'accuracy',
                'v': 'valid',
                'note': 'note'}.items()}
            args.update({
                'd': datetime.now(),
                'r': ring})

            self.query(("UPDATE Location "
                        "SET modified = :d, name = :n, lat = :lat, lon = :lon,"
                        "    accuracy = :a, valid = :v, note = :note "
                        "WHERE location_id = :l "
                        "      AND ring_id = :r"), args)
        except:
            log.debug_error()
            log.err("Location update failed.")

    def update_location_metadata(self,
                                 location_ids,
                                 accuracy=None,
                                 valid=None,
                                 note=None, 
                                 ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return
        if type(location_ids) == int:
            location_ids = str(location_ids)
        if type(location_ids) in (filter, tuple, list):
            location_ids = ','.join(str(x) for x in location_ids)
        if accuracy:
            self.query(("UPDATE Location "
                        "SET modified = :m, accuracy = :a "
                        "WHERE ring_id = :r "
                        "      AND location_id IN ("+location_ids+")"),
                       {'m': datetime.now(),
                        'a': accuracy,
                        'r': ring})
        elif valid is not None:
            self.query(("UPDATE Location "
                        "SET modified = :m, valid = :v "
                        "WHERE ring_id = :r "
                        "      AND location_id IN ("+location_ids+")"),
                       {'m': datetime.now(),
                        'v': valid,
                        'r': ring})
        elif note:
            self.query(("UPDATE Location "
                        "SET modified = :m, note = :n "
                        "WHERE ring_id = :r "
                        "      AND location_id IN ("+location_ids+")"),
                       {'m': datetime.now(),
                        'n': note,
                        'r': ring})

###########################################
# Time methods
###########################################
    def create_time(self, d, t, accuracy=0, valid=True, note=None, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return None
        '''
        try:
            datetime.datetime.strptime(d, '%Y-%m-%d')
        except:
            d = '0000-00-00'
        try:
            datetime.datetime.strptime(t, '%H:%M:%S')
        except:
            try:
                datetime.datetime.strptime(t, '%H:%M')
            except:
                t = '00:00:00'
        dt = '%s %s' % (d, t)
        '''
        dt = lib.datetime_from_str('%s %s' % (d, t))
        # TODO find if not exists
        try:
            self.query(("INSERT INTO Time(time, accuracy, valid, ring_id, "
                        "                 modified, note) "
                        "VALUES(:d, :a, :v, :r, :m, :n)"),
                       {'d': dt,
                        'a': accuracy,
                        'v': valid,
                        'r': ring,
                        'm': datetime.now(),
                        'n': note})
            time_id = self.query("SELECT time_id "
                                 "FROM Time "
                                 "ORDER BY time_id DESC LIMIT 1")[0][0]
            return time_id
        except:
            log.debug_error()
            return None

    def get_times(self, interval=None, sort='time', ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return []
        result = self.query(("SELECT time_id, "
                             #"       DATE_FORMAT(time, '%Y-%m-%d %H:%i:%s'), "
                             "       time, "
                             "       accuracy, valid, modified, note "
                             #"       accuracy, valid, note "
                             "FROM Time "
                             "WHERE ring_id = :r "
                             "ORDER BY time"), # TODO use sort here when it works
                            {'r': ring,
                             's': sort})
        #print(result)
        if interval:
            start, end = interval
            if type(start) == str:
                start = lib.datetime_from_str(start)
            if type(end) == str:
                end = lib.datetime_from_str(end)
            result = [x for x in result 
                      if lib.datetime_from_str(x[1]) >= start 
                      and lib.datetime_from_str(x[1]) <= end]
        return result

    def delete_times(self, time_ids, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return []
        if type(time_ids) == int:
            time_ids = str(time_ids)
        if type(time_ids) in (filter, tuple, list):
            time_ids = ','.join(str(x) for x in time_ids)
        self.query(("DELETE FROM Time "
                    "WHERE time_id IN ("+time_ids+") "
                    "      AND ring_id = :r"), {'r': ensa.ring})

    def get_time(self, time_id, force_no_current_ring=False, ring=None):
        ring = ring or ensa.current_ring
        try:
            if force_no_current_ring:
                info = self.query(("SELECT time_id, "
                                   "       time,"
                                   "       accuracy, valid, note "
                                   "FROM Time "
                                   "WHERE time_id = :t "),
                                  {'t': time_id})[0]
            else:
                if not self.ring_ok(ring):
                    return []
                info = self.query(("SELECT time_id, "
                                   "       time,"
                                   "       accuracy, valid, note "
                                   "FROM Time "
                                   "WHERE time_id = :t "
                                   "      AND ring_id = :r"),
                                  {'t': time_id,
                                   'r': ring})[0]
        except:
            log.err('There is no such time entry.')
            log.debug_error()
            return []
        return info

    def update_time(self, ring=None, **kwargs):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return []
        try:
            args = {k: kwargs[v] for k, v in {
                't': 'time_id',
                'd': 'datetime',
                'a': 'accuracy',
                'v': 'valid',
                'note': 'note'}.items()}
            args.update({'m': datetime.now(),
                         'r': ring})
            self.query(("UPDATE Time "
                        "SET modified = :m, time = :d, accuracy = :a, "
                        "    valid = :v, note = :note "
                        "WHERE time_id = :t "
                        "      AND ring_id = :r"), args)
        except:
            log.debug_error()
            log.err("Time update failed.")

    def update_time_metadata(self,
                             time_ids,
                             accuracy=None,
                             valid=None,
                             note=None,
                             ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return []
        if type(time_ids) == int:
            time_ids = str(time_ids)
        if type(time_ids) in (filter, tuple, list):
            time_ids = ','.join(str(x) for x in time_ids)
        if accuracy:
            self.query(("UPDATE Time "
                        "SET modified = :m, accuracy = :a "
                        "WHERE ring_id = :r "
                        "      AND time_id IN ("+time_ids+")"),
                       {'m': datetime.now(),
                        'a': accuracy,
                        'r': ring})
        elif valid is not None:
            self.query(("UPDATE Time "
                        "SET modified = :m, valid = :v "
                        "WHERE ring_id = :r "
                        "      AND time_id IN ("+time_ids+")"),
                       {'m': datetime.now(),
                        'v': valid,
                        'r': ring})
        elif note:
            self.query(("UPDATE Time "
                        "SET modified = :m, note = :n "
                        "WHERE ring_id = :r "
                        "      AND time_id IN ("+time_ids+")"),
                       {'m': datetime.now(),
                        'n': note,
                        'r': ring})

###########################################
# Association methods
###########################################
    def create_association(self, level=None, accuracy=0, valid=True, note=None, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return None
        try:
            self.query(("INSERT INTO Association(ring_id, level, accuracy, "
                        "                        valid, modified, note) "
                        "VALUES(:r, :l, :a, :v, :m, :n)"),
                       {'r': ring,
                        'l': level,
                        'a': accuracy,
                        'v': valid,
                        'm': datetime.now(),
                        'n': note})
            association_id = self.query("SELECT association_id "
                                        "FROM Association "
                                        "ORDER BY association_id DESC "
                                        "LIMIT 1")[0][0]
            return association_id
        except:
            log.debug_error()
            return None

    def associate_association(self, association_id, association_ids, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return None
        if type(association_ids) == int:
            association_ids = str(association_ids)
        if type(association_ids) in (filter, tuple, list):
            association_ids = ','.join(str(x) for x in association_ids)
        try:
            ring_id = self.query(("SELECT DISTINCT ring_id "
                                  "FROM Association "
                                  "WHERE association_id = :a "
                                  "      OR association_id IN "
                                  "          ("+association_ids+")"),
                                 {'a': association_id})
            if len(ring_id) != 1:
                raise AttributeError
            ring_id = ring_id[0][0]
            if ring_id != ring:
                raise AttributeError
        except:
            log.err('All associations must belong to current ring.')
            return None
        try:
            count_before = self.query("SELECT COUNT(*) FROM AA")[0][0]
            self.query(("INSERT INTO AA(association_id_1, association_id_2) "
                        "SELECT :a, association_id "
                        "FROM Association "
                        "WHERE association_id IN (" + association_ids + ") "
                        "      AND ring_id = :r"),
                       {'a': association_id,
                        'r': ring})
            count_after = self.query("SELECT COUNT(*) FROM AA")[0][0]
            if count_before == count_after:
                log.err('Association must belong to current ring.')
                return None
            self.query(("UPDATE Association "
                        "SET modified = :m "
                        "WHERE association_id = :a"),
                       {'m': datetime.now(),
                        'a': association_id})
            return tuple([(association_id, a)
                          for a in association_ids.split(',')])
        except:
            log.debug_error()
            log.err('Failed to associate association.')
            return None

    def associate_information(self, association_id, information_ids, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return None
        if type(information_ids) == int:
            information_ids = str(information_ids)
        if type(information_ids) in (filter, tuple, list):
            information_ids = ','.join(str(x) for x in information_ids)
        try:
            ring_id = self.query(("SELECT ring_id "
                                  "FROM Association "
                                  "WHERE association_id = :a"),
                                 {'a': association_id})[0][0]
            if ring_id != ring:
                raise AttributeError
        except:
            log.err('Current ring has no such asssociation.')
            return None
        try:
            count_before = self.query("SELECT COUNT(*) FROM AI")[0][0]
            self.query(("INSERT INTO AI(association_id, information_id) "
                        "SELECT :a, information_id "
                        "FROM Information "
                        "WHERE information_id IN (" + information_ids + ") "
                        "      AND subject_id IN "
                        "          (SELECT subject_id "
                        "           FROM Subject "
                        "         WHERE ring_id = :r)"),
                       {'a': association_id,
                        'r': ring})
            count_after = self.query("SELECT COUNT(*) FROM AI")[0][0]
            if count_before == count_after:
                log.err('Information must belong to current ring.')
                return None
            self.query(("UPDATE Association "
                        "SET modified = :m "
                        "WHERE association_id = :a"),
                       {'m': datetime.now(),
                        'a': association_id})
            return tuple([(association_id, i) for i in information_ids])
        except:
            log.err('Failed to associate information.')
            return None

    def associate_location(self, association_id, location_ids, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return None
        if type(location_ids) == int:
            location_ids = str(location_ids)
        if type(location_ids) in (filter, tuple, list):
            location_ids = ','.join(str(x) for x in location_ids)
        try:
            ring_id = self.query(("SELECT ring_id "
                                  "FROM Association "
                                  "WHERE association_id = :a"),
                                 {'a': association_id})[0][0]
            if ring_id != ring:
                raise AttributeError
        except:
            log.err('Current ring has no such asssociation.')
            return None
        try:
            count_before = self.query("SELECT COUNT(*) FROM AL")[0][0]
            self.query(("INSERT INTO AL(association_id, location_id) "
                        "SELECT :a, location_id "
                        "FROM Location "
                        "WHERE location_id IN (" + location_ids + ") "
                        "      AND ring_id = :r"),
                       {'a': association_id,
                        'r': ring})
            count_after = self.query("SELECT COUNT(*) FROM AL")[0][0]
            if count_before == count_after:
                log.err('Location must belong to current ring.')
                return None
            self.query(("UPDATE Association "
                        "SET modified = :m "
                        "WHERE association_id = :a"),
                       {'m': datetime.now(),
                        'a': association_id})
            return tuple([(association_id, l) for l in location_ids])
        except:
            log.debug_error()
            log.err('Failed to associate location.')
            return None

    def associate_subject(self, association_id, codenames, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return None
        if type(codenames) in (filter, tuple, list):
            codenames = "','".join(codenames)
        try:
            ring_id = self.query(("SELECT ring_id "
                                  "FROM Association "
                                  "WHERE association_id = :a"),
                                 {'a': association_id})[0][0]
            if ring_id != ring:
                raise AttributeError
        except:
            log.err('Current ring has no such asssociation.')
            return None
        try:
            count_before = self.query("SELECT COUNT(*) FROM AI")[0][0]
            # pdb.set_trace()
            self.query(("INSERT INTO AI(association_id, information_id) "
                        "SELECT :a, I.information_id "
                        "FROM Subject S INNER JOIN Information I "
                        "     ON S.subject_id = I.subject_id "
                        "WHERE I.name = 'codename' "
                        "      AND S.codename IN ('" + codenames + "') "
                        "      AND S.ring_id = :r"),
                       {'a': association_id, 'r': ring})
            count_after = self.query("SELECT COUNT(*) FROM AI")[0][0]
            if count_before == count_after:
                log.err('Subject must belong to current ring.')
                return None
            self.query(("UPDATE Association "
                        "SET modified = :m "
                        "WHERE association_id = :a"),
                       {'m': datetime.now(),
                        'a': association_id})
            return tuple([(association_id, codename)
                          for codename in codenames.split(',')])
        except:
            log.debug_error()
            log.err('Failed to associate subject.')
            return None

    def associate_time(self, association_id, time_ids, ring=None):
        ring = ring or ensa.current_ring
        #import pdb
        # pdb.set_trace()
        if not self.ring_ok(ring):
            return None
        if type(time_ids) == int:
            time_ids = str(time_ids)
        if type(time_ids) in (filter, tuple, list):
            time_ids = ','.join(str(x) for x in time_ids)
        try:
            ring_id = self.query(("SELECT ring_id "
                                  "FROM Association "
                                  "WHERE association_id = :a"),
                                 {'a': association_id})[0][0]
            if ring_id != ring:
                raise AttributeError
        except:
            log.err('Current ring has no such asssociation.')
            return None
        try:
            count_before = self.query("SELECT COUNT(*) FROM AT")[0][0]
            self.query(("INSERT INTO AT(association_id, time_id) "
                        "SELECT :a, time_id "
                        "FROM Time "
                        "WHERE time_id IN (" + time_ids + ") "
                        "      AND ring_id = :r"),
                       {'a': association_id,
                        'r': ring})
            count_after = self.query("SELECT COUNT(*) FROM AT")[0][0]
            if count_before == count_after:
                log.err('Time must belong to current ring.')
                return None
            self.query(("UPDATE Association "
                        "SET modified = :m "
                        "WHERE association_id = :a"),
                       {'m': datetime.now(),
                        'a': association_id})
            return tuple([(association_id, t) for t in time_ids])
        except:
            log.debug_error()
            log.err('Failed to associate time.')
            return None

    def get_associations(self, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return []
        # get associations
        return self.query(("SELECT association_id, ring_id, level, accuracy, "
                           "       valid, modified, note "
                           "FROM Association "
                           "WHERE ring_id = :r"),
                          {'r': ring})

    def get_associations_by_X(self, query, query_args=None, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return []
        # get associations
        associations = self.query(query, query_args)

        result = []
        for assoc in associations:
            # in current ring?
            if assoc[1] != ring:
                continue
            # TODO is ring check needed for ITL entries?
            # get info entries (+ subject)
            infos_nodata = self.query(
                ("SELECT I.information_id, I.subject_id, S.codename, "
                 "       I.type, I.name, I.level, I.accuracy, I.valid, "
                 "       I.modified, I.note "
                 "FROM Subject S INNER JOIN Information I "
                 "     ON S.subject_id = I.subject_id "
                 "WHERE information_id IN "
                 "    (SELECT information_id "
                 "     FROM AI "
                 "     WHERE association_id = :a) "
                 "ORDER BY information_id"), {'a': assoc[0]})
            infos = []
            for info in infos_nodata:
                """ get active/inactive """
                active_times = self.query(("SELECT T.time, A.active "
                                           "FROM Time T INNER JOIN Active A"
                                           "     ON T.time_id = A.time_id "
                                           "WHERE A.information_id = :i "
                                           "ORDER BY T.time"),
                                          {'i': info[0]})
                is_active = False
                for time, active in active_times:
                    if lib.datetime_from_str(time) <= ensa.variables['reference_time']:
                        is_active = bool(active)
                    else:
                        break
                """ get data """
                if info[3] == Database.INFORMATION_TEXT:
                    value = self.query(("SELECT value "
                                        "FROM Text "
                                        "WHERE information_id = :i"),
                                       {'i': info[0]})[0][0]
                elif info[3] == Database.INFORMATION_BINARY:
                    value = '[binary]'
                elif info[3] == Database.INFORMATION_COMPOSITE:
                    value = [row[0] for row in self.query((
                        "SELECT part_id "
                        "FROM Composite "
                        "WHERE information_id = :i"), {'i': info[0]})]
                else:
                    value = 'ERROR'
                infos.append(tuple(list(info)+[is_active, value]))
            # get time entries
            times = self.query(("SELECT Time.time_id, "
                                #"       DATE_FORMAT(time, '%Y-%m-%d %H:%i:%s'),"
                                "       time, accuracy, valid, modified, note "
                                "FROM Time INNER JOIN AT "
                                "     ON Time.time_id = AT.time_id "
                                "WHERE AT.association_id = :a"),
                               {'a': assoc[0]}) or []
            # get location entries
            locations = self.query(("SELECT L.location_id, name, "
                                    "       lat, lon, accuracy, valid, "
                                    "       modified, note "
                                    "FROM Location L INNER JOIN AL "
                                    "     ON L.location_id = AL.location_id "
                                    "WHERE AL.association_id = :a"),
                                   {'a': assoc[0]}) or []
            # get associated associations
            associations = self.query(("SELECT association_id, ring_id, level, "
                                       "       accuracy, valid, modified, note "
                                       "FROM Association "
                                       "WHERE association_id IN"
                                       "      (SELECT association_id_2 "
                                       "       FROM AA "
                                       "       WHERE association_id_1 = :a)"),
                                      {'a': assoc[0]}) or []

            result.append((assoc, infos, times, locations, associations))
        return result

    def get_associations_by_ids(self, association_ids, ring=None):
        ring = ring or ensa.current_ring
        if type(association_ids) == int:
            association_ids = str(association_ids)
        elif type(association_ids) in (filter, tuple, list):
            association_ids = ','.join(str(x) for x in association_ids)
        query = ("SELECT DISTINCT association_id, ring_id, level, accuracy, "
                 "       valid, modified, note "
                 "FROM Association "
                 "WHERE association_id IN("+association_ids+")")
        return self.get_associations_by_X(query, ring=ring)

    def get_associations_by_note(self, string, ring=None):
        ring = ring or ensa.current_ring
        query = ("SELECT DISTINCT association_id, ring_id, level, accuracy, "
                 "       valid, modified, note "
                 "FROM Association "
                 "WHERE note LIKE '%"+string+"%'")
        return self.get_associations_by_X(query, ring=ring)

    def get_associations_by_location(self, location_ids, ring=None):
        ring = ring or ensa.current_ring
        if type(location_ids) == int:
            location_ids = str(location_ids)
        elif type(location_ids) in (filter, tuple, list):
            location_ids = ','.join(str(x) for x in location_ids)
        query = ("SELECT DISTINCT A.association_id, ring_id, level, accuracy, "
                 "       valid, modified, note "
                 "FROM Association A INNER JOIN AL "
                 "     ON A.association_id = AL.association_id "
                 "WHERE location_id IN("+location_ids+")")
        return self.get_associations_by_X(query, ring=ring)

    def get_associations_by_time(self, time_ids, ring=None):
        ring = ring or ensa.current_ring
        if type(time_ids) == int:
            time_ids = str(time_ids)
        elif type(time_ids) in (filter, tuple, list):
            time_ids = ','.join(str(x) for x in time_ids)
        query = ("SELECT DISTINCT A.association_id, ring_id, level, accuracy, "
                 "       valid, modified, note "
                 "FROM Association A INNER JOIN AT "
                 "     ON A.association_id = AT.association_id "
                 "WHERE time_id IN("+time_ids+")")
        return self.get_associations_by_X(query, ring=ring)

    def get_associations_by_information(self, information_ids, ring=None):
        ring = ring or ensa.current_ring
        if type(information_ids) == int:
            information_ids = str(information_ids)
        elif type(information_ids) in (filter, tuple, list):
            information_ids = ','.join(str(x) for x in information_ids)
        query = ("SELECT DISTINCT A.association_id, ring_id, level, accuracy, "
                 "       valid, modified, note "
                 "FROM Association A INNER JOIN AI "
                 "     ON A.association_id = AI.association_id "
                 "WHERE information_id IN("+information_ids+")")
        return self.get_associations_by_X(query, ring=ring)

    def get_associations_by_subject(self, codenames, ring=None):
        ring = ring or ensa.current_ring
        if type(codenames) in (filter, tuple, list):
            codenames = "','".join(codenames)
        query = ("SELECT DISTINCT A.association_id, A.ring_id, A.level, A.accuracy, "
                 "       A.valid, A.modified, A.note "
                 "FROM Association A "
                 "     INNER JOIN AI "
                 "         ON A.association_id = AI.association_id "
                 "     INNER JOIN Information I "
                 "         ON AI.information_id = I.information_id "
                 "     INNER JOIN Subject S "
                 "         ON I.subject_id = S.subject_id "
                 "WHERE S.codename IN('"+codenames+"')")
        return self.get_associations_by_X(query, ring=ring)

    def get_timeline_by_location(self, location_ids, ring=None):
        ring = ring or ensa.current_ring
        if type(location_ids) == int:
            location_ids = str(location_ids)
        elif type(location_ids) in (filter, tuple, list):
            location_ids = ','.join(str(i) for i in location_ids)
        query = ("SELECT DISTINCT A.association_id, A.ring_id, A.level, A.accuracy, "
                 "       A.valid, A.modified, A.note "
                 "FROM Association A "
                 "     INNER JOIN AL "
                 "         ON A.association_id = AL.association_id "
                 "     INNER JOIN AT "
                 "         ON A.association_id = AT.association_id "
                 "     INNER JOIN Time T "
                 "         ON T.time_id = AT.time_id "
                 "WHERE location_id IN("+location_ids+") "
                 "ORDER BY T.time")
        return self.get_associations_by_X(query, ring=ring)

    def get_timeline_by_information(self, information_ids, ring=None):
        ring = ring or ensa.current_ring
        if type(information_ids) == int:
            information_ids = str(information_ids)
        elif type(information_ids) in (filter, tuple, list):
            information_ids = ','.join(str(i) for i in information_ids)
        query = ("SELECT DISTINCT A.association_id, A.ring_id, A.level, A.accuracy, "
                 "       A.valid, A.modified, A.note "
                 "FROM Association A "
                 "     INNER JOIN AI "
                 "         ON A.association_id = AI.association_id "
                 "     INNER JOIN AT "
                 "         ON A.association_id = AT.association_id "
                 "     INNER JOIN Time T "
                 "         ON T.time_id = AT.time_id "
                 "WHERE information_id IN("+information_ids+") "
                 "ORDER BY T.time")
        return self.get_associations_by_X(query, ring=ring)

    def get_timeline_by_subject(self, codenames, ring=None):
        ring = ring or ensa.current_ring
        if type(codenames) in (filter, tuple, list):
            codenames = "','".join(codenames)
        query = ("SELECT DISTINCT A.association_id, A.ring_id, A.level, A.accuracy, "
                 "       A.valid, A.modified, A.note "
                 "FROM Association A "
                 "     INNER JOIN AI "
                 "         ON A.association_id = AI.association_id "
                 "     INNER JOIN Information I "
                 "         ON AI.information_id = I.information_id "
                 "     INNER JOIN Subject S "
                 "         ON I.subject_id = S.subject_id "
                 "     INNER JOIN AT "
                 "         ON A.association_id = AT.association_id "
                 "     INNER JOIN Time T "
                 "         ON T.time_id = AT.time_id "
                 "WHERE S.codename IN('"+codenames+"') "
                 "ORDER BY T.time")
        return self.get_associations_by_X(query, ring=ring)

    def get_timeline_by_range(self, start, end, ring=None):
        ring = ring or ensa.current_ring
        query = ("SELECT DISTINCT A.association_id, A.ring_id, A.level, A.accuracy, "
                 "       A.valid, A.modified, A.note "
                 "FROM Association A "
                 "     INNER JOIN AT "
                 "         ON A.association_id = AT.association_id "
                 "     INNER JOIN Time T "
                 "         ON T.time_id = AT.time_id "
                 "WHERE T.time BETWEEN :s AND :e "
                 "ORDER BY T.time")
        return self.get_associations_by_X(query, {'s': start, 'e': end}, ring=ring)

    def delete_associations(self, association_ids, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return
        self.query(("DELETE FROM Association "
                    "WHERE association_id IN ("+association_ids+") "
                    "      AND ring_id = :r"),
                   {'r': ring})

    def dissociate_associations(self, association_id, association_ids, ring=None):
        ring = ring or ensa.current_ring
        if type(association_ids) == int:
            association_ids = str(association_ids)
        elif type(association_ids) in (filter, tuple, list):
            association_ids = ','.join(str(x) for x in association_ids)
        if not self.ring_ok(ring):
            return
        self.query(("DELETE FROM AA "
                    "WHERE association_id_1 IN "
                    "    (SELECT association_id "
                    "     FROM Association "
                    "     WHERE association_id = :a "
                    "           AND ring_id = :r) "
                    "    AND association_id_2 IN ("+association_ids+")"),
                   {'a': association_id,
                    'r': ring})
        self.query(("UPDATE Association "
                    "SET modified = :m "
                    "WHERE association_id = :a "
                    "      AND ring_id = :r"),
                   {'m': datetime.now(),
                    'a': association_id,
                    'r': ring})

    def dissociate_informations(self, association_id, information_ids, ring=None):
        ring = ring or ensa.current_ring
        if type(information_ids) == int:
            information_ids = str(information_ids)
        elif type(information_ids) in (filter, tuple, list):
            information_ids = ','.join(str(x) for x in information_ids)
        if not self.ring_ok(ring):
            return
        self.query(("DELETE FROM AI "
                    "WHERE association_id IN "
                    "    (SELECT association_id "
                    "     FROM Association "
                    "     WHERE association_id = :a "
                    "           AND ring_id = :r) "
                    "    AND information_id IN ("+information_ids+")"),
                   {'a': association_id,
                    'r': ring})
        self.query(("UPDATE Association "
                    "SET modified = :m "
                    "WHERE association_id = :a "
                    "      AND ring_id = :r"),
                   {'m': datetime.now(),
                    'a': association_id,
                    'r': ring})

    def dissociate_locations(self, association_id, location_ids, ring=None):
        ring = ring or ensa.current_ring
        if type(location_ids) == int:
            location_ids = str(location_ids)
        elif type(location_ids) in (filter, tuple, list):
            location_ids = ','.join(str(x) for x in location_ids)
        if not self.ring_ok(ring):
            return []
        self.query(("DELETE FROM AL "
                    "WHERE association_id IN "
                    "    (SELECT association_id "
                    "     FROM Association "
                    "     WHERE association_id = :a "
                    "           AND ring_id = :r) "
                    "    AND location_id IN ("+location_ids+")"),
                   {'a': association_id,
                    'r': ring})
        self.query(("UPDATE Association "
                    "SET modified = :m "
                    "WHERE association_id = :a "
                    "      AND ring_id = :r"),
                   {'m': datetime.now(),
                    'a': association_id,
                    'r': ring})

    def dissociate_times(self, association_id, time_ids, ring=None):
        ring = ring or ensa.current_ring
        if type(time_ids) == int:
            time_ids = str(time_ids)
        elif type(time_ids) in (filter, tuple, list):
            time_ids = ','.join(str(x) for x in time_ids)
        if not self.ring_ok(ring):
            return []
        self.query(("DELETE FROM AT "
                    "WHERE association_id IN "
                    "    (SELECT association_id "
                    "     FROM Association "
                    "     WHERE association_id = :a "
                    "           AND ring_id = :r) "
                    "    AND time_id IN ("+time_ids+")"),
                   {'a': association_id,
                    'r': ring})
        self.query(("UPDATE Association "
                    "SET modified = :m "
                    "WHERE association_id = :a "
                    "      AND ring_id = :r"),
                   {'m': datetime.now(),
                    'a': association_id,
                    'r': ring})

    def get_association(self, association_id, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return []
        try:
            info = self.query(("SELECT association_id, level, accuracy, "
                               "       valid, note "
                               "FROM Association "
                               "WHERE association_id = :a "
                               "      AND ring_id = :r"),
                              {'a': association_id,
                               'r': ring})[0]
        except:
            log.err('There is no such association.')
            log.debug_error()
            return []
        return info

    def update_association(self, ring=None, **kwargs):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return []
        try:
            args = {k: kwargs[v] for k, v in {
                'as': 'association_id',
                'a': 'accuracy',
                'l': 'level',
                'v': 'valid',
                'n': 'note'}.items()}
            args.update({
                'm': datetime.now(),
                'r': ring})
            self.query("UPDATE Association "
                       "SET modified = :m, level = :l, accuracy = :a, "
                       "    valid = :v, note = :n "
                       "WHERE association_id = :as "
                       "      AND ring_id = :r", args)
        except:
            log.debug_error()
            log.err("Association update failed.")

    def update_association_metadata(self,
                                    association_ids,
                                    accuracy=None,
                                    level=None,
                                    valid=None,
                                    note=None,
                                    ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return []
        if type(association_ids) == int:
            association_ids = str(association_ids)
        elif type(association_ids) in (filter, tuple, list):
            association_ids = ','.join(str(x) for x in association_ids)
        if accuracy:
            self.query(("UPDATE Association "
                        "SET modified = :m, accuracy = :a "
                        "WHERE ring_id = :r "
                        "      AND association_id IN ("+association_ids+")"),
                       {'m': datetime.now(),
                        'a': accuracy,
                        'r': ring})
        elif valid is not None:
            self.query(("UPDATE Association "
                        "SET modified = :m, valid = :v "
                        "WHERE ring_id = :r "
                        "      AND association_id IN ("+association_ids+")"),
                       {'m': datetime.now(),
                        'v': valid,
                        'r': ring})
        elif note:
            self.query(("UPDATE Association "
                        "SET modified = :m, note = :n "
                        "WHERE ring_id = :r "
                        "      AND association_id IN ("+association_ids+")"),
                       {'m': datetime.now(),
                        'n': note,
                        'r': ring})
        else:  # only level remains
            self.query(("UPDATE Association "
                        "SET modified = :m, level = :l "
                        "WHERE ring_id = :r "
                        "      AND association_id IN ("+association_ids+")"),
                       {'m': datetime.now(),
                        'l': level,
                        'r': ring})

###########################################
# Keyword methods
###########################################
    def get_keyword_id(self, keyword):
        try:
            keyword_id = self.query(("SELECT keyword_id "
                                     "FROM Keyword "
                                     "WHERE keyword = :k"),
                                    {'k': keyword})[0][0]
        except:
            self.query(("INSERT INTO Keyword(keyword) "
                        "VALUES(:k)"), {'k': keyword})
            keyword_id = self.query(("SELECT keyword_id "
                                     "FROM Keyword "
                                     "ORDER BY keyword_id DESC LIMIT 1"))[0][0]
        return keyword_id

    def add_keyword(self, information_ids, keyword, subject=None):
        subject = subject or ensa.current_subject
        if not self.subject_ok(subject):
            return
        if type(information_ids) == int:
            information_ids = str(information_ids)
        elif type(information_ids) in (filter, tuple, list):
            information_ids = ','.join(str(x) for x in information_ids)
        keyword_id = self.get_keyword_id(keyword)
        self.query(("INSERT INTO IK(information_id, keyword_id) "
                    "SELECT information_id, :k "
                    "FROM Information "
                    "WHERE subject_id = :s "
                    "      AND information_id IN ("+information_ids+")"),
                   {'k': keyword_id,
                    's': subject})

    def delete_keywords(self, information_ids, keywords, subject=None):
        subject = subject or ensa.current_subject
        if not self.subject_ok(subject):
            return
        if keywords:
            keyword_ids = ','.join([str(x[0]) for x in self.query(
                "SELECT keyword_id "
                "FROM Keyword "
                "WHERE keyword IN ("+keywords+")")])
            self.query(("DELETE FROM IK "
                        "WHERE keyword_id IN ("+keyword_ids+") "
                        "      AND information_id IN "
                        "          (SELECT information_id "
                        "           FROM Information "
                        "           WHERE information_id IN(" +
                                                            information_ids+")"
                        "                 AND subject_id = :s)"),
                       {'s': subject})
        else:  # delete all keywords
            self.query(("DELETE FROM IK "
                        "WHERE information_id IN "
                        "      (SELECT information_id "
                        "       FROM Information "
                        "       WHERE information_id IN("+information_ids+")"
                        "       AND subject_id = :s)"),
                       {'s': subject})
        self.information_cleanup('keywords')

    def get_keywords(self, subject=None, ring=None):
        ring = ring or ensa.current_ring
        if not self.ring_ok(ring):
            return []
        if subject:
            result = self.query(("SELECT DISTINCT K.keyword "
                                 "FROM Keyword K "
                                 "    INNER JOIN IK "
                                 "     ON K.keyword_id = IK.keyword_id "
                                 "    INNER JOIN Information I "
                                 "     ON IK.information_id = I.information_id "
                                 "WHERE I.subject_id = :s "
                                 "ORDER BY K.keyword"),
                                {'s': subject})
        else:
            result = self.query(("SELECT DISTINCT K.keyword "
                                 "FROM Keyword K "
                                 "    INNER JOIN IK "
                                 "     ON K.keyword_id = IK.keyword_id "
                                 "    INNER JOIN Information I "
                                 "     ON IK.information_id = I.information_id "
                                 "    INNER JOIN Subject S "
                                 "     ON I.subject_id = S.subject_id "
                                 "WHERE S.ring_id = :r "
                                 "ORDER BY K.keyword"),
                                {'r': ring})
        return result

    def get_keywords_for_informations(self, information_ids, subject=None, force_no_current_subject=False):
        subject = subject or ensa.current_subject
        if type(information_ids) == int:
            information_ids = str(information_ids)
        elif type(information_ids) in (filter, tuple, list):
            information_ids = ','.join(str(x) for x in information_ids)
        if force_no_current_subject:
            result = self.query(("SELECT IK.information_id, K.keyword "
                                 "FROM IK INNER JOIN Keyword K "
                                 "     ON IK.keyword_id = K.keyword_id "
                                 "WHERE IK.information_id IN "
                                 "      (SELECT information_id "
                                 "       FROM Information "
                                 "       WHERE information_id IN "
                                 "           ("+information_ids+")) "))
        else:
            if not self.subject_ok(subject):
                return []
            result = self.query(("SELECT IK.information_id, K.keyword "
                                 "FROM IK INNER JOIN Keyword K "
                                 "     ON IK.keyword_id = K.keyword_id "
                                 "WHERE IK.information_id IN "
                                 "      (SELECT information_id "
                                 "       FROM Information "
                                 "       WHERE information_id IN "
                                 "           ("+information_ids+") "
                                 "       AND subject_id = :s)"),
                                {'s': subject})
        return result

    def get_informations_for_keywords_or(self, keywords, ring=None, subject=None):
        ring = ring or ensa.current_ring
        subject = subject or ensa.current_subject
        if not self.ring_ok(ring):
            return []
        if subject:
            infos_nodata = self.query(("SELECT I.information_id, I.subject_id, "
                                       "       S.codename, I.type, I.name, "
                                       "       I.level, I.accuracy, I.valid, "
                                       "       I.modified, I.note "
                                       "FROM Information I INNER JOIN Subject S"
                                       "     ON I.subject_id = S.subject_id "
                                       "WHERE I.subject_id = :s "
                                       "      AND I.information_id IN "
                                       "      (SELECT IK.information_id "
                                       "       FROM IK INNER JOIN Keyword K "
                                       "        ON IK.keyword_id = K.keyword_id"
                                       "       WHERE K.keyword IN "
                                       "           ("+keywords+"))"),
                                      {'s': subject})
        else:
            infos_nodata = self.query(("SELECT I.information_id, I.subject_id, "
                                       "       S.codename, I.type, I.name, "
                                       "       I.level, I.accuracy, I.valid, "
                                       "       I.modified, I.note "
                                       "FROM Information I INNER JOIN Subject S"
                                       "     ON I.subject_id = S.subject_id "
                                       "WHERE S.ring_id = :r "
                                       "      AND I.information_id IN "
                                       "      (SELECT IK.information_id "
                                       "       FROM IK INNER JOIN Keyword K "
                                       "        ON IK.keyword_id = K.keyword_id"
                                       "        WHERE K.keyword IN "
                                       "            ("+keywords+"))"),
                                      {'r': ring})
        infos = []
        for info in infos_nodata:
            """ get active/inactive """
            active_times = self.query(("SELECT T.time, A.active "
                                       "FROM Time T INNER JOIN Active A"
                                       "     ON T.time_id = A.time_id "
                                       "WHERE A.information_id = :i "
                                       "ORDER BY T.time"),
                                      {'i': info[0]})
            is_active = False
            for time, active in active_times:
                if lib.datetime_from_str(time) <= ensa.variables['reference_time']:
                    is_active = bool(active)
                else:
                    break
            """ get data """
            if info[3] in [Database.INFORMATION_ALL,
                           Database.INFORMATION_TEXT]:
                value = self.query(("SELECT value "
                                    "FROM Text "
                                    "WHERE information_id = :i"),
                                   {'i': info[0]})[0][0]
                '''
                elif info[3] in [Database.INFORMATION_ALL, 
                                 Database.INFORMATION_BINARY]:
                    value = '[binary]'
                '''
            elif info[3] in [Database.INFORMATION_ALL,
                             Database.INFORMATION_COMPOSITE]:
                value = [row[0] for row in self.query((
                    "SELECT part_id "
                    "FROM Composite "
                    "WHERE information_id = :i"), {'i': info[0]})]
            else:
                value = 'ERROR'
            infos.append(tuple(list(info)+[value]))
        return infos

    def get_informations_for_keywords_and(self, keywords, ring=None, subject=None):
        ring = ring or ensa.current_ring
        subject = subject or ensa.current_subject
        if not self.ring_ok(ring):
            return []
        if subject:
            infos_nodata = self.query(
                ("SELECT I.information_id, I.subject_id, S.codename, "
                 "       I.type, I.name, I.level, I.accuracy, I.valid, "
                 "       I.modified, I.note "
                 "FROM Information I INNER JOIN Subject S "
                 "     ON I.subject_id = S.subject_id "
                 "WHERE I.subject_id = :s "
                 "      AND I.information_id IN"
                 "      (SELECT information_id "
                 "       FROM IK "
                 "       WHERE keyword_id IN"
                 "           (SELECT keyword_id "
                 "            FROM Keyword "
                 "            WHERE keyword IN ("+keywords+")) "
                 "       GROUP BY information_id "
                 "       HAVING COUNT(keyword_id) = :c)"),
                {'s': subject,
                 'c': keywords.count(',')+1})
        else:
            infos_nodata = self.query(
                ("SELECT I.information_id, I.subject_id, S.codename, "
                 "       I.type, I.name, I.level, I.accuracy, I.valid, "
                 "       I.modified, I.note "
                 "FROM Information I INNER JOIN Subject S "
                 "     ON I.subject_id = S.subject_id "
                 "WHERE S.ring_id = :r "
                 "      AND I.information_id IN"
                 "      (SELECT information_id "
                 "       FROM IK "
                 "       WHERE keyword_id IN"
                 "          (SELECT keyword_id "
                 "           FROM Keyword "
                 "           WHERE keyword IN ("+keywords+")) "
                 "       GROUP BY information_id "
                 "       HAVING COUNT(keyword_id) = :c)"),
                {'r': ring,
                 'c': keywords.count(',')+1})

        infos = []
        for info in infos_nodata:
            """ get active/inactive """
            active_times = self.query(("SELECT T.time, A.active "
                                       "FROM Time T INNER JOIN Active A"
                                       "     ON T.time_id = A.time_id "
                                       "WHERE A.information_id = :i "
                                       "ORDER BY T.time"),
                                      {'i': info[0]})
            is_active = False
            for time, active in active_times:
                if lib.datetime_from_str(time) <= ensa.variables['reference_time']:
                    is_active = bool(active)
                else:
                    break
            """ get data """
            if info[3] in [Database.INFORMATION_ALL,
                           Database.INFORMATION_TEXT]:
                value = self.query(("SELECT value "
                                    "FROM Text "
                                    "WHERE information_id = :i"),
                                   {'i': info[0]})[0][0]
                '''
                elif info[3] in [Database.INFORMATION_ALL, 
                                 Database.INFORMATION_BINARY]:
                    value = '[binary]'
                '''
            elif info[3] in [Database.INFORMATION_ALL,
                             Database.INFORMATION_COMPOSITE]:
                value = [row[0] for row in self.query((
                    "SELECT part_id "
                    "FROM Composite "
                    "WHERE information_id = :i"), {'i': info[0]})]
            else:
                value = 'ERROR'
            infos.append(tuple(list(info)+[value]))
        return infos


# # #
ensa.db = Database()
# # #

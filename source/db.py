#!/usr/bin/env python3
import time
import datetime
import os
import sqlite3 as sqlite
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

    def connect(self):
        lib.reload_config()
        """
        try:
            cnx_params = {
                'host': ensa.config['db.host'][0],
                'database': ensa.config['db.name'][0],
                'user': ensa.config['db.username'][0],
                'password': ensa.config['db.password'][0],
            }
            self.cnx = mysql.connector.connect(**cnx_params, autocommit=True)
            self.cur = self.cnx.cursor(prepared=True)
            return True
        except:
            return False
        """
        try:
            self.cnx = sqlite.connect(ensa.config['db.file'][0])
            self.cur = self.cnx.cursor()
            self.query("PRAGMA foreign_keys=ON")
            return True
        except Exception as e:
            print(str(e))
            return False
    
    def query(self, command, parameters=None):
        # TODO lock (because of last insert id)
        log.debug_query(command)
        try:
            #self.cur.execute(command, parameters or tuple())
            self.cur.execute(command, parameters or tuple())
            self.cnx.commit()
        except Exception as e:#mysql.connector.errors.OperationalError:
            print(str(e))
        #    self.connect()
        #    self.cur.execute(command, parameters or tuple())
            
        if command.upper().startswith('SELECT '):
            return self.cur.fetchall()
        return []

    def ring_ok(self):
        if not ensa.current_ring:
            log.err('First select a ring with `rs <name>`.')
            return False
        return True

    def subject_ok(self):
        if not ensa.current_subject:
            log.err('First select a subject with `ss <codename>`.')
            return False
        return True
###########################################
# Ring methods
###########################################
    def get_rings(self, name=None):
        if name:
            return self.query(("SELECT ring_id, name, password, "
                               "       reference_date, note "
                               "FROM Ring "
                               "WHERE name LIKE '%"+name+"%'"))
        return self.query("SELECT ring_id, name, password, reference_date, note "
                          "FROM Ring")

    def create_ring(self, name, password, note):
        try:
            self.query(("INSERT INTO Ring(name, password, reference_date, note) "
                        "VALUES(:n, :p, :d, :note)"), 
                       {'n': name, 
                        'p': password, 
                        'd': 'now', 
                        'note': note})
            return name
        except:
            log.debug_error()
            return ''

    def select_ring(self, name):
        result = self.query(("SELECT ring_id, reference_date "
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

    def set_ring_reference_date(self, reference_date):
        if not self.ring_ok():
            return
        self.query(("UPDATE Ring "
                    "SET reference_date = :d "
                    "WHERE ring_id = :r"), 
                   {'d': reference_date, 
                    'r': ensa.current_ring})

###########################################
# Subject methods
###########################################
    def create_subject(self, codename, note=None):
        if not self.ring_ok():
            return None
        try:
            self.query(("INSERT INTO Subject(ring_id, codename, created, note) "
                        "VALUES(:r, :c, :d, :n)"), 
                       {'r': ensa.current_ring, 
                        'c': codename, 
                        'd': time.strftime('%Y-%m-%d %H:%M:%S'), 
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

    def get_subjects(self, codename=None, sort='codename'):
        if not self.ring_ok():
            return []
        if codename:
            codename_condition = "AND codename like '%" + codename + "%' "
        else:
            codename_condition = " "
        result = self.query(("SELECT subject_id, codename, created, note "
                             "FROM Subject "
                             "WHERE ring_id = :r " + codename_condition + 
                             "ORDER BY :s"), 
                            {'r': ensa.current_ring, 
                             's': sort})
        return result

    def select_subject(self, codename):
        if not self.ring_ok():
            return None
        result = self.query(("SELECT subject_id "
                             "FROM Subject "
                             "WHERE codename = :c "
                             "      AND ring_id = :r"), 
                            {'c': codename, 
                             'r': ensa.current_ring})
        if result:
            return result[0][0]
        log.err('There is no such subject in this ring.')
        return None

    def get_subject_codename(self, subject_id):
        if not self.ring_ok():
            return None
        result = self.query(("SELECT codename "
                             "FROM Subject "
                             "WHERE subject_id = :s "
                             "      AND ring_id = :r"), 
                            {'s': subject_id, 
                             'r': ensa.current_ring})
        if result:
            return result[0][0]
        log.err('There is no such subject in this ring.')
        return None

    def delete_subject(self, subject_id):
        if not self.ring_ok():
            return
        self.query(("DELETE FROM Subject "
                    "WHERE subject_id = :s "
                    "      AND ring_id = :r"), 
                   {'s': subject_id, 
                    'r': ensa.current_ring})
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
                       {'t': Database.INFORMATION_COMPOSITE,})
        if not args or 'keywords' in args:
            self.query(("DELETE FROM Keyword "
                        "WHERE keyword_id NOT IN "
                        "      (SELECT keyword_id FROM IK)"))

    def create_information(self, 
                           info_type, 
                           name, 
                           value, 
                           accuracy=ensa.config['interaction.default_accuracy'][0], 
                           level=None, 
                           valid=True, 
                           note=None):
        if not self.subject_ok():
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
                        'm': time.strftime('%Y-%m-%d %H:%M:%S'), 
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

                '''
                elif info_type == Database.INFORMATION_BINARY:
                    # TODO optional encryption?
                '''

            elif info_type == Database.INFORMATION_COMPOSITE:
                self.query(("INSERT INTO Composite(information_id, part_id) "
                            "SELECT :i, information_id "
                            "FROM Information "
                            "WHERE information_id IN ("+value+") "
                            "      AND subject_id = :s"), 
                           {'i': information_id, 
                            's': ensa.current_subject})
                self.information_cleanup('composites')

            return information_id
        except:
            log.debug_error()
            return None
    
    def add_binary(self, information_id, filename):
        """
        adds binary content to an existing information entry
        """
        """move file from uploads/ to binary/, rename properly"""
        os.rename('files/uploads/%s' % filename, 
                  'files/binary/%d' % information_id)

    def delete_information(self, information_id):
        # test if can delete
        try:
            subject_id, info_type = self.query(("SELECT subject_id, type "
                                                "FROM Information "
                                                "WHERE information_id = :i"), 
                                               {'i': information_id})[0]
            if subject_id != ensa.current_subject:
                raise AttributeError    
        except:
            log.debug_error()
            log.err('That information does not belong to current subject.')
            return 
        self.query(("DELETE FROM Information "
                    "WHERE information_id = :i"), 
                   {'i': information_id})
        if os.path.isfile('files/binary/%d' % information_id):
            os.remove('files/binary/%d' % information_id)
        log.info('Information deleted.')


    def get_informations(self, info_type=None, no_composite_parts=False):
        #if not self.subject_ok():
        #    return []
        if info_type is None:
            info_type = Database.INFORMATION_ALL
        result = []
        if ensa.current_subject:
            if no_composite_parts:
                infos_nodata = self.query((
                    "SELECT I.information_id, I.subject_id, S.codename, "
                    "       I.type, I.name, I.level, I.accuracy, I.valid, "
                    "       I.modified, I.note "
                    "FROM Subject S INNER JOIN Information I "
                    "     ON S.subject_id = I.subject_id "
                    "WHERE I.subject_id = :s "
                    "      AND I.information_id NOT IN "
                    "          (SELECT part_id FROM Composite) "
                    "ORDER BY I.name"), {'s': ensa.current_subject})
            else:
                infos_nodata = self.query((
                    "SELECT I.information_id, I.subject_id, S.codename, "
                    "       I.type, I.name, I.level, I.accuracy, I.valid, "
                    "       I.modified, I.note "
                    "FROM Subject S INNER JOIN Information I "
                    "     ON S.subject_id = I.subject_id "
                    "WHERE I.subject_id = :s "
                    "ORDER BY I.name"), {'s': ensa.current_subject})
        else:
            if no_composite_parts:
                infos_nodata = self.query((
                    "SELECT I.information_id, I.subject_id, S.codename, "
                    "       I.type, I.name, I.level, I.accuracy, I.valid, "
                    "       I.modified, I.note "
                    "FROM Subject S INNER JOIN Information I "
                    "     ON S.subject_id = I.subject_id "
                    "WHERE S.ring_id = :r "
                    "      AND I.information_id NOT IN "
                    "          (SELECT part_id FROM Composite) "
                    "ORDER BY I.name"), {'r': ensa.current_ring})
            else:
                infos_nodata = self.query((
                    "SELECT I.information_id, I.subject_id, S.codename, "
                    "       I.type, I.name, I.level, I.accuracy, I.valid, "
                    "       I.modified, I.note "
                    "FROM Subject S INNER JOIN Information I "
                    "     ON S.subject_id = I.subject_id "
                    "WHERE S.ring_id = :r "
                    "ORDER BY I.name"), {'r': ensa.current_ring})
            

        infos = []
        for info in infos_nodata:
            if info[3] in [Database.INFORMATION_ALL, 
                           Database.INFORMATION_TEXT]:
                value = self.query(("SELECT value "
                                    "FROM Text "
                                    "WHERE information_id = :i"), 
                                   {'i': info[0]})[0][0]
            elif info[3] in [Database.INFORMATION_ALL, 
                             Database.INFORMATION_BINARY]:
                value = '[binary]'
            elif info[3] in [Database.INFORMATION_ALL, 
                             Database.INFORMATION_COMPOSITE]:
                value = '{composite}'
            else:
                value = 'ERROR'
            if (info_type == Database.INFORMATION_ALL 
                    or info_type == info[3]):
                infos.append(tuple(list(info)+[value]))
        return infos
    
    def get_information(self, information_id):
        try:
            info = self.query(
                ("SELECT I.information_id, S.codename, I.type, I.name, "
                 "       I.level, I.accuracy, I.valid, I.note "
                 "FROM Subject S INNER JOIN Information I "
                 "     ON S.subject_id = I.subject_id "
                 "WHERE I.subject_id = :s "
                 "      AND I.information_id = :i"), 
                {'s': ensa.current_subject, 'i': information_id})[0]
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
        elif info[2] in [Database.INFORMATION_ALL, 
                         Database.INFORMATION_BINARY]:
            value = b'[binary]'
        elif info[2] in [Database.INFORMATION_ALL, 
                         Database.INFORMATION_COMPOSITE]:
            value = b' '.join(row[0] for row in self.query((
                "SELECT part_id "
                "FROM Composite "
                "WHERE information_id = :i"), {'i': information_id}))
        else:
            value = b'ERROR'
        return tuple(list(info)+[value])
      

    def update_information(self, **kwargs):
        if not self.subject_ok():
            return
        try:
            args = {k:kwargs[v] for k,v in {
                's': 'subject_id', 
                'n': 'name', 
                'l': 'level', 
                'a': 'accuracy', 
                'v': 'valid', 
                'note': 'note', 
                'i': 'information_id'}.items()}
            args.update({'d': time.strftime('%Y-%m-%d %H:%M:%S')})
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
                            's': ensa.current_subject})
            #elif 'path' in kwargs.keys():# TODO binary
            #elif 'compounds' in kwargs.keys(): # TODO composite without edit support?
        except: 
            log.debug_error()
            log.err("Information update failed.")
    
    
    def update_information_metadata(self, 
                                    information_ids, 
                                    accuracy=None, 
                                    level=None, 
                                    valid=None, 
                                    note=None): 
        if not self.subject_ok():
            return
        if accuracy:
            self.query(("UPDATE Information "
                        "SET modified = :m, accuracy = :a "
                        "WHERE subject_id = :s "
                        "      AND information_id IN ("+information_ids+")"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'a': accuracy, 
                        's': ensa.current_subject})
        elif valid is not None:
            self.query(("UPDATE Information "
                        "SET modified = :m, valid = :v "
                        "WHERE subject_id = :s "
                        "      AND information_id IN ("+information_ids+")"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'v': valid, 
                        's': ensa.current_subject})
        elif note:
            self.query(("UPDATE Information "
                        "SET modified = :m, note = :n "
                        "WHERE subject_id = :s "
                        "      AND information_id IN ("+information_ids+")"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'n': note, 
                        's': ensa.current_subject})
        else: # only level remains
            self.query(("UPDATE Information "
                        "SET modified = :m, level = :l "
                        "WHERE subject_id = :s "
                        "      AND information_id IN ("+information_ids+")"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'l': level, 
                        's': ensa.current_subject})


###########################################
# Location methods
###########################################
    def create_location(self, 
                        name, 
                        lat, 
                        lon, 
                        accuracy=0, 
                        valid=True, 
                        note=None):
        if not self.ring_ok():
            return None
        try:
            gps = 'POINT(%f, %f)' % (lat, lon) if lat and lon else 'NULL'
            print(gps)
            self.query(("INSERT INTO Location(name, gps, accuracy, valid, "
                        "                     ring_id, modified, note) "
                        "VALUES(:n, "+gps+", :a, :v, :r, :m, :note)"), 
                       {'n': name, 
                        'a': accuracy, 
                        'v': valid, 
                        'r': ensa.current_ring, 
                        'm': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'note': note})
            location_id = self.query("SELECT location_id "
                                     "FROM Location "
                                     "ORDER BY location_id DESC LIMIT 1")[0][0]
            return location_id
        except:
            log.debug_error()
            return None
    
    
    def get_locations(self):
        if not self.ring_ok():
            return []
        return self.query(("SELECT location_id, name, ST_AsText(gps), "
                           "       accuracy, valid, modified, note "
                           "FROM Location "
                           "WHERE ring_id = :r"), 
                          {'r': ensa.current_ring})


    def delete_locations(self, location_ids):
        if self.ring_ok():
            self.query(("DELETE FROM Location "
                        "WHERE location_id IN ("+location_ids+") "
                        "      AND ring_id = :r"), 
                       {'r': ensa.current_ring})
    

    def get_location(self, location_id):
        if not self.ring_ok():
            return []
        try:
            info = self.query(("SELECT location_id, name, ST_AsText(gps), "
                               "       accuracy, valid, note "
                               "FROM Location "
                               "WHERE location_id = :l "
                               "      AND ring_id = :r"), 
                              {'l': location_id, 
                               'r': ensa.current_ring})[0]
        except:
            log.err('There is no such location.')
            log.debug_error()
            return []
        return info
    

    def update_location(self, **kwargs):
        if not self.ring_ok():
            return
        try:
            gps = ('POINT(%s, %s)' % (kwargs['lat'], kwargs['lon']) 
                   if kwargs.get('lat') and kwargs.get('lon') 
                   else 'NULL')
            args = {k:kwargs[v] for k,v in {
                'l': 'location_id', 
                'n': 'name', 
                'a': 'accuracy', 
                'v': 'valid', 
                'note': 'note'}.items()}
            args.update({
                'd': time.strftime('%Y-%m-%d %H:%M:%S'),
                'r': ensa.current_ring})

            self.query(("UPDATE Location "
                        "SET modified = :d, name = :n, gps = "+gps+", "
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
                                 note=None):
        if not self.ring_ok():
            return
        if accuracy:
            self.query(("UPDATE Location "
                        "SET modified = :m, accuracy = :a "
                        "WHERE ring_id = :r "
                        "      AND location_id IN ("+location_ids+")"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'a': accuracy, 
                        'r': ensa.current_ring})
        elif valid is not None:
            self.query(("UPDATE Location "
                        "SET modified = :m, valid = :v "
                        "WHERE ring_id = :r "
                        "      AND location_id IN ("+location_ids+")"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'v': valid, 
                        'r': ensa.current_ring})
        elif note:
            self.query(("UPDATE Location "
                        "SET modified = :m, note = :n "
                        "WHERE ring_id = :r "
                        "      AND location_id IN ("+location_ids+")"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'n': note, 
                        'r': ensa.current_ring})
            
###########################################
# Time methods
###########################################
    def create_time(self, d, t, accuracy=0, valid=True, note=None):
        if not self.ring_ok():
            return None
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
        try:
            self.query(("INSERT INTO Time(time, accuracy, valid, ring_id, "
                        "                 modified, note) "
                        "VALUES(:d, :a, :v, :r, :m, :n)"), 
                       {'d': dt, 
                        'a': accuracy, 
                        'v': valid, 
                        'r': ensa.current_ring, 
                        'm': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'n': note})
            time_id = self.query("SELECT time_id "
                                 "FROM Time "
                                 "ORDER BY time_id DESC LIMIT 1")[0][0]
            return time_id
        except:
            log.debug_error()
            return None

    def get_times(self):
        if not self.ring_ok():
            return []
        return self.query(("SELECT time_id, "
                           #"       DATE_FORMAT(time, '%Y-%m-%d %H:%i:%s'), "
                           "       time, "
                           "       accuracy, valid, modified, note "
                           #"       accuracy, valid, note "
                           "FROM Time "
                           "WHERE ring_id = :r"), {'r': ensa.current_ring})

    def delete_times(self, time_ids):
        if not self.ring_ok():
            return []
        self.query(("DELETE FROM Time "
                    "WHERE time_id IN ("+time_ids+") "
                    "      AND ring_id = :r"), {'r': ensa.current_ring})
    

    def get_time(self, time_id):
        if not self.ring_ok():
            return []
        try:
            info = self.query(("SELECT time_id, "
                               "       time"
                               "       accuracy, valid, note "
                               "FROM Time "
                               "WHERE time_id = :t "
                               "      AND ring_id = :r"), 
                              {'t': time_id, 
                               'r': ensa.current_ring})[0]
        except:
            log.err('There is no such time entry.')
            log.debug_error()
            return []
        return info
    

    def update_time(self, **kwargs):
        if not self.ring_ok():
            return []
        try:
            args = {k:kwargs[v] for k,v in {
                't': 'time_id', 
                'd': 'datetime', 
                'a': 'accuracy', 
                'v': 'valid', 
                'note': 'note'}.items()}
            args.update({'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                         'r': ensa.current_ring})
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
                             note=None):
        if not self.ring_ok():
            return []
        if accuracy:
            self.query(("UPDATE Time "
                        "SET modified = :m, accuracy = :a "
                        "WHERE ring_id = :r "
                        "      AND time_id IN ("+time_ids+")"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'a': accuracy, 
                        'r': ensa.current_ring})
        elif valid is not None:
            self.query(("UPDATE Time "
                        "SET modified = :m, valid = :v "
                        "WHERE ring_id = :r "
                        "      AND time_id IN ("+time_ids+")"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'v': valid, 
                        'r': ensa.current_ring})
        elif note:
            self.query(("UPDATE Time "
                        "SET modified = :m, note = :n "
                        "WHERE ring_id = :r "
                        "      AND time_id IN ("+time_ids+")"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'n': note, 
                        'r': ensa.current_ring})

###########################################
# Association methods
###########################################
    def create_association(self, level=None, accuracy=0, valid=True, note=None):
        if not self.ring_ok():
            return None
        try:
            self.query(("INSERT INTO Association(ring_id, level, accuracy, "
                        "                        valid, modified, note) "
                        "VALUES(:r, :l, :a, :v, :m, :n)"), 
                       {'r': ensa.current_ring, 
                       'l': level, 
                       'a': accuracy, 
                       'v': valid, 
                       'm': time.strftime('%Y-%m-%d %H:%M:%S'), 
                       'n': note})
            association_id = self.query("SELECT association_id "
                                        "FROM Association "
                                        "ORDER BY association_id DESC "
                                        "LIMIT 1")[0][0]
            return association_id
        except:
            log.debug_error()
            return None

    def associate_association(self, association_id, association_ids):
        if not self.ring_ok():
            return None
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
            if ring_id != ensa.current_ring:
                raise AttributeError
        except:
            log.err('All associations must belong to current ring.')
            return None
        try:
            count_before = self.query("SELECT COUNT(*) FROM AA")[0][0]
            self.query(("INSERT INTO AA(association_id_1, association_id_2) "
                        "SELECT :a, association_id "
                        "FROM Association "
                        "WHERE association_id IN ("+ association_ids +") "
                        "      AND ring_id = :r"), 
                       {'a': association_id, 
                        'r': ensa.current_ring})
            count_after = self.query("SELECT COUNT(*) FROM AA")[0][0]
            if count_before == count_after:
                log.err('Association must belong to current ring.')
                return None
            self.query(("UPDATE Association "
                        "SET modified = :m "
                        "WHERE association_id = :a"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'a': association_id})
            return tuple([(association_id, a) 
                          for a in association_ids.split(',')])
        except:
            log.debug_error()
            log.err('Failed to associate association.')
            return None


    def associate_information(self, association_id, information_ids):
        if not self.ring_ok():
            return None
        try:
            ring_id = self.query(("SELECT ring_id "
                                  "FROM Association "
                                  "WHERE association_id = :a"), 
                                 {'a': association_id})[0][0]
            if ring_id != ensa.current_ring:
                raise AttributeError
        except:
            log.err('Current ring has no such asssociation.')
            return None
        try:
            count_before = self.query("SELECT COUNT(*) FROM AI")[0][0]
            self.query(("INSERT INTO AI(association_id, information_id) "
                        "SELECT :a, information_id "
                        "FROM Information "
                        "WHERE information_id IN ("+ information_ids +") "
                        "      AND subject_id IN "
                        "          (SELECT subject_id "
                        "           FROM Subject "
                        "         WHERE ring_id = :r)"), 
                       {'a': association_id, 
                        'r': ensa.current_ring})
            count_after = self.query("SELECT COUNT(*) FROM AI")[0][0]
            if count_before == count_after:
                log.err('Information must belong to current ring.')
                return None
            self.query(("UPDATE Association "
                        "SET modified = :m "
                        "WHERE association_id = :a"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'a': association_id})
            return tuple([(association_id, i) for i in information_ids])
        except:
            log.err('Failed to associate information.')
            return None


    def associate_location(self, association_id, location_ids):
        if not self.ring_ok():
            return None
        try:
            ring_id = self.query(("SELECT ring_id "
                                  "FROM Association "
                                  "WHERE association_id = :a"), 
                                 {'a': association_id})[0][0]
            if ring_id != ensa.current_ring:
                raise AttributeError
        except:
            log.err('Current ring has no such asssociation.')
            return None
        try:
            count_before = self.query("SELECT COUNT(*) FROM AL")[0][0]
            self.query(("INSERT INTO AL(association_id, location_id) "
                        "SELECT :a, location_id "
                        "FROM Location "
                        "WHERE location_id IN ("+ location_ids +") "
                        "      AND ring_id = :r"), 
                       {'a': association_id, 
                        'r': ensa.current_ring})
            count_after = self.query("SELECT COUNT(*) FROM AL")[0][0]
            if count_before == count_after:
                log.err('Location must belong to current ring.')
                return None
            self.query(("UPDATE Association "
                        "SET modified = :m "
                        "WHERE association_id = :a"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'a': association_id})
            return tuple([(association_id, l) for l in location_ids])
        except:
            log.debug_error()
            log.err('Failed to associate location.')
            return None
    
    
    def associate_subject(self, association_id, codenames):
        if not self.ring_ok():
            return None
        try:
            ring_id = self.query(("SELECT ring_id "
                                  "FROM Association "
                                  "WHERE association_id = :a"), 
                                 {'a': association_id})[0][0]
            if ring_id != ensa.current_ring:
                raise AttributeError
        except:
            log.err('Current ring has no such asssociation.')
            return None
        try:
            count_before = self.query("SELECT COUNT(*) FROM AI")[0][0]
            self.query(("INSERT INTO AI(association_id, information_id) "
                        "SELECT :a, I.information_id "
                        "FROM Subject S INNER JOIN Information I "
                        "     ON S.subject_id = I.subject_id "
                        "WHERE I.name = 'codename' "
                        "      AND S.codename IN ("+ codenames +") "
                        "      AND S.ring_id = :r"), 
                       {'a': association_id, 'r': ensa.current_ring})
            count_after = self.query("SELECT COUNT(*) FROM AI")[0][0]
            if count_before == count_after:
                log.err('Subject must belong to current ring.')
                return None
            self.query(("UPDATE Association "
                        "SET modified = :m "
                        "WHERE association_id = :a"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'a': association_id})
            return tuple([(association_id, codename) 
                          for codename in codenames.split(',')])
        except:
            log.debug_error()
            log.err('Failed to associate subject.')
            return None


    def associate_time(self, association_id, time_ids):
        if not self.ring_ok():
            return None
        try:
            ring_id = self.query(("SELECT ring_id "
                                  "FROM Association "
                                  "WHERE association_id = :a"), 
                                 {'a': association_id})[0][0]
            if ring_id != ensa.current_ring:
                raise AttributeError
        except:
            log.err('Current ring has no such asssociation.')
            return None
        try:
            count_before = self.query("SELECT COUNT(*) FROM AT")[0][0]
            self.query(("INSERT INTO AT(association_id, time_id) "
                        "SELECT :a, time_id "
                        "FROM Time "
                        "WHERE time_id IN ("+ time_ids +") "
                        "      AND ring_id = :r"), 
                       {'a': association_id, 
                        'r': ensa.current_ring})
            count_after = self.query("SELECT COUNT(*) FROM AT")[0][0]
            if count_before == count_after:
                log.err('Time must belong to current ring.')
                return None
            self.query(("UPDATE Association "
                        "SET modified = :m "
                        "WHERE association_id = :r"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'a': association_id})
            return tuple([(association_id, t) for t in time_ids])
        except:
            log.debug_error()
            log.err('Failed to associate time.')
            return None

    def get_associations(self):
        if not self.ring_ok():
            return []
        # get associations
        return self.query(("SELECT association_id, ring_id, level, accuracy, "
                           "       valid, modified, note "
                           "FROM Association "
                           "WHERE ring_id = :r"), 
                          {'r': ensa.current_ring})

    def get_associations_by_X(self, query, query_args=None):
        if not self.ring_ok():
            return []
        # get associations
        associations = self.query(query, query_args)

        result = []
        for assoc in associations:
            # in current ring?
            if assoc[1] != ensa.current_ring:
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
                if info[3] == Database.INFORMATION_TEXT:
                    value = self.query(("SELECT value "
                                        "FROM Text "
                                        "WHERE information_id = :i"), 
                                       {'i': info[0]})[0][0]
                elif info[3] == Database.INFORMATION_BINARY:
                    value = '[binary]'
                elif info[3] == Database.INFORMATION_COMPOSITE:
                    value = '{composite}'
                else:
                    value = 'ERROR'
                infos.append(tuple(list(info)+[value]))
            # get time entries
            times = self.query(("SELECT Time.time_id, "
                                "       DATE_FORMAT(time, '%Y-%m-%d %H:%i:%s'),"
                                "       accuracy, valid, modified, note "
                                "FROM Time INNER JOIN AT "
                                "     ON Time.time_id = AT.time_id "
                                "WHERE AT.association_id = :a"), 
                               {'a': assoc[0]}) or []
            # get location entries
            locations = self.query(("SELECT L.location_id, name, "
                                    "       ST_AsText(gps), accuracy, valid, "
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


    def get_associations_by_ids(self, association_ids):
        query = ("SELECT association_id, ring_id, level, accuracy, "
                 "       valid, modified, note "
                 "FROM Association "
                 "WHERE association_id IN("+association_ids+")")
        return self.get_associations_by_X(query)

    def get_associations_by_note(self, string):
        query = ("SELECT association_id, ring_id, level, accuracy, "
                 "       valid, modified, note "
                 "FROM Association "
                 "WHERE note LIKE '%"+string+"%'")
        return self.get_associations_by_X(query)

    def get_associations_by_location(self, location_ids):
        query = ("SELECT A.association_id, ring_id, level, accuracy, "
                 "       valid, modified, note "
                 "FROM Association A INNER JOIN AL "
                 "     ON A.association_id = AL.association_id "
                 "WHERE location_id IN("+location_ids+")")
        return self.get_associations_by_X(query)

    def get_associations_by_time(self, time_ids):
        query = ("SELECT A.association_id, ring_id, level, accuracy, "
                 "       valid, modified, note "
                 "FROM Association A INNER JOIN AT "
                 "     ON A.association_id = AT.association_id "
                 "WHERE time_id IN("+time_ids+")")
        return self.get_associations_by_X(query)
    
    def get_associations_by_information(self, information_ids):
        query = ("SELECT A.association_id, ring_id, level, accuracy, "
                 "       valid, modified, note "
                 "FROM Association A INNER JOIN AI "
                 "     ON A.association_id = AI.association_id "
                 "WHERE information_id IN("+information_ids+")")
        return self.get_associations_by_X(query)
    
    def get_associations_by_subject(self, codenames):
        query = ("SELECT A.association_id, A.ring_id, A.level, A.accuracy, "
                 "       A.valid, A.modified, A.note "
                 "FROM Association A "
                 "     INNER JOIN AI "
                 "         ON A.association_id = AI.association_id "
                 "     INNER JOIN Information I "
                 "         ON AI.information_id = I.information_id "
                 "     INNER JOIN Subject S "
                 "         ON I.subject_id = S.subject_id "
                 "WHERE S.codename IN("+codenames+")")
        return self.get_associations_by_X(query)


    def get_timeline_by_location(self, location_ids):
        query = ("SELECT A.association_id, A.ring_id, A.level, A.accuracy, "
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
        return self.get_associations_by_X(query)

    def get_timeline_by_information(self, information_ids):
        query = ("SELECT A.association_id, A.ring_id, A.level, A.accuracy, "
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
        return self.get_associations_by_X(query)

    def get_timeline_by_subject(self, codenames):
        query = ("SELECT A.association_id, A.ring_id, A.level, A.accuracy, "
                 "       A.valid, A.modified, A.note"
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
                 "WHERE S.codename IN("+codenames+") "
                 "ORDER BY T.time")
        return self.get_associations_by_X(query)

    def get_timeline_by_range(self, start, end):
        query = ("SELECT A.association_id, A.ring_id, A.level, A.accuracy, "
                 "       A.valid, A.modified, A.note "
                 "FROM Association A "
                 "     INNER JOIN AT "
                 "         ON A.association_id = AT.association_id "
                 "     INNER JOIN Time T "
                 "         ON T.time_id = AT.time_id "
                 "WHERE T.time BETWEEN :s AND :e "
                 "ORDER BY T.time")
        return self.get_associations_by_X(query, {'s': start, 'e': end})


    def delete_associations(self, association_ids):
        if not self.ring_ok():
            return
        self.query(("DELETE FROM Association "
                    "WHERE association_id IN ("+association_ids+") "
                    "      AND ring_id = :r"), 
                   {'r': ensa.current_ring})


    def dissociate_associations(self, association_id, association_ids):
        if not self.ring_ok():
            return
        self.query(("DELETE FROM AA "
                    "WHERE association_id_1 IN "
                    "    (SELECT association_id "
                    "     FROM Association "
                    "     WHERE association_id = :a "
                    "           AND ring_id = :r) "
                    "    AND association_id_2 IN ("+association_ids+")"), 
                   {'a': association_id, 
                    'r': ensa.current_ring})
        self.query(("UPDATE Association "
                    "SET modified = :m "
                    "WHERE association_id = :a "
                    "      AND ring_id = :r"), 
                   {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                    'a': association_id, 
                    'r': ensa.current_ring})

    
    def dissociate_informations(self, association_id, information_ids):
        if not self.ring_ok():
            return
        self.query(("DELETE FROM AI "
                    "WHERE association_id IN "
                    "    (SELECT association_id "
                    "     FROM Association "
                    "     WHERE association_id = :a "
                    "           AND ring_id = :r) "
                    "    AND information_id IN ("+information_ids+")"), 
                   {'a': association_id, 
                    'r': ensa.current_ring})
        self.query(("UPDATE Association "
                    "SET modified = :m "
                    "WHERE association_id = :a "
                    "      AND ring_id = :r"), 
                   {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                    'a': association_id, 
                    'r': ensa.current_ring})
     
    
    def dissociate_locations(self, association_id, location_ids):
        if not self.ring_ok():
            return []
        self.query(("DELETE FROM AL "
                    "WHERE association_id IN "
                    "    (SELECT association_id "
                    "     FROM Association "
                    "     WHERE association_id = :a "
                    "           AND ring_id = :r) "
                    "    AND location_id IN ("+location_ids+")"), 
                   {'a': association_id, 
                    'r': ensa.current_ring})
        self.query(("UPDATE Association "
                    "SET modified = :m "
                    "WHERE association_id = :a "
                    "      AND ring_id = :r"), 
                   {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                    'a': association_id, 
                    'r': ensa.current_ring})
  

    def dissociate_times(self, association_id, time_ids):
        if not self.ring_ok():
            return []
        self.query(("DELETE FROM AT "
                    "WHERE association_id IN "
                    "    (SELECT association_id "
                    "     FROM Association "
                    "     WHERE association_id = :a "
                    "           AND ring_id = :r) "
                    "    AND time_id IN ("+time_ids+")"), 
                   {'a': association_id, 
                    'r': ensa.current_ring})
        self.query(("UPDATE Association "
                    "SET modified = :m "
                    "WHERE association_id = :a "
                    "      AND ring_id = :r"), 
                   {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                    'a': association_id, 
                    'r': ensa.current_ring})


    def get_association(self, association_id):
        if not self.ring_ok():
            return []
        try:
            info = self.query(("SELECT association_id, level, accuracy, "
                               "       valid, note "
                               "FROM Association "
                               "WHERE association_id = :a "
                               "      AND ring_id = :r"), 
                              {'a': association_id, 
                               'r': ensa.current_ring})[0]
        except:
            log.err('There is no such association.')
            log.debug_error()
            return []
        return info
    

    def update_association(self, **kwargs):
        if not self.ring_ok():
            return []
        try:
            args = {k:kwargs[v] for k,v in {
                'as': 'association_id', 
                'd': 'datetime', 
                'a': 'accuracy', 
                'v': 'valid', 
                'note': 'note'}.items()}
            args.update({
                'm': time.strftime('%Y-%m-%d %H:%M:%S'), 
                'r': ensa.current_ring})
            self.query(("UPDATE Association "
                        "SET modified = :m, level = :l, accuracy = :a, "
                        "    valid = :v, note = :n "
                        "WHERE association_id = :as "
                        "      AND ring_id = :r", args))
        except: 
            log.debug_error()
            log.err("Association update failed.")
    
    
    def update_association_metadata(self, 
                                    association_ids, 
                                    accuracy=None, 
                                    level=None, 
                                    valid=None, 
                                    note=None): 
        if not self.ring_ok():
            return []
        if accuracy:
            self.query(("UPDATE Association "
                        "SET modified = :m, accuracy = :a "
                        "WHERE ring_id = :r "
                        "      AND association_id IN ("+association_ids+")"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'a': accuracy, 
                        'r': ensa.current_ring})
        elif valid is not None:
            self.query(("UPDATE Association "
                        "SET modified = :m, valid = :v "
                        "WHERE ring_id = :r "
                        "      AND association_id IN ("+association_ids+")"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'v': valid, 
                        'r': ensa.current_ring})
        elif note:
            self.query(("UPDATE Association "
                        "SET modified = :m, note = :n "
                        "WHERE ring_id = :r "
                        "      AND association_id IN ("+association_ids+")"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'n': note,
                        'r': ensa.current_ring})
        else: # only level remains
            self.query(("UPDATE Association "
                        "SET modified = :m, level = :l "
                        "WHERE ring_id = :r "
                        "      AND association_id IN ("+association_ids+")"), 
                       {'m': time.strftime('%Y-%m-%d %H:%M:%S'), 
                        'l': level, 
                        'r': ensa.current_ring})
            
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


    def add_keyword(self, information_ids, keyword):
        if not self.subject_ok():
            return
        if type(information_ids) == int:
            information_ids = str(information_ids)
        elif type(information_ids) in (tuple, list):
            information_ids = ','.join(information_ids)
        keyword_id = self.get_keyword_id(keyword)
        self.query(("INSERT INTO IK(information_id, keyword_id) "
                    "SELECT information_id, :k "
                    "FROM Information "
                    "WHERE subject_id = :s "
                    "      AND information_id IN ("+information_ids+")"), 
                   {'k': keyword_id, 
                    's': ensa.current_subject})


    def delete_keywords(self, information_ids, keywords):
        if not self.subject_ok():
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
                        "           WHERE information_id IN("+information_ids+")" 
                        "                 AND subject_id = :s)"), 
                       {'s': ensa.current_subject})
        else: # delete all keywords
            self.query(("DELETE FROM IK "
                        "WHERE information_id IN "
                        "      (SELECT information_id "
                        "       FROM Information "
                        "       WHERE information_id IN("+information_ids+")"
                        "       AND subject_id = :s)"), 
                       {'s': ensa.current_subject})
        self.information_cleanup('keywords')
            

    def get_keywords(self):
        if not self.ring_ok():
            return []
        if ensa.current_subject:
            result = self.query(("SELECT DISTINCT K.keyword "
                                 "FROM Keyword K "
                                 "    INNER JOIN IK "
                                 "     ON K.keyword_id = IK.keyword_id "
                                 "    INNER JOIN Information I "
                                 "     ON IK.information_id = I.information_id "
                                 "WHERE I.subject_id = :s "
                                 "ORDER BY K.keyword"), 
                                {'s': ensa.current_subject})
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
                                {'r': ensa.current_ring})
        return result

    def get_keywords_for_informations(self, information_ids):
        if not self.subject_ok():
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
                            {'s': ensa.current_subject})
        return result
   

    def get_informations_for_keywords_or(self, keywords):
        if not self.ring_ok():
            return []
        if ensa.current_subject:
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
                                      {'s': ensa.current_subject})
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
                                      {'r': ensa.current_ring})
        infos = []
        for info in infos_nodata:
            if info[3] in [Database.INFORMATION_ALL, 
                           Database.INFORMATION_TEXT]:
                value = self.query(("SELECT value "
                                    "FROM Text "
                                    "WHERE information_id = :i"), 
                                   {'i': info[0]})[0][0]
            elif info[3] in [Database.INFORMATION_ALL, 
                             Database.INFORMATION_BINARY]:
                value = '[binary]'
            elif info[3] in [Database.INFORMATION_ALL, 
                             Database.INFORMATION_COMPOSITE]:
                value = '{composite}'
            else:
                value = 'ERROR'
            infos.append(tuple(list(info)+[value]))
        return infos


    def get_informations_for_keywords_and(self, keywords):
        if not self.ring_ok():
            return []
        if ensa.current_subject:
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
                {'s': ensa.current_subject, 
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
                {'r': ensa.current_ring, 
                 'c': keywords.count(',')+1})

        infos = []
        for info in infos_nodata:
            if info[3] in [Database.INFORMATION_ALL, 
                           Database.INFORMATION_TEXT]:
                value = self.query(("SELECT value "
                                    "FROM Text "
                                    "WHERE information_id = :i"), 
                                   {'i': info[0]})[0][0]
            elif info[3] in [Database.INFORMATION_ALL, 
                             Database.INFORMATION_BINARY]:
                value = '[binary]'
            elif info[3] in [Database.INFORMATION_ALL, 
                             Database.INFORMATION_COMPOSITE]:
                value = '{composite}'
            else:
                value = 'ERROR'
            infos.append(tuple(list(info)+[value]))
        return infos


# # #
ensa.db = Database()
# # #



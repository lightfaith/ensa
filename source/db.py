#!/usr/bin/env python3
import time, datetime, traceback
import mysql.connector
from source import log
from source import ensa
from source import lib


class Database():
    pass

class Database():
    INFORMATION_ALL = -1
    INFORMATION_TEXT = 0
    INFORMATION_BINARY = 1
    INFORMATION_COMPOSITE = 2

    def __init__(self):
        pass

    def connect(self):
        lib.reload_config()
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
    
    def query(self, command, parameters=None):
        # TODO lock (because of last insert id)
        #print(command)
        try:
            self.cur.execute(command, parameters or tuple())
        except mysql.connector.errors.OperationalError:
            self.connect()
            self.cur.execute(command, parameters or tuple())
            
        if command.upper().startswith('SELECT '):
            return self.cur.fetchall()
        return []

###########################################
# Ring methods
###########################################
    def get_rings(self):
        return self.query("SELECT ring_id, name, password, note FROM Ring")

    def create_ring(self, name, password, note):
        try:
            self.query("INSERT INTO Ring(name, password, note) VALUES(%s, %s, %s)", (name, password, note))
            return True
        except:
            traceback.print_exc()
            return False

    def select_ring(self, name):
        result = self.query("SELECT ring_id FROM Ring WHERE name = %s", (name,))
        if result:
            return result[0][0]
        log.err('There is no such ring.')
        return None

    def get_ring_name(self, ring_id):
        result = self.query("SELECT name FROM Ring WHERE ring_id = %s", (ring_id,))
        if result:
            return result[0][0]
        log.err('There is no such ring.')
        return None

###########################################
# Subject methods
###########################################
    def create_subject(self, codename, note=None):
        if not ensa.current_ring:
            log.err('First select a ring with `rs <name>`.')
            return None
        try:
            self.query("INSERT INTO Subject(ring_id, codename, created, note) VALUES(%s, %s, %s, %s)", (ensa.current_ring, codename, time.strftime('%Y-%m-%d %H:%M:%S'), note))
            #subject_id = self.query("SELECT LAST_INSERT_ID()")[0][0]
            subject_id = self.query("SELECT subject_id FROM Subject LIMIT 1")[0][0]
            if not subject_id:
                log.err('Cannot retrieve the new subject ID.')
                return None
            self.create_information(Database.INFORMATION_TEXT, 'codename', codename, accuracy=10, level=None, valid=True, note=None)
            return subject_id
        except:
            traceback.print_exc()
            return None

    def get_subjects(self, sort='codename'):
        if not ensa.current_ring:
            log.err('First select a ring with `rs <name>`.')
            return []
        result = self.query("SELECT subject_id, codename, created, note FROM Subject WHERE ring_id = %s ORDER BY %s", (ensa.current_ring, sort))
        return result

    def select_subject(self, codename):
        if not ensa.current_ring:
            log.err('First select a ring with `rs <name>`.')
            return None
        result = self.query("SELECT subject_id FROM Subject WHERE codename = %s AND ring_id = %s", (codename, ensa.current_ring))
        if result:
            return result[0][0]
        log.err('There is no such subject in this ring.')
        return None

    def get_subject_codename(self, subject_id):
        if not ensa.current_ring:
            log.err('First select a ring with `rs <name>`.')
            return None
        result = self.query("SELECT codename FROM Subject WHERE subject_id = %s AND ring_id = %s", (subject_id, ensa.current_ring))
        if result:
            return result[0][0]
        log.err('There is no such subject in this ring.')
        return None

        
###########################################
# Information methods
###########################################
    def information_cleanup(self, *args):
        if not args or 'composites' in args:
            self.query("DELETE FROM Information WHERE type = %s AND information_id NOT IN (SELECT information_id FROM Composite)", (Database.INFORMATION_COMPOSITE,))
        #if not args or 'relationships' in args:
        #    self.query("DELETE FROM Information WHERE type = %s AND information_id NOT IN (SELECT information_id FROM Relationship)", (Database.INFORMATION_RELATIONSHIP,))

    def create_information(self, info_type, name, value, accuracy=0, level=None, valid=True, note=None):
        if not ensa.current_subject:
            log.err('First select a subject with `ss <codename>`.')
            return None
        try:
            self.query("INSERT INTO Information(subject_id, type, name, accuracy, level, valid, modified, note) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)", (ensa.current_subject, info_type, name, accuracy, level, valid, time.strftime('%Y-%m-%d %H:%M:%S'), note))
            #information_id = self.query("SELECT LAST_INSERT_ID()")[0][0]
            information_id = self.query("SELECT information_id from Information LIMIT 1")[0][0]


            if info_type == Database.INFORMATION_TEXT:
                self.query("INSERT INTO Text(information_id, value) VALUES(%s, %s)", (information_id, value))


            #elif info_type == Database.INFORMATION_BINARY: # TODO file upload, path alteration
            #    self.query("INSERT INTO Bin(information_id, path) VALUES(%s, %s)", (information_id, value))


            elif info_type == Database.INFORMATION_COMPOSITE:
                ## check if all parts exist
                #available = [str(x[0]) for x in self.query("SELECT information_id FROM Information WHERE subject_id = %s", (ensa.current_subject,))]
                #for part in value:
                #    if part in available:
                #
                self.query("INSERT INTO Composite(information_id, part_id) SELECT %s, information_id FROM Information WHERE information_id IN ("+value+") AND subject_id = %s", (information_id, ensa.current_subject))
                #    else:
                #        log.err('Information #%s does not belong to current subject.' % (part))
                # clean composites without parts
                self.information_cleanup('composites')


            """elif info_type == Database.INFORMATION_RELATIONSHIP:
                # TODO try suggest reverse relationship
                try:
                    peer_id = self.select_subject(value)
                    if not peer_id:
                        raise AttributeError
                    self.query("INSERT INTO Relationship(information_id, subject_id) VALUES(%s, %s)", (information_id, peer_id))
                except:
                    log.err("No such peer exists in current ring.")
                # clean relationships without subjects
                self.information_cleanup('relationships')"""

            return information_id
        except:
            traceback.print_exc()
            return None
    

    def delete_information(self, information_id):
        # test if can delete
        try:
            subject_id, info_type = self.query("SELECT subject_id, type FROM Information WHERE information_id = %s", (information_id,))[0]
            if subject_id != ensa.current_subject:
                raise AttributeError    
        except:
            traceback.print_exc()
            log.err('That information does not belong to current subject.')
            return 
        # delete actual data
        if info_type == Database.INFORMATION_TEXT:
            self.query("DELETE FROM Text WHERE information_id = %s", (information_id,))
        #elif info_type == Database.INFORMATION_BINARY:
        #    self.query("DELETE FROM Bin WHERE information_id = %s", (information_id,))
        elif info_type == Database.INFORMATION_COMPOSITE:
            self.query("DELETE FROM Composite WHERE information_id = %s OR part_id = %s", (information_id, information_id))
        #elif info_type == Database.INFORMATION_RELATIONSHIP:
        #    self.query("DELETE FROM Relationship WHERE information_id = %s", (information_id,))
        # TODO delete tag links
        # TODO delete references
        # delete information metadata
        self.query("DELETE FROM Information WHERE information_id = %s", (information_id,))
        log.info('Information deleted.')


    def get_information(self, info_type=None, no_composite_parts=False):
        if not ensa.current_subject:
            log.err('First select a subject with `ss <codename>`.')
            return None
        if info_type is None:
            info_type = Database.INFORMATION_ALL
        result = []

        if info_type in [Database.INFORMATION_ALL, Database.INFORMATION_TEXT]:
            if no_composite_parts:
                q = "SELECT i.*, v.value FROM Information i INNER JOIN Text v ON i.information_id = v.information_id WHERE i.subject_id = %s AND v.information_id NOT IN (SELECT part_id FROM Composite) ORDER BY i.name"
            else:
                q = "SELECT i.*, v.value FROM Information i INNER JOIN Text v ON i.information_id = v.information_id WHERE i.subject_id = %s ORDER BY i.name"
            result += self.query(q, (ensa.current_subject,))
        
        
        if info_type in [Database.INFORMATION_ALL, Database.INFORMATION_BINARY]:
            result += self.query("SELECT *, '[binary]' FROM Information WHERE subject_id = %s ORDER BY name", (ensa.current_subject,))
        
        
        if info_type in [Database.INFORMATION_ALL, Database.INFORMATION_COMPOSITE]:
            result += self.query("SELECT i.*, v.part_id FROM Information i INNER JOIN Composite v ON i.information_id = v.information_id WHERE i.subject_id = %s ORDER BY i.name", (ensa.current_subject,))
        
        
        """if info_type in [Database.INFORMATION_ALL, Database.INFORMATION_RELATIONSHIP]:
            result += self.query("SELECT i.*, v.subject_id FROM Information i INNER JOIN Relationship v ON i.information_id = v.information_id WHERE i.subject_id = %s ORDER BY i.name", (ensa.current_subject,))"""
        return result


###########################################
# Location methods
###########################################
    def create_location(self, name, lat, lon, accuracy=0, valid=True, note=None):
        if not ensa.current_ring:
            log.err('First select a ring with `rs <name>`.')
            return None
        try:
            gps = 'POINT(%f %f)' % (lat, lon) if lat and lon else 'NULL'
            self.query("INSERT INTO Location(name, gps, accuracy, valid, ring_id, note) VALUES(%s, "+gps+", %s, %s, %s, %s)", (name, accuracy, valid, ensa.current_ring, note))
            location_id = self.query("SELECT location_id from Location LIMIT 1")[0][0]
            return location_id
        except:
            traceback.print_exc()
            return None

###########################################
# Time methods
###########################################
    def create_time(self, date, time, accuracy=0, valid=True, note=None):
        if not ensa.current_ring:
            log.err('First select a ring with `rs <name>`.')
            return None
        try:
            datetime.datetime.strptime(date, '%Y-%m-%d')
        except:
            date = '0000-00-00'
        try:
            datetime.datetime.strptime(time, '%H:%M:%S')
        except:
            try:
                datetime.datetime.strptime(time, '%H:%M')
            except:
                time = '00:00:00'
        dt = '%s %s' % (date, time)
        try:
            self.query("INSERT INTO Time(time, accuracy, valid, ring_id, note) VALUES(%s, %s, %s, %s, %s)", (dt, accuracy, valid, ensa.current_ring, note))
            time_id = self.query("SELECT time_id from Time LIMIT 1")[0][0]
            return time_id # TODO wrong value
        except:
            traceback.print_exc()
            return None

###########################################
# Association methods
###########################################
    def create_association(self, level=None, accuracy=0, valid=True, note=None):
        if not ensa.current_ring:
            log.err('First select a ring with `rs <name>`.')
            return None
        try:
            self.query("INSERT INTO Association(ring_id, level, accuracy, valid, note) VALUES(%s, %s, %s, %s, %s)", (ensa.current_ring, level, accuracy, valid, note))
            association_id = self.query("SELECT association_id from Association LIMIT 1")[0][0]
            return association_id
        except:
            traceback.print_exc()
            return None

    def associate_information(self, association_id, information_ids):
        if not ensa.current_ring:
            log.err('First select a ring with `rs <name>`.')
            return None
        try:
            ring_id = self.query("SELECT ring_id FROM Association WHERE association_id = %s", (association_id,))[0][0]
            if ring_id != ensa.current_ring:
                raise AttributeError
        except:
            log.err('Current ring has no such asssociation.')
            return None
        try:
            self.query("INSERT INTO AI(association_id, information_id) SELECT %s, information_id FROM Information WHERE information_id IN (SELECT "+ information_ids +") AND subject_id IN (SELECT subject_id FROM Subject WHERE ring_id = %s)", (association_id, ensa.current_ring))
            return tuple([(association_id, i) for i in information_ids])
        except:
            log.err('Failed to associate information.')
            return None

        
# # #
ensa.db = Database()
# # #

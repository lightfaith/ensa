#!/usr/bin/env python3
import time, datetime
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
        log.debug_query(command)
        try:
            self.cur.execute(command, parameters or tuple())
        except mysql.connector.errors.OperationalError:
            self.connect()
            self.cur.execute(command, parameters or tuple())
            
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
    def get_rings(self):
        return self.query("SELECT ring_id, name, password, note FROM Ring")

    def create_ring(self, name, password, note):
        try:
            self.query("INSERT INTO Ring(name, password, note) VALUES(%s, %s, %s)", (name, password, note))
            return True
        except:
            log.debug_error()
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

    def delete_ring(self, ring_id):
        self.query("DELETE FROM Ring WHERE ring_id = %s", (ring_id,))

###########################################
# Subject methods
###########################################
    def create_subject(self, codename, note=None):
        if not self.ring_ok():
            return None
        try:
            self.query("INSERT INTO Subject(ring_id, codename, created, note) VALUES(%s, %s, %s, %s)", (ensa.current_ring, codename, time.strftime('%Y-%m-%d %H:%M:%S'), note))
            #subject_id = self.query("SELECT LAST_INSERT_ID()")[0][0]
            subject_id = self.query("SELECT subject_id FROM Subject ORDER BY subject_id DESC LIMIT 1")[0][0]
            if not subject_id:
                log.err('Cannot retrieve the new subject ID.')
                return None
            ensa.current_subject = subject_id
            self.create_information(Database.INFORMATION_TEXT, 'codename', codename, accuracy=10, level=None, valid=True, note=None)
            return subject_id
        except:
            log.debug_error()
            return None

    def get_subjects(self, sort='codename'):
        if not self.ring_ok():
            return []
        result = self.query("SELECT subject_id, codename, created, note FROM Subject WHERE ring_id = %s ORDER BY %s", (ensa.current_ring, sort))
        return result

    def select_subject(self, codename):
        if not self.ring_ok():
            return None
        result = self.query("SELECT subject_id FROM Subject WHERE codename = %s AND ring_id = %s", (codename, ensa.current_ring))
        if result:
            return result[0][0]
        log.err('There is no such subject in this ring.')
        return None

    def get_subject_codename(self, subject_id):
        if not self.ring_ok():
            return None
        result = self.query("SELECT codename FROM Subject WHERE subject_id = %s AND ring_id = %s", (subject_id, ensa.current_ring))
        if result:
            return result[0][0]
        log.err('There is no such subject in this ring.')
        return None

    def delete_subject(self, subject_id):
        if not self.ring_ok():
            return None
        self.query("DELETE FROM Subject WHERE subject_id = %s AND ring_id = %s", (subject_id,ensa.current_ring))
###########################################
# Information methods
###########################################
    def information_cleanup(self, *args):
        if not args or 'composites' in args:
            self.query("DELETE FROM Information WHERE type = %s AND information_id NOT IN (SELECT information_id FROM Composite)", (Database.INFORMATION_COMPOSITE,))
        if not args or 'keywords' in args:
            self.query("DELETE FROM Keyword WHERE keyword_id NOT IN (SELECT keyword_id FROM IK)")

    def create_information(self, info_type, name, value, accuracy=0, level=None, valid=True, note=None):
        if not self.subject_ok():
            return None
        try:
            self.query("INSERT INTO Information(subject_id, type, name, accuracy, level, valid, modified, note) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)", (ensa.current_subject, info_type, name, accuracy, level, valid, time.strftime('%Y-%m-%d %H:%M:%S'), note))
            #information_id = self.query("SELECT LAST_INSERT_ID()")[0][0]
            information_id = self.query("SELECT information_id from Information ORDER BY information_id DESC LIMIT 1")[0][0]


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

            return information_id
        except:
            log.debug_error()
            return None
    

    def delete_information(self, information_id):
        # test if can delete
        try:
            subject_id, info_type = self.query("SELECT subject_id, type FROM Information WHERE information_id = %s", (information_id,))[0]
            if subject_id != ensa.current_subject:
                raise AttributeError    
        except:
            log.debug_error()
            log.err('That information does not belong to current subject.')
            return 
        self.query("DELETE FROM Information WHERE information_id = %s", (information_id,))
        log.info('Information deleted.')


    def get_informations(self, info_type=None, no_composite_parts=False):
        if not self.subject_ok():
            return []
        if info_type is None:
            info_type = Database.INFORMATION_ALL
        result = []
        if no_composite_parts:
            infos_nodata = self.query("SELECT I.information_id, I.subject_id, S.codename, I.type, I.name, I.level, I.accuracy, I.valid, I.modified, I.note FROM Subject S INNER JOIN Information I ON S.subject_id = I.subject_id WHERE I.subject_id = %s AND I.information_id NOT IN (SELECT part_id FROM Composite) ORDER BY I.name", (ensa.current_subject,))
        else:
            infos_nodata = self.query("SELECT I.information_id, I.subject_id, S.codename, I.type, I.name, I.level, I.accuracy, I.valid, I.modified, I.note FROM Subject S INNER JOIN Information I ON S.subject_id = I.subject_id WHERE I.subject_id = %s ORDER BY I.name", (ensa.current_subject,))
        infos = []
        for info in infos_nodata:
            if info[3] in [Database.INFORMATION_ALL, Database.INFORMATION_TEXT]:
                value = self.query("SELECT value FROM Text WHERE information_id = %s", (info[0],))[0][0]
            elif info[3] in [Database.INFORMATION_ALL, Database.INFORMATION_BINARY]:
                value = b'[binary]'
            elif info[3] in [Database.INFORMATION_ALL, Database.INFORMATION_COMPOSITE]:
                value = b'{composite}'
            else:
                value = 'ERROR'
            infos.append(tuple(list(info)+[value]))
        return infos
    
    def get_information(self, information_id):
        try:
            info = self.query("SELECT I.information_id, S.codename, I.type, I.name, I.level, I.accuracy, I.valid, I.note FROM Subject S INNER JOIN Information I ON S.subject_id = I.subject_id WHERE I.subject_id = %s AND I.information_id = %s", (ensa.current_subject, information_id))[0]
        except:
            log.err('There is no such information.')
            log.debug_error()
            return []

        if info[2] in [Database.INFORMATION_ALL, Database.INFORMATION_TEXT]:
            value = self.query("SELECT value FROM Text WHERE information_id = %s", (info[0],))[0][0]
        elif info[2] in [Database.INFORMATION_ALL, Database.INFORMATION_BINARY]:
            value = b'[binary]'
        elif info[2] in [Database.INFORMATION_ALL, Database.INFORMATION_COMPOSITE]:
            value = b' '.join(row[0] for row in self.query("SELECT part_id FROM Composite WHERE information_id = %s", (information_id,)))
        else:
            value = b'ERROR'
        return tuple(list(info)+[value])
      

    def update_information(self, **kwargs):
        if not self.subject_ok():
            return []
        try:
            self.query("UPDATE Information SET modified = %s, subject_id = %s, name = %s, level = %s, accuracy = %s, valid = %s, note = %s WHERE information_id = %s AND subject_id = %s", tuple([time.strftime('%Y-%m-%d %H:%M:%S')] + [kwargs[x] for x in [
                'subject_id', 'name', 'level', 'accuracy', 
                'valid', 'note', 'information_id'
            ]] + [ensa.current_subject]))
            if 'value' in kwargs.keys():
                self.query("UPDATE Text SET value = %s WHERE information_id = %s AND information_id IN(SELECT information_id FROM Information WHERE subject_id = %s)", (kwargs['value'], kwargs['information_id'], ensa.current_subject))
            #elif 'path' in kwargs.keys():# TODO binary
            #elif 'compounds' in kwargs.keys(): # TODO composite without edit support?
        except: 
            log.debug_error()
            log.err("Information update failed.")
    
    
    def update_information_metadata(self, information_ids, accuracy=None, level=None, valid=None, note=None): 
        if not self.subject_ok():
            return []
        if accuracy:
            self.query("UPDATE Information SET modified = %s, accuracy = %s WHERE subject_id = %s AND information_id IN ("+information_ids+")", (time.strftime('%Y-%m-%d %H:%M:%S'), accuracy, ensa.current_subject))
        elif valid is not None:
            self.query("UPDATE Information SET modified = %s, valid = %s WHERE subject_id = %s AND information_id IN ("+information_ids+")", (time.strftime('%Y-%m-%d %H:%M:%S'), valid, ensa.current_subject))
        elif note:
            self.query("UPDATE Information SET modified = %s, note = %s WHERE subject_id = %s AND information_id IN ("+information_ids+")", (time.strftime('%Y-%m-%d %H:%M:%S'), note, ensa.current_subject))
        else: # only level remains
            self.query("UPDATE Information SET modified = %s, level = %s WHERE subject_id = %s AND information_id IN ("+information_ids+")", (time.strftime('%Y-%m-%d %H:%M:%S'), level, ensa.current_subject))
            



###########################################
# Location methods
###########################################
    def create_location(self, name, lat, lon, accuracy=0, valid=True, note=None):
        if not self.ring_ok():
            return None
        try:
            gps = 'POINT(%f, %f)' % (lat, lon) if lat and lon else 'NULL'
            print(gps)
            self.query("INSERT INTO Location(name, gps, accuracy, valid, ring_id, modified, note) VALUES(%s, "+gps+", %s, %s, %s, %s, %s)", (name, accuracy, valid, ensa.current_ring, time.strftime('%Y-%m-%d %H:%M:%S'), note))
            location_id = self.query("SELECT location_id from Location ORDER BY location_id DESC LIMIT 1")[0][0]
            return location_id
        except:
            log.debug_error()
            return None
    
    
    def get_locations(self):
        if not self.ring_ok():
            return []
        return self.query("SELECT location_id, name, ST_AsText(gps), accuracy, valid, modified, note FROM Location WHERE ring_id = %s", (ensa.current_ring,))


    def delete_locations(self, location_ids):
        if not self.ring_ok():
            return []
        self.query("DELETE FROM Location WHERE location_id IN ("+location_ids+") AND ring_id = %s", (ensa.current_ring,))
    

    def get_location(self, location_id):
        if not self.ring_ok():
            return []
        try:
            info = self.query("SELECT location_id, name, ST_AsText(gps), accuracy, valid, note FROM Location WHERE location_id = %s AND ring_id = %s", (location_id, ensa.current_ring,))[0]
        except:
            log.err('There is no such location.')
            log.debug_error()
            return []
        return info
    

    def update_location(self, **kwargs):
        if not self.ring_ok():
            return []
        try:
            print(kwargs)
            gps = 'POINT(%s, %s)' % (kwargs['lat'], kwargs['lon']) if kwargs.get('lat') and kwargs.get('lon') else 'NULL'
            self.query("UPDATE Location SET modified = %s, name = %s, gps = "+gps+", accuracy = %s, valid = %s, note = %s WHERE location_id = %s AND ring_id = %s", tuple([time.strftime('%Y-%m-%d %H:%M:%S')] + [kwargs[x] for x in [
                'name', 'accuracy', 'valid', 'note', 'location_id']] + [ensa.current_ring]))
        except: 
            log.debug_error()
            log.err("Location update failed.")

    def update_location_metadata(self, location_ids, accuracy=None, valid=None, note=None):
        if not self.ring_ok():
            return []
        if accuracy:
            self.query("UPDATE Location SET modified = %s, accuracy = %s WHERE ring_id = %s AND location_id IN ("+location_ids+")", (time.strftime('%Y-%m-%d %H:%M:%S'), accuracy, ensa.current_ring))
        elif valid is not None:
            self.query("UPDATE Location SET modified = %s, valid = %s WHERE ring_id = %s AND location_id IN ("+location_ids+")", (time.strftime('%Y-%m-%d %H:%M:%S'), valid, ensa.current_ring))
        elif note:
            self.query("UPDATE Location SET modified = %s, note = %s WHERE ring_id = %s AND location_id IN ("+location_ids+")", (time.strftime('%Y-%m-%d %H:%M:%S'), note, ensa.current_ring))
            
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
            self.query("INSERT INTO Time(time, accuracy, valid, ring_id, modified, note) VALUES(%s, %s, %s, %s, %s, %s)", (dt, accuracy, valid, ensa.current_ring, time.strftime('%Y-%m-%d %H:%M:%S'), note))
            time_id = self.query("SELECT time_id from Time ORDER BY time_id DESC LIMIT 1")[0][0]
            return time_id
        except:
            log.debug_error()
            return None

    def get_times(self):
        if not self.ring_ok():
            return []
        return self.query("SELECT time_id, DATE_FORMAT(time, '%Y-%m-%d %H:%i:%s'), accuracy, valid, modified, note FROM Time WHERE ring_id = %s", (ensa.current_ring,))
        #return self.query("SELECT time_id, , accuracy, valid, note FROM Time WHERE time_id IN (8)")

    def delete_times(self, time_ids):
        if not self.ring_ok():
            return []
        self.query("DELETE FROM Time WHERE time_id IN ("+time_ids+") AND ring_id = %s", (ensa.current_ring,))
    

    def get_time(self, time_id):
        if not self.ring_ok():
            return []
        try:
            info = self.query("SELECT time_id, DATE_FORMAT(time, '%Y-%m-%d %H:%i:%s'), accuracy, valid, note FROM Time WHERE time_id = %s AND ring_id = %s", (time_id, ensa.current_ring,))[0]
        except:
            log.err('There is no such time entry.')
            log.debug_error()
            return []
        return info
    

    def update_time(self, **kwargs):
        if not self.ring_ok():
            return []
        try:
            self.query("UPDATE Time SET modified = %s, time = %s, accuracy = %s, valid = %s, note = %s WHERE time_id = %s AND ring_id = %s", tuple([time.strftime('%Y-%m-%d %H:%M:%S')] + [kwargs[x] for x in [
                'datetime', 'accuracy', 'valid', 'note', 'time_id']] + [ensa.current_ring]))
        except: 
            log.debug_error()
            log.err("Time update failed.")
    
    def update_time_metadata(self, time_ids, accuracy=None, valid=None, note=None):
        if not self.ring_ok():
            return []
        if accuracy:
            self.query("UPDATE Time SET modified = %s, accuracy = %s WHERE ring_id = %s AND time_id IN ("+time_ids+")", (time.strftime('%Y-%m-%d %H:%M:%S'), accuracy, ensa.current_ring))
        elif valid is not None:
            self.query("UPDATE Time SET modified = %s, valid = %s WHERE ring_id = %s AND time_id IN ("+time_ids+")", (time.strftime('%Y-%m-%d %H:%M:%S'), valid, ensa.current_ring))
        elif note:
            self.query("UPDATE Time SET modified = %s, note = %s WHERE ring_id = %s AND time_id IN ("+time_ids+")", (time.strftime('%Y-%m-%d %H:%M:%S'), note, ensa.current_ring))

###########################################
# Association methods
###########################################
    def create_association(self, level=None, accuracy=0, valid=True, note=None):
        if not self.ring_ok():
            return None
        try:
            self.query("INSERT INTO Association(ring_id, level, accuracy, valid, modified, note) VALUES(%s, %s, %s, %s, %s, %s)", (ensa.current_ring, level, accuracy, valid, time.strftime('%Y-%m-%d %H:%M:%S'), note))
            association_id = self.query("SELECT association_id from Association ORDER BY association_id DESC LIMIT 1")[0][0]
            return association_id
        except:
            log.debug_error()
            return None

    def associate_association(self, association_id, association_ids):
        if not self.ring_ok():
            return None
        try:
            ring_id = self.query("SELECT DISTINCT ring_id FROM Association WHERE association_id = %s OR association_id IN ("+association_ids+")", (association_id,))
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
            self.query("INSERT INTO AA(association_id_1, association_id_2) SELECT %s, association_id FROM Association WHERE association_id IN ("+ association_ids +") AND ring_id = %s", (association_id, ensa.current_ring))
            count_after = self.query("SELECT COUNT(*) FROM AA")[0][0]
            if count_before == count_after:
                log.err('Association must belong to current ring.')
                return None
            self.query("UPDATE Association SET modified = %s WHERE association_id = %s", (time.strftime('%Y-%m-%d %H:%M:%S'), association_id))
            return tuple([(association_id, a) for a in association_ids.split(',')])
        except:
            log.debug_error()
            log.err('Failed to associate association.')
            return None


    def associate_information(self, association_id, information_ids):
        if not self.ring_ok():
            return None
        try:
            ring_id = self.query("SELECT ring_id FROM Association WHERE association_id = %s", (association_id,))[0][0]
            if ring_id != ensa.current_ring:
                raise AttributeError
        except:
            log.err('Current ring has no such asssociation.')
            return None
        try:
            count_before = self.query("SELECT COUNT(*) FROM AI")[0][0]
            self.query("INSERT INTO AI(association_id, information_id) SELECT %s, information_id FROM Information WHERE information_id IN ("+ information_ids +") AND subject_id IN (SELECT subject_id FROM Subject WHERE ring_id = %s)", (association_id, ensa.current_ring))
            count_after = self.query("SELECT COUNT(*) FROM AI")[0][0]
            if count_before == count_after:
                log.err('Information must belong to current ring.')
                return None
            self.query("UPDATE Association SET modified = %s WHERE association_id = %s", (time.strftime('%Y-%m-%d %H:%M:%S'), association_id))
            return tuple([(association_id, i) for i in information_ids])
        except:
            log.err('Failed to associate information.')
            return None


    def associate_location(self, association_id, location_ids):
        if not self.ring_ok():
            return None
        try:
            ring_id = self.query("SELECT ring_id FROM Association WHERE association_id = %s", (association_id,))[0][0]
            if ring_id != ensa.current_ring:
                raise AttributeError
        except:
            log.err('Current ring has no such asssociation.')
            return None
        try:
            count_before = self.query("SELECT COUNT(*) FROM AL")[0][0]
            self.query("INSERT INTO AL(association_id, location_id) SELECT %s, location_id FROM Location WHERE location_id IN ("+ location_ids +") AND ring_id = %s", (association_id, ensa.current_ring))
            count_after = self.query("SELECT COUNT(*) FROM AL")[0][0]
            if count_before == count_after:
                log.err('Location must belong to current ring.')
                return None
            self.query("UPDATE Association SET modified = %s WHERE association_id = %s", (time.strftime('%Y-%m-%d %H:%M:%S'), association_id))
            return tuple([(association_id, l) for l in location_ids])
        except:
            log.debug_error()
            log.err('Failed to associate location.')
            return None
    
    
    def associate_subject(self, association_id, codenames):
        if not self.ring_ok():
            return None
        try:
            ring_id = self.query("SELECT ring_id FROM Association WHERE association_id = %s", (association_id,))[0][0]
            if ring_id != ensa.current_ring:
                raise AttributeError
        except:
            log.err('Current ring has no such asssociation.')
            return None
        try:
            count_before = self.query("SELECT COUNT(*) FROM AI")[0][0]
            self.query("INSERT INTO AI(association_id, information_id) SELECT %s, I.information_id FROM Subject S INNER JOIN Information I ON S.subject_id = I.subject_id WHERE I.name = 'codename' AND S.codename IN ("+ codenames +") AND S.ring_id = %s", (association_id, ensa.current_ring))
            count_after = self.query("SELECT COUNT(*) FROM AI")[0][0]
            if count_before == count_after:
                log.err('Subject must belong to current ring.')
                return None
            self.query("UPDATE Association SET modified = %s WHERE association_id = %s", (time.strftime('%Y-%m-%d %H:%M:%S'), association_id))
            return tuple([(association_id, codename) for codename in codenames.split(',')])
        except:
            log.debug_error()
            log.err('Failed to associate subject.')
            return None


    def associate_time(self, association_id, time_ids):
        if not self.ring_ok():
            return None
        try:
            ring_id = self.query("SELECT ring_id FROM Association WHERE association_id = %s", (association_id,))[0][0]
            if ring_id != ensa.current_ring:
                raise AttributeError
        except:
            log.err('Current ring has no such asssociation.')
            return None
        try:
            count_before = self.query("SELECT COUNT(*) FROM AT")[0][0]
            self.query("INSERT INTO AT(association_id, time_id) SELECT %s, time_id FROM Time WHERE time_id IN ("+ time_ids +") AND ring_id = %s", (association_id, ensa.current_ring))
            count_after = self.query("SELECT COUNT(*) FROM AT")[0][0]
            if count_before == count_after:
                log.err('Time must belong to current ring.')
                return None
            self.query("UPDATE Association SET modified = %s WHERE association_id = %s", (time.strftime('%Y-%m-%d %H:%M:%S'), association_id))
            return tuple([(association_id, t) for t in time_ids])
        except:
            log.debug_error()
            log.err('Failed to associate time.')
            return None

    def get_associations(self):
        if not self.ring_ok():
            return []
        # get associations
        return self.query("SELECT association_id, ring_id, level, accuracy, valid, modified, note FROM Association WHERE ring_id = %s", (ensa.current_ring,))


    def get_associations_by_ids(self, association_ids):
        if not self.ring_ok():
            return []
        # get associations
        associations = self.query("SELECT association_id, ring_id, level, accuracy, valid, modified, note FROM Association WHERE association_id IN("+association_ids+")")
        result = []
        for assoc in associations:
            # in current ring?
            if assoc[1] != ensa.current_ring:
                continue
            # TODO is ring check needed for ITL entries?
            # get info entries (+ subject)
            infos_nodata = self.query("SELECT I.information_id, I.subject_id, S.codename, I.type, I.name, I.level, I.accuracy, I.valid, I.modified, I.note FROM Subject S INNER JOIN Information I ON S.subject_id = I.subject_id WHERE information_id IN (SELECT information_id FROM AI WHERE association_id = %s) ORDER BY information_id", (assoc[0],))
            infos = []
            for info in infos_nodata:
                if info[3] == Database.INFORMATION_TEXT:
                    value = self.query("SELECT value FROM Text WHERE information_id = %s", (info[0],))[0][0]
                elif info[3] == Database.INFORMATION_BINARY:
                    value = '[binary]'
                elif info[3] == Database.INFORMATION_COMPOSITE:
                    value = '{composite}'
                else:
                    value = 'ERROR'
                infos.append(tuple(list(info)+[value]))
            # get time entries
            times = self.query("SELECT Time.time_id, DATE_FORMAT(time, '%Y-%m-%d %H:%i:%s'), accuracy, valid, modified, note FROM Time INNER JOIN AT ON Time.time_id = AT.time_id WHERE AT.association_id = %s", (assoc[0],)) or []
            # get location entries
            locations = self.query("SELECT Location.location_id, name, ST_AsText(gps), accuracy, valid, modified, note FROM Location INNER JOIN AL ON Location.location_id = AL.location_id WHERE AL.association_id = %s", (assoc[0],)) or []
            # get associated associations
            associations = self.query("SELECT association_id, ring_id, level, accuracy, valid, modified, note FROM Association WHERE association_id IN(SELECT association_id_2 FROM AA WHERE association_id_1 = %s)", (assoc[0],)) or []

            result.append((assoc, infos, times, locations, associations))
        return result


    def delete_associations(self, association_ids):
        if not self.ring_ok():
            return []
        self.query("DELETE FROM Association WHERE association_id IN ("+association_ids+") AND ring_id = %s", (ensa.current_ring,))


    def dissociate_associations(self, association_id, association_ids):
        if not self.ring_ok():
            return []
        self.query("DELETE FROM AA WHERE association_id_1 IN (SELECT association_id FROM Association WHERE association_id = %s AND ring_id = %s) AND association_id_2 IN ("+association_ids+")", (association_id, ensa.current_ring,))
        self.query("UPDATE Association SET modified = %s WHERE association_id = %s AND ring_id = %s", (time.strftime('%Y-%m-%d %H:%M:%S'), association_id, ensa.current_ring))

    
    def dissociate_informations(self, association_id, information_ids):
        if not self.ring_ok():
            return []
        self.query("DELETE FROM AI WHERE association_id IN (SELECT association_id FROM Association WHERE association_id = %s AND ring_id = %s) AND information_id IN ("+information_ids+")", (association_id, ensa.current_ring,))
        self.query("UPDATE Association SET modified = %s WHERE association_id = %s AND ring_id = %s", (time.strftime('%Y-%m-%d %H:%M:%S'), association_id, ensa.current_ring))
     
    
    def dissociate_locations(self, association_id, location_ids):
        if not self.ring_ok():
            return []
        self.query("DELETE FROM AL WHERE association_id IN (SELECT association_id FROM Association WHERE association_id = %s AND ring_id = %s) AND location_id IN ("+location_ids+")", (association_id, ensa.current_ring,))
        self.query("UPDATE Association SET modified = %s WHERE association_id = %s AND ring_id = %s", (time.strftime('%Y-%m-%d %H:%M:%S'), association_id, ensa.current_ring))
    
    def dissociate_times(self, association_id, time_ids):
        if not self.ring_ok():
            return []
        self.query("DELETE FROM AT WHERE association_id IN (SELECT association_id FROM Association WHERE association_id = %s AND ring_id = %s) AND time_id IN ("+time_ids+")", (association_id, ensa.current_ring,))
        self.query("UPDATE Association SET modified = %s WHERE association_id = %s AND ring_id = %s", (time.strftime('%Y-%m-%d %H:%M:%S'), association_id, ensa.current_ring))


    def get_association(self, association_id):
        if not self.ring_ok():
            return []
        try:
            info = self.query("SELECT association_id, level, accuracy, valid, note FROM Association WHERE association_id = %s AND ring_id = %s", (association_id, ensa.current_ring,))[0]
        except:
            log.err('There is no such association.')
            log.debug_error()
            return []
        return info
    

    def update_association(self, **kwargs):
        if not self.ring_ok():
            return []
        try:
            self.query("UPDATE Association SET modified = %s, level = %s, accuracy = %s, valid = %s, note = %s WHERE association_id = %s AND ring_id = %s", tuple([time.strftime('%Y-%m-%d %H:%M:%S')] + [kwargs[x] for x in [
                'level', 'accuracy', 'valid', 'note', 'association_id']] + [ensa.current_ring]))
        except: 
            log.debug_error()
            log.err("Association update failed.")
    
    
    def update_association_metadata(self, association_ids, accuracy=None, level=None, valid=None, note=None): 
        if not self.ring_ok():
            return []
        if accuracy:
            self.query("UPDATE Association SET modified = %s, accuracy = %s WHERE ring_id = %s AND association_id IN ("+association_ids+")", (time.strftime('%Y-%m-%d %H:%M:%S'), accuracy, ensa.current_ring))
        elif valid is not None:
            self.query("UPDATE Association SET modified = %s, valid = %s WHERE ring_id = %s AND association_id IN ("+association_ids+")", (time.strftime('%Y-%m-%d %H:%M:%S'), valid, ensa.current_ring))
        elif note:
            self.query("UPDATE Association SET modified = %s, note = %s WHERE ring_id = %s AND association_id IN ("+association_ids+")", (time.strftime('%Y-%m-%d %H:%M:%S'), note, ensa.current_ring))
        else: # only level remains
            self.query("UPDATE Association SET modified = %s, level = %s WHERE ring_id = %s AND association_id IN ("+association_ids+")", (time.strftime('%Y-%m-%d %H:%M:%S'), level, ensa.current_ring))
            
###########################################
# Keyword methods
###########################################
    def get_keyword_id(self, keyword):
        try:
            keyword_id = self.query("SELECT keyword_id FROM Keyword WHERE keyword = %s", (keyword,))[0][0]
        except:
            self.query("INSERT INTO Keyword(keyword) VALUES(%s)", (keyword,))
            keyword_id = self.query("SELECT keyword_id FROM Keyword ORDER BY keyword_id DESC LIMIT 1")[0][0]
        return keyword_id


    def add_keyword(self, information_ids, keyword):
        if not self.subject_ok():
            return []
        keyword_id = self.get_keyword_id(keyword)
        self.query("INSERT INTO IK(information_id, keyword_id) SELECT information_id, %s FROM Information WHERE subject_id = %s AND information_id IN ("+information_ids+")", (keyword_id, ensa.current_subject))


    def delete_keywords(self, information_ids, keywords):
        if not self.subject_ok():
            return []
        if keywords:
            keyword_ids = ','.join([str(x[0]) for x in self.query("SELECT keyword_id FROM Keyword WHERE keyword IN ("+keywords+")")])
            self.query("DELETE FROM IK WHERE keyword_id IN ("+keyword_ids+") AND information_id IN (SELECT information_id FROM Information WHERE information_id IN("+information_ids+") AND subject_id = %s)", (ensa.current_subject,))
        else: # delete all keywords
            self.query("DELETE FROM IK WHERE information_id IN (SELECT information_id FROM Information WHERE information_id IN("+information_ids+") AND subject_id = %s)", (ensa.current_subject,))
        self.information_cleanup('keywords')
            
    def get_keywords(self):
        if not self.ring_ok():
            return []
        if ensa.current_subject:
            result = self.query("SELECT DISTINCT K.keyword FROM Keyword K INNER JOIN IK ON K.keyword_id = IK.keyword_id INNER JOIN Information I ON IK.information_id = I.information_id WHERE I.subject_id = %s ORDER BY K.keyword", (ensa.current_subject,))
        else:
            result = self.query("SELECT DISTINCT K.keyword FROM Keyword K INNER JOIN IK ON K.keyword_id = IK.keyword_id INNER JOIN Information I ON IK.information_id = I.information_id INNER JOIN Subject S ON I.subject_id = S.subject_id WHERE S.ring_id = %s ORDER BY K.keyword", (ensa.current_ring,))
        return result

    def get_keywords_for_informations(self, information_ids):
        if not self.subject_ok():
            return []
        result = self.query("SELECT IK.information_id, K.keyword FROM IK INNER JOIN Keyword K ON IK.keyword_id = K.keyword_id WHERE IK.information_id IN (SELECT information_id FROM Information WHERE information_id IN ("+information_ids+") AND subject_id = %s)", (ensa.current_subject,))
        return result
   

    def get_informations_for_keywords_or(self, keywords):
        if not self.ring_ok():
            return []
        if ensa.current_subject:
            infos_nodata = self.query("SELECT I.information_id, I.subject_id, S.codename, I.type, I.name, I.level, I.accuracy, I.valid, I.modified, I.note FROM Information I INNER JOIN Subject S ON I.subject_id = S.subject_id WHERE I.subject_id = %s AND I.information_id IN (SELECT IK.information_id FROM IK INNER JOIN Keyword K ON IK.keyword_id = K.keyword_id WHERE K.keyword IN ("+keywords+"))", (ensa.current_subject,))
        else:
            infos_nodata = self.query("SELECT I.information_id, I.subject_id, S.codename, I.type, I.name, I.level, I.accuracy, I.valid, I.modified, I.note FROM Information I INNER JOIN Subject S ON I.subject_id = S.subject_id WHERE S.ring_id = %s AND I.information_id IN (SELECT IK.information_id FROM IK INNER JOIN Keyword K ON IK.keyword_id = K.keyword_id WHERE K.keyword IN ("+keywords+"))", (ensa.current_ring,))
        infos = []
        for info in infos_nodata:
            if info[3] in [Database.INFORMATION_ALL, Database.INFORMATION_TEXT]:
                value = self.query("SELECT value FROM Text WHERE information_id = %s", (info[0],))[0][0]
            elif info[3] in [Database.INFORMATION_ALL, Database.INFORMATION_BINARY]:
                value = b'[binary]'
            elif info[3] in [Database.INFORMATION_ALL, Database.INFORMATION_COMPOSITE]:
                value = b'{composite}'
            else:
                value = 'ERROR'
            infos.append(tuple(list(info)+[value]))
        return infos


    def get_informations_for_keywords_and(self, keywords):
        if not self.ring_ok():
            return []
        if ensa.current_subject:
            infos_nodata = self.query("SELECT I.information_id, I.subject_id, S.codename, I.type, I.name, I.level, I.accuracy, I.valid, I.modified, I.note FROM Information I INNER JOIN Subject S ON I.subject_id = S.subject_id WHERE I.subject_id = %s AND I.information_id IN(SELECT information_id FROM IK WHERE keyword_id IN(SELECT keyword_id FROM Keyword WHERE keyword IN ("+keywords+")) GROUP BY information_id HAVING COUNT(keyword_id) = %s)", (ensa.current_subject, keywords.count(',')+1))
        else:
            infos_nodata = self.query("SELECT I.information_id, I.subject_id, S.codename, I.type, I.name, I.level, I.accuracy, I.valid, I.modified, I.note FROM Information I INNER JOIN Subject S ON I.subject_id = S.subject_id WHERE S.ring_id = %s AND I.information_id IN(SELECT information_id FROM IK WHERE keyword_id IN(SELECT keyword_id FROM Keyword WHERE keyword IN ("+keywords+")) GROUP BY information_id HAVING COUNT(keyword_id) = %s)", (ensa.current_ring, keywords.count(',')+1))

        infos = []
        for info in infos_nodata:
            if info[3] in [Database.INFORMATION_ALL, Database.INFORMATION_TEXT]:
                value = self.query("SELECT value FROM Text WHERE information_id = %s", (info[0],))[0][0]
            elif info[3] in [Database.INFORMATION_ALL, Database.INFORMATION_BINARY]:
                value = b'[binary]'
            elif info[3] in [Database.INFORMATION_ALL, Database.INFORMATION_COMPOSITE]:
                value = b'{composite}'
            else:
                value = 'ERROR'
            infos.append(tuple(list(info)+[value]))
        return infos


# # #
ensa.db = Database()
# # #



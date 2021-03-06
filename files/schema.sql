CREATE TABLE Ring
    (
            ring_id INTEGER NOT NULL PRIMARY KEY,
            name VARCHAR(30) NOT NULL UNIQUE,
            note VARCHAR(16384),
            reference_time_id INTEGER
    );
CREATE TABLE Information(
            information_id INTEGER NOT NULL PRIMARY KEY,
            subject_id INTEGER NOT NULL,
            type TINYINT UNSIGNED NOT NULL,
            name VARCHAR(80) NOT NULL,
            level TINYINT UNSIGNED DEFAULT NULL,
            accuracy TINYINT UNSIGNED DEFAULT 0,
            valid BOOL DEFAULT TRUE,
            modified DATETIME NOT NULL,
            note VARCHAR(16384),
            FOREIGN KEY(subject_id) REFERENCES Subject(subject_id) ON DELETE CASCADE
    );
CREATE TABLE Text(
            information_id INTEGER NOT NULL PRIMARY KEY,
            value VARCHAR(16384) NOT NULL,
            FOREIGN KEY(information_id) REFERENCES Information(information_id) ON DELETE CASCADE
    );
CREATE TABLE Composite(
            information_id INTEGER NOT NULL,
            part_id INTEGER NOT NULL,
            PRIMARY KEY(information_id, part_id),
            FOREIGN KEY(information_id) REFERENCES Information(information_id) ON DELETE CASCADE,
            FOREIGN KEY(part_id) REFERENCES Information(information_id) ON DELETE CASCADE
    );
CREATE TABLE Association(
            association_id INTEGER NOT NULL PRIMARY KEY,
            ring_id INTEGER NOT NULL,
            level TINYINT UNSIGNED DEFAULT NULL,
            accuracy TINYINT UNSIGNED DEFAULT 0,
            valid BOOL DEFAULT TRUE,
            modified DATETIME NOT NULL,
            note VARCHAR(16384),
            FOREIGN KEY(ring_id) REFERENCES Ring(ring_id) ON DELETE CASCADE
    );
CREATE TABLE Time(
            time_id INTEGER NOT NULL PRIMARY KEY,
            ring_id INTEGER NOT NULL,
            time DATETIME NOT NULL,
            accuracy TINYINT UNSIGNED DEFAULT 0,
            valid BOOL DEFAULT TRUE,
            note VARCHAR(16384), modified DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00',
            FOREIGN KEY(ring_id) REFERENCES Ring(ring_id) ON DELETE CASCADE
    );
CREATE TABLE AA(
            association_id_1 INTEGER NOT NULL,
            association_id_2 INTEGER NOT NULL,
            PRIMARY KEY(association_id_1, association_id_2),
            FOREIGN KEY(association_id_1) REFERENCES Association(association_id) ON DELETE CASCADE,
            FOREIGN KEY(association_id_2) REFERENCES Association(association_id) ON DELETE CASCADE
    );
CREATE TABLE AI(
            association_id INTEGER NOT NULL,
            information_id INTEGER NOT NULL,
            PRIMARY KEY(association_id, information_id),
            FOREIGN KEY(association_id) REFERENCES Association(association_id) ON DELETE CASCADE,
            FOREIGN KEY(information_id) REFERENCES Information(information_id) ON DELETE CASCADE
    );
CREATE TABLE AT(
            association_id INTEGER NOT NULL,
            time_id INTEGER NOT NULL,
            PRIMARY KEY(association_id, time_id),
            FOREIGN KEY(association_id) REFERENCES Association(association_id) ON DELETE CASCADE,
            FOREIGN KEY(time_id) REFERENCES Time(time_id) ON DELETE CASCADE
    );
CREATE TABLE Keyword(
            keyword_id INTEGER NOT NULL PRIMARY KEY,
            keyword VARCHAR(64) NOT NULL UNIQUE
    );
CREATE TABLE IK(
            information_id INTEGER NOT NULL,
            keyword_id INTEGER NOT NULL,
            PRIMARY KEY(information_id, keyword_id),
            FOREIGN KEY(information_id) REFERENCES Information(information_id) ON DELETE CASCADE,
            FOREIGN KEY(keyword_id) REFERENCES Keyword(keyword_id) ON DELETE CASCADE
    );
CREATE TABLE Location(
    location_id INTEGER NOT NULL PRIMARY KEY,
            ring_id INTEGER NOT NULL,
            name VARCHAR(1024),
            lat DECIMAL(8,6),
            lon DECIMAL(9,6),
            accuracy TINYINT UNSIGNED DEFAULT 0,
            valid BOOL DEFAULT TRUE,
            modified DATETIME NOT NULL,
            note VARCHAR(16384),
            FOREIGN KEY(ring_id) REFERENCES Ring(ring_id) ON DELETE CASCADE
    );
CREATE TABLE AL(
            association_id INTEGER NOT NULL,
            location_id INTEGER NOT NULL,
            PRIMARY KEY(association_id, location_id),
            FOREIGN KEY(association_id) REFERENCES Association(association_id) ON DELETE CASCADE,
            FOREIGN KEY(location_id) REFERENCES Location(location_id) ON DELETE CASCADE
    );
CREATE TABLE IF NOT EXISTS "Subject" (
            `subject_id`    INTEGER NOT NULL,
            `ring_id`       INTEGER NOT NULL,
            `codename`      VARCHAR ( 50 ) NOT NULL,
            `created`       DATETIME NOT NULL,
            `note`  VARCHAR ( 16384 ),
            UNIQUE(`ring_id`, `codename`),
            FOREIGN KEY(`ring_id`) REFERENCES `Ring`(`ring_id`) ON DELETE CASCADE,
            PRIMARY KEY(`subject_id`)
    );
CREATE TABLE IF NOT EXISTS "Active" (
            `information_id` INTEGER NOT NULL,
            `time_id` INTEGER NOT NULL,
            `active` BOOL NOT NULL DEFAULT true,
            FOREIGN KEY(`time_id`) REFERENCES `Time`(`time_id`) ON DELETE CASCADE,
            FOREIGN KEY(`information_id`) REFERENCES `Information`(`information_id`) ON DELETE CASCADE,
            PRIMARY KEY(`information_id`,`time_id`)
    );

CREATE TABLE Ring
(
	ring_id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
	name VARCHAR(30) NOT NULL UNIQUE,
	password BINARY(60) DEFAULT NULL,
	note VARCHAR(65535)
);


CREATE TABLE Subject(
	subject_id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
	ring_id INTEGER NOT NULL,
	codename VARCHAR(50) NOT NULL UNIQUE,
	created DATETIME NOT NULL,
	note VARCHAR(65535),
	FOREIGN KEY(ring_id) REFERENCES Ring(ring_id)
);


CREATE TABLE Information(
	information_id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
	subject_id INTEGER NOT NULL,
	type TINYINT UNSIGNED NOT NULL,
	name VARCHAR(80) NOT NULL,
	level TINYINT UNSIGNED DEFAULT NULL,
	accuracy TINYINT UNSIGNED DEFAULT 0,
	valid BOOL DEFAULT TRUE,
	modified DATETIME NOTO NULL,
	note VARCHAR(65535),
	FOREIGN KEY(subject_id) REFERENCES Subject(subject_id)
);


CREATE TABLE Text(
	information_id INTEGER NOT NULL PRIMARY KEY,
	value VARCHAR(65535) NOT NULL,
	FOREIGN KEY(information_id) REFERENCES Information(information_id)
);



CREATE TABLE Composite(
	information_id INTEGER NOT NULL,
	part_id INTEGER NOT NULL,
	PRIMARY KEY(information_id, part_id),
	FOREIGN KEY(information_id) REFERENCES Information(information_id),
	FOREIGN KEY(part_id) REFERENCES Information(information_id)
);


CREATE TABLE Association(
	association_id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
	ring_id INTEGER NOT NULL,
	level TINYINT UNSIGNED DEFAULT NULL,
	accuracy TINYINT UNSIGNED DEFAULT 0,
	valid BOOL DEFAULT TRUE,
	note VARCHAR(65535),
	FOREIGN KEY(ring_id) REFERENCES Ring(ring_id)
);


CREATE TABLE Location(
	location_id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
	ring_id INTEGER NOT NULL,
	name VARCHAR(1024),
	gps POINT,
	accuracy TINYINT UNSIGNED DEFAULT 0,
	valid BOOL DEFAULT TRUE,
	note VARCHAR(65535),
	FOREIGN KEY(ring_id) REFERENCES Ring(ring_id)
);

CREATE TABLE Time(
	time_id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
	ring_id INTEGER NOT NULL,
	time DATETIME NOT NULL,
	accuracy TINYINT UNSIGNED DEFAULT 0,
	valid BOOL DEFAULT TRUE,
	note VARCHAR(65535),
	FOREIGN KEY(ring_id) REFERENCES Ring(ring_id)
);

CREATE TABLE AA(
	association_id_1 INTEGER NOT NULL,
	association_id_2 INTEGER NOT NULL,
	PRIMARY KEY(association_id_1, association_id_2),
	FOREIGN KEY(association_id_1) REFERENCES Association(association_id),
	FOREIGN KEY(association_id_2) REFERENCES Association(association_id)
);

CREATE TABLE AI(
	association_id INTEGER NOT NULL,
	information_id INTEGER NOT NULL,
	PRIMARY KEY(association_id, information_id),
	FOREIGN KEY(association_id) REFERENCES Association(association_id),
	FOREIGN KEY(information_id) REFERENCES Information(information_id)
);

CREATE TABLE AL(
	association_id INTEGER NOT NULL,
	location_id INTEGER NOT NULL,
	PRIMARY KEY(association_id, location_id),
	FOREIGN KEY(association_id) REFERENCES Association(association_id),
	FOREIGN KEY(location_id) REFERENCES Location(location_id)
);

CREATE TABLE AT(
	association_id INTEGER NOT NULL,
	time_id INTEGER NOT NULL,
	PRIMARY KEY(association_id, time_id),
	FOREIGN KEY(association_id) REFERENCES Association(association_id),
	FOREIGN KEY(time_id) REFERENCES Time(time_id)
);

CREATE TABLE Tag(
	tag_id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
	tag VARCHAR(64) NOT NULL UNIQUE
);

CREATE TABLE ITag(
	information_id INTEGER NOT NULL,
	tag_id INTEGER NOT NULL,
	PRIMARY KEY(information_id, tag_id),
	FOREIGN KEY(information_id) REFERENCES Information(information_id),
	FOREIGN KEY(tag_id) REFERENCES Tag(tag_id)
);


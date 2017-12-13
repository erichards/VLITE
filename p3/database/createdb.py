"""Functions to create database tables, functions, and triggers."""


def make_error(cursor):
    """Inserts values into the database error table."""
    reason_dict = {'short duration' : 1,
                   'close to bright radio source' : 2,
                   'PyBDSF failed to process' : 3,
                   'poor quality' : 4}

    sql = 'INSERT INTO error (id, reason) VALUES (%s, %s);'
    for key in reason_dict.keys():
        cursor.execute(sql, (reason_dict[key], key))


def create(conn, safe=False):
    """Creates new tables and triggers for the connected `PostgreSQL` 
    database by dropping tables if they exist. The current user
    must own the tables or be a superuser in order to drop them.
    USE WITH CAUTION! DELETING THE DATA CANNOT BE UNDONE.

    Parameters
    ----------
    conn : psycopg2.extensions.connect instance
        The `PostgreSQL` database connection object.
    safe : bool, optional
        If ``False``, the user will be warned that existing data
        is about to be deleted and prompted to continue. Default
        value is ``False``.
    """
    if not safe:
        cont = raw_input(('\nWARNING: Any existing tables and data in this '
                          'database will be deleted. Are you sure you want '
                          'to continue? '))
    else:
        cont = 'yes'
    if cont == 'y' or cont == 'yes':
        print('\nDropping tables if they exist...')
        cur = conn.cursor()
        sql = (
            '''
            DROP TABLE IF EXISTS vlite_unique;
            DROP TABLE IF EXISTS catalog_match;
            DROP TABLE IF EXISTS corrected_flux;
            DROP TABLE IF EXISTS detected_source;
            DROP TABLE IF EXISTS detected_island;
            DROP TABLE IF EXISTS image;
            DROP TABLE IF EXISTS assoc_source;
            DROP TABLE IF EXISTS error;
            DROP FUNCTION IF EXISTS update_assoc_func;
            DROP FUNCTION IF EXISTS remove_vu_func;
            DROP FUNCTION IF EXISTS update_detected_func;
            ''')
        cur.execute(sql)

        print('\nCreating new tables...')
        sql = (
            '''
            CREATE EXTENSION IF NOT EXISTS q3c;

            CREATE TABLE error (
                id INTEGER NOT NULL,
                reason TEXT,
                PRIMARY KEY (id)
            );

            CREATE TABLE assoc_source (
                id SERIAL NOT NULL,
                ra DOUBLE PRECISION,
                e_ra DOUBLE PRECISION,
                dec DOUBLE PRECISION,
                e_dec DOUBLE PRECISION,
                beam DOUBLE PRECISION,
                ndetect INTEGER,
                nmatches INTEGER,
                PRIMARY KEY (id)
            )
            WITH (fillfactor=90);

            CREATE TABLE image (
                id SERIAL NOT NULL UNIQUE,
                filename TEXT UNIQUE,
                imsize VARCHAR(14),
                obs_ra DOUBLE PRECISION,
                obs_dec DOUBLE PRECISION,
                pixel_scale DOUBLE PRECISION,
                object TEXT,
                obs_date DATE,
                map_date DATE,
                obs_freq REAL,
                primary_freq REAL,
                bmaj REAL,
                bmin REAL,
                bpa REAL,
                noise REAL,
                peak REAL,
                config TEXT,
                nvis INTEGER,
                mjdtime REAL,
                tau_time REAL,
                duration REAL,
                radius REAL,
                nsrc INTEGER,
                rms_box VARCHAR(14),
                stage INTEGER,
                error_id INTEGER,
                PRIMARY KEY (id),
                FOREIGN KEY (error_id) 
                  REFERENCES error (id) 
                  ON UPDATE CASCADE
            );

            CREATE TABLE detected_island (
                isl_id INTEGER NOT NULL,
                image_id INTEGER NOT NULL,
                total_flux DOUBLE PRECISION,
                e_total_flux DOUBLE PRECISION,
                rms DOUBLE PRECISION,
                mean DOUBLE PRECISION,
                resid_rms DOUBLE PRECISION,
                resid_mean DOUBLE PRECISION,
                PRIMARY KEY (isl_id, image_id),
                FOREIGN KEY (image_id) 
                    REFERENCES image (id) 
                    ON DELETE CASCADE
            );

            CREATE TABLE detected_source (
                src_id INTEGER NOT NULL,
                isl_id INTEGER NOT NULL,
                image_id INTEGER NOT NULL,
                ra DOUBLE PRECISION,
                e_ra DOUBLE PRECISION,
                dec DOUBLE PRECISION,
                e_dec DOUBLE PRECISION,
                total_flux DOUBLE PRECISION,
                e_total_flux DOUBLE PRECISION,
                peak_flux DOUBLE PRECISION,
                e_peak_flux DOUBLE PRECISION,
                ra_max DOUBLE PRECISION,
                e_ra_max DOUBLE PRECISION,
                dec_max DOUBLE PRECISION,
                e_dec_max DOUBLE PRECISION,
                maj DOUBLE PRECISION,
                e_maj DOUBLE PRECISION,
                min DOUBLE PRECISION,
                e_min DOUBLE PRECISION,
                pa DOUBLE PRECISION,
                e_pa DOUBLE PRECISION,
                dc_maj DOUBLE PRECISION,
                e_dc_maj DOUBLE PRECISION,
                dc_min DOUBLE PRECISION,
                e_dc_min DOUBLE PRECISION,
                dc_pa DOUBLE PRECISION,
                e_dc_pa DOUBLE PRECISION,
                code TEXT,
                assoc_id INTEGER,
                PRIMARY KEY (src_id, image_id),
                FOREIGN KEY (isl_id, image_id)
                  REFERENCES detected_island (isl_id, image_id)
                  ON DELETE CASCADE
            );

            CREATE TABLE corrected_flux (
                src_id INTEGER NOT NULL,
                isl_id INTEGER NOT NULL,
                image_id INTEGER NOT NULL,
                total_flux DOUBLE PRECISION,
                e_total_flux DOUBLE PRECISION,
                peak_flux DOUBLE PRECISION,
                e_peak_flux DOUBLE PRECISION,
                isl_total_flux DOUBLE PRECISION,
                isl_e_total_flux DOUBLE PRECISION,
                isl_rms DOUBLE PRECISION,
                isl_mean DOUBLE PRECISION,
                isl_resid_rms DOUBLE PRECISION,
                isl_resid_mean DOUBLE PRECISION,
                PRIMARY KEY (src_id, image_id),
                FOREIGN KEY (src_id, image_id)
                  REFERENCES detected_source (src_id, image_id)
                  ON DELETE CASCADE,
                FOREIGN KEY (isl_id, image_id)
                  REFERENCES detected_island (isl_id, image_id)
                  ON DELETE CASCADE
            );

            CREATE TABLE catalog_match (
                id SERIAL NOT NULL,
                catalog_id INTEGER,
                src_id INTEGER,
                assoc_id INTEGER,
                min_deRuiter DOUBLE PRECISION,
                PRIMARY KEY (id),
                FOREIGN KEY (assoc_id)
                  REFERENCES assoc_source (id)
                  ON DELETE CASCADE,
                UNIQUE (catalog_id, src_id, assoc_id)
            );

            CREATE TABLE vlite_unique (
                id SERIAL NOT NULL,
                image_id INTEGER,
                assoc_id INTEGER,
                detected BOOLEAN,
                PRIMARY KEY (id),
                FOREIGN KEY (image_id)
                  REFERENCES image (id)
                  ON DELETE CASCADE,
                FOREIGN KEY (assoc_id)
                  REFERENCES assoc_source (id)
                  ON DELETE CASCADE
            );

            CREATE INDEX ON detected_source (q3c_ang2ipix(ra, dec))
                WITH (fillfactor = 90);
            CREATE INDEX ON assoc_source (q3c_ang2ipix(ra, dec))
                WITH (fillfactor = 90);
            ''')
        cur.execute(sql)
        
        # Make error table
        make_error(cur)

        conn.commit()

        # Triggers
        sql = (
            '''
            CREATE OR REPLACE FUNCTION update_assoc_func() 
              RETURNS trigger AS $$
            BEGIN
              DELETE FROM assoc_source
              WHERE id = OLD.assoc_id AND ndetect = 1;
              UPDATE assoc_source SET 
                ra = (1./((1./(e_ra*e_ra))-(1./(OLD.e_ra*OLD.e_ra))))*(
                  (ra/(e_ra*e_ra))-(OLD.ra/(OLD.e_ra*OLD.e_ra))),
                e_ra = SQRT(1./((1./(e_ra*e_ra))-(1./(OLD.e_ra*OLD.e_ra)))),
                dec = (1./((1./(e_dec*e_dec))-(1./(OLD.e_dec*OLD.e_dec))))*(
                  (dec/(e_dec*e_dec))-(OLD.dec/(OLD.e_dec*OLD.e_dec))),
                e_dec = SQRT(1./(
                  (1./(e_dec*e_dec))-(1./(OLD.e_dec*OLD.e_dec)))),
                ndetect = ndetect - 1
              WHERE id = OLD.assoc_id;
            RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER update_assoc
              AFTER DELETE ON detected_source
              FOR EACH ROW
              EXECUTE PROCEDURE update_assoc_func();
            ''')

        cur.execute(sql)

        sql = (
            '''
            CREATE OR REPLACE FUNCTION remove_vu_func()
              RETURNS TRIGGER AS $$
            BEGIN
              DELETE FROM vlite_unique WHERE assoc_id = OLD.id;
            RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER remove_vu
              AFTER UPDATE OF nmatches ON assoc_source
              FOR EACH ROW
              WHEN (OLD.nmatches = 0 AND NEW.nmatches = 1)
              EXECUTE PROCEDURE remove_vu_func();
            ''')
        
        cur.execute(sql)

        sql = (
            '''
            CREATE OR REPLACE FUNCTION update_detected_func()
              RETURNS TRIGGER AS $$
            BEGIN
              UPDATE detected_source SET assoc_id = -1
              WHERE assoc_id = OLD.id;
            RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER update_detected
              AFTER DELETE ON assoc_source
              FOR EACH ROW
              EXECUTE PROCEDURE update_detected_func();
            ''')
        
        cur.execute(sql)
        conn.commit()
        cur.close()

    else:
        print('\nAborting... database left unchanged.')


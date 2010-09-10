# smpl-repl #

Simple Replication (smpl-repl) is a configuration of MySQL and a utility script that will allow you to share row change events from your database to other programs on your network. smpl-repl creates INSERT/UPDATE/DELETE triggers on tables you specify that send out row change events over a Spread network. The events are encoded as JSON, and should contain sufficient metadata to allow you to replicate the database in any way you'd like. "But doesn't MySQL already have awesome replication?", you ask. It does, and if you're not running MySQL's master/slave replication, you're doing it wrong and you're going to lose data. The point of smpl-repl is not to replace your database or its native replication system. Rather, it is to provide a program-agnostic mechanism to share replication events with other applications in your stack.

Say you have a cache that you want to update/invalidate after a row is changed in the database, you can write a simple client that listens for relevant changes on the Spread network. Say you have a cluster of read-only Tokyo Tyrant instances on your network that you use for read scalability, a simple client on each cluster member can handle updating each instance for you, because Spread takes care of getting the message to all machines. Say you want to fire off a long-running job each time certain rows are altered, your client can wait for those events, and discard the rest. There are many use cases for which specific MySQL UDFs and triggers have been created. Rather than try to do everything in the database, I wanted a general way to get events out of the database, and leave what to do up to each client.

## How to use it: ##

Install Spread, MySQL, MesgApi Spread, and lib_mysqludf_json (see below for links).

Generate the triggers for your tables:

    > python smplrepl.py --user=root --passwd=passw0rd --schema=test --table=test --group=replication |mysql -u root -ppassw0rd test

Use the tables as you normally would:

    mysql> INSERT INTO test (name, value) VALUES ("shizzle", "nizzle");
    mysql> UPDATE test SET name="foo", value="bar" WHERE name="shizzle";
    mysql> DELETE FROM test WHERE name="foo";

Create a client that listens for Spread messages that contain the table change events.

## How it works: ##

smplrepl.py has the following command line arguments:

    -h, --host= (Database hostname. Defaults to 'localhost'.)
    -P, --port= (Database port. Defaults to '3306'.)
    -u, --user= (Database user.)
    -p, --passwd= (Database password.)
    -s, --schema= (Database schema.)
    -t, --tables= (Space delimited list of tables. Defaults to all tables available in the specified schema.)
    -g, --group= (Spread group to publish messages. Defaults to 'replication'.)

For the example in the first section above, smplrepl.py generates INSERT/UPDATE/DELETE triggers on the 'test' table in the 'test' schema. For the following table:

    CREATE TABLE test (
      test_id int(11) NOT NULL AUTO_INCREMENT,
      name varchar(255) NOT NULL,
      value varchar(255) DEFAULT NULL,
      modified timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (test_id),
      UNIQUE KEY name (name)
    ) ENGINE=InnoDB;

smplrepl.py will generate the following triggers:

    -- insert
    DROP TRIGGER IF EXISTS test_trigger_insert;
    DELIMITER |
    CREATE TRIGGER test_trigger_insert
    AFTER INSERT ON test
    FOR EACH ROW BEGIN
    SET @mm= send_mesg("replication",
    json_object(
      json_members(
        "schema", "test",
        "table", "test",
        "timestamp", now(),
        "operation", "insert",
        "primary", "test_id",
        "keys", json_array( "test_id","name" ),
        "columns", json_array( "test_id","name","value","modified" ),
        "new", json_object(
          json_members(
            "test_id", NEW.test_id,
            "name", NEW.name,
            "value", NEW.value,
            "modified", NEW.modified
          )
        )
      )
    )
    );
    END |
    DELIMITER ;
    
    -- update
    DROP TRIGGER IF EXISTS test_trigger_update;
    DELIMITER |
    CREATE TRIGGER test_trigger_update
    AFTER UPDATE ON test
    FOR EACH ROW BEGIN
    SET @mm= send_mesg("replication",
    json_object(
      json_members(
        "schema", "test",
        "table", "test",
        "timestamp", now(),
        "operation", "update",
        "primary", "test_id",
        "keys", json_array( "test_id","name" ),
        "columns", json_array( "test_id","name","value","modified" ),
        "new", json_object(
          json_members(
            "test_id", NEW.test_id,
            "name", NEW.name,
            "value", NEW.value,
            "modified", NEW.modified
          )
        ),
        "old", json_object(
          json_members(
            "test_id", OLD.test_id,
            "name", OLD.name,
            "value", OLD.value,
            "modified", OLD.modified
          )
        )
      )
    )
    );
    END |
    DELIMITER ;
    
    -- delete
    DROP TRIGGER IF EXISTS test_trigger_delete;
    DELIMITER |
    CREATE TRIGGER test_trigger_delete
    AFTER DELETE ON test
    FOR EACH ROW BEGIN
    SET @mm= send_mesg("replication",
    json_object(
      json_members(
        "schema", "test",
        "table", "test",
        "timestamp", now(),
        "operation", "delete",
        "primary", "test_id",
        "keys", json_array( "test_id","name" ),
        "columns", json_array( "test_id","name","value","modified" ),
        "old", json_object(
          json_members(
            "test_id", OLD.test_id,
            "name", OLD.name,
            "value", OLD.value,
            "modified", OLD.modified
          )
        )
      )
    )
    );
    END |
    DELIMITER ;

So, every time a row is changed in these tables, a message will be published to the 'replication' Spread message group. The JSON message will have a format similar to the following example:

    {
        "schema": "test",
        "table": "test",
        "timestamp": "2010-09-09 13:00:10",
        "operation": "update",
        "primary": "test_id",
        "keys": [ "test_id", "name" ],
        "columns": [ "test_id", "name", "value", "modified" ],
        "new":
        {
            "test_id": "1",
            "name": "foo",
            "value": "bar",
            "modified": "2010-09-09 13:00:10"
        },
        "old":
        {
            "test_id": "1",
            "name": "shizzle",
            "value": "nizzle",
            "modified": "2010-09-09 13:00:10"
        }
    }

The 'new' and 'old' object values are only both present in the 'update' operation message. For 'insert', only 'new' is present, and for 'delete', only 'old' is present. All other metadata fields ('schema', 'table', 'timestamp', 'operation', 'primary', 'keys', and 'columns') are always present.

## A sample client: ##

The following sample client listens on the Spread network for messages published tou the 'replication' group, and prints them to stdout:

    import spread
    import types
    
    sprconn = spread.connect('4803')
    sprconn.join('replication')
    
    while 1:
        msg = sprconn.receive()
        t = type(msg)
        if t.__name__!="MembershipMsg":
            print msg.message

A more useful example is to use the message to load the changed values into a Tokyo Tyrant database by primary key:

    import pytyrant
    import spread
    import simplejson as json
    import types
    
    sprconn = spread.connect('4803')
    sprconn.join('replication')
    tyconn = pytyrant.Tyrant.open()
    
    while 1:
        msg = sprconn.receive()
        t = type(msg)
        if t.__name__!="MembershipMsg":
            obj = json.loads(msg.message)
    	if obj['operation']=="insert" or obj['operation']=="update":
    	    tyconn.put(obj['new'][obj['primary']], obj['new'])
    	if obj['operation']=="delete":
    	    tyconn.out(obj['new'][obj['primary']])

These samples are written in Python, but you can write your clients in any language that has a Spread library: <http://www.spread.org/SpreadPlatforms.html>

## What you need: ##

### Database: ###
* Spread 4 <http://www.spread.org/>
* MySQL 5.1.* <http://www.mysql.com/>
* MesgApi Spread <http://forge.mysql.com/wiki/MesgApi_Spread>
* lib_mysqludf_json <http://www.mysqludf.org/lib_mysqludf_json/>

### Utils: ###
* Python 2.4+ <http://www.python.org/>
* MySQLdb <http://sourceforge.net/projects/mysql-python/>

### Samples: ###
* Python 2.4+ <http://www.python.org/>
* simplejson <http://www.undefined.org/python/>
* Python Spread <http://www.zope.org/Members/tim_one/spread/view>
* pytyrant <http://code.google.com/p/pytyrant/>


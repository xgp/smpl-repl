import sys
import getopt
import MySQLdb

def main(argv):
    host = "localhost"
    port = 3306
    user = ""
    passwd = ""
    schema = "test"
    tables = "*"
    group = "replication"
    try:
        opts, args = getopt.getopt(argv, "h:P:u:p:s:t:g:", ["host=", "port=", "user=", "passwd=", "schema=", "tables=", "group="]) 
    except getopt.GetoptError:
        #TODO: usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--host"):
            host = arg
        if opt in ("-P", "--port"):
            port = int(arg)
        if opt in ("-u", "--user"):
            user = arg
        if opt in ("-p", "--passwd"):
            passwd = arg
        if opt in ("-s", "--schema"):
            schema = arg
        if opt in ("-t", "--tables"):
            tables = arg.split(" ")
        if opt in ("-g", "--group"):
            group = arg
    #TODO: validate that sufficient arguments are given
            
    conn = MySQLdb.connect(host=host, port=port, user=user, passwd=passwd, db=schema)
    cursor = conn.cursor()
    tbls = []
    if tables=="*":
        cursor.execute("show tables")
        results = cursor.fetchall()
        for row in results:
            tbls.append(row[0])
    else:
        for t in tables:
            tbls.append(t)
    for tbl in tbls:
        sql = "DESC %s" % (tbl)
        cursor.execute(sql)
        results = cursor.fetchall()
        pri = ""
        keys = []
        cols = []
        for row in results:
            if (row[3]=="PRI"): pri = row[0]
            if (row[3]!=""): keys.append(row[0])
            cols.append(row[0])
        print """%s
%s
%s""" % ( create_trigger(schema, tbl, pri, keys, cols, group, "insert", True, False), create_trigger(schema, tbl, pri, keys, cols, group, "update", True, True), create_trigger(schema, tbl, pri, keys, cols, group, "delete", False, True) )

def create_trigger(schema, table, pri, keys, cols, group, operation, new_obj=False, old_obj=False):
    tri = """-- %s
DROP TRIGGER IF EXISTS %s;
DELIMITER |
CREATE TRIGGER %s
AFTER %s ON %s
FOR EACH ROW BEGIN
SET @mm= send_mesg("%s",
json_object(
  json_members(
    "schema", "%s",
    "table", "%s",
    "timestamp", now(),
    "operation", "%s",
    "primary", "%s",
    "keys", json_array( %s ),
    "columns", json_array( %s ),
%s
  )
)
);
END |
DELIMITER ;
""" % ( operation, get_trigger_name(table, operation), get_trigger_name(table, operation), operation.upper(), table, group, schema, table, operation, pri, get_param_list(keys), get_param_list(cols), create_obj(cols, new_obj, old_obj) )
    return tri

def get_trigger_name(table, operation):
    return "%s_trigger_%s" % (table, operation);

def get_param_list(ls):
    if len(ls) <= 1: return "\"%s\"" % (ls[0])
    ns = []
    for l in ls:
        ns.append("\"%s\"" % (l))
    return ",".join(ns)

def create_obj(cols, new_obj=False, old_obj=False):
    n = []
    if new_obj:
        o = []
        for c in cols:
            o.append("\n        \"%s\", NEW.%s" % (c,c))
        n.append("""    "new", json_object(
      json_members(%s
      )
    )""" % ( ",".join(o) ))
    if old_obj:
        o = []
        for c in cols:
            o.append("\n        \"%s\", OLD.%s" % (c,c))
        n.append("""    "old", json_object(
      json_members(%s
      )
    )""" % ( ",".join(o) ))
        return ",".join(n)
    else:
        return n[0]


if __name__ == "__main__":
    main(sys.argv[1:])

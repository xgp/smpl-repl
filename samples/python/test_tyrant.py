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

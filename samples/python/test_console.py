import spread
import types

sprconn = spread.connect('4803')
sprconn.join('replication')

while 1:
    msg = sprconn.receive()
    t = type(msg)
    if t.__name__!="MembershipMsg":
        print msg.message

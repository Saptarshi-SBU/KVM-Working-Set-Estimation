import time
# Balloon Driver Events 

  # balloon events
RFLT_RDS   = 0
PSWPOUT    = 1
ACTUAL     = 2
FREERAM    = 3
DISK_RDS   = 4
PGMAJFAULT = 5
TOTALRAM   = 6
PSWPIN     = 7
PGFAULT    = 8
COMMITTED  = 9
DMA_RDS    = 10


list = [];
param = ['PSWPOUT','ACTUAL','FREERAM','PGMAJFAULT','TOTALRAM','PSWPIN', 'PGFAULT', 'COMMITTED'];

def parse_balloon_stat(string) :
        global list
        list = [];
	string = str(string); 
        string = string.split(': {');
	#print string
	string = string[1];
	#print string
        string = string.split(',');
        for i in string :
	    if '{' in i :
	        i = i.replace("{","");	
	    if '}' in i :
	        i = i.replace("}","");	
            k= i.split(':');
            list.append(k[1])
	if " u'DeviceNotActive'" in list :
	    print 'ERR : Balloon Device Missing !'
	    time.sleep(1000)
        #print list

def read_balloon_stat(val) :
        global list
	global param
        if isinstance(val,int) == True : 
           #print  param[val] + "\t "  + str(long(list[val]))
	   #print val
           return long(list[val])
        else :
           print ' [read ballon stat] : invalid argument] '
           return -1;
        


#string = "{u'pswpout': 166293504, u'actual': 4294967296, u'freeram': 1562214400, u'pgmajfault': 18439, u'totalram': 4147392512, u'pswpin': 38506496, u'pgfault': 11568283, u'committed_as': 525268}"
#parse_balloon_stat(string)
#for k in range(0,8) :
#   val = read_balloon_stat(k)
#   print val;
#   print k


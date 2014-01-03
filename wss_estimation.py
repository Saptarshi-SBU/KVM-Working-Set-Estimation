#-------------------------------------------------------------------------------
# Copyright (c) 2013 ITRI Taiwan
# All Rights Reserved
#
# Module For  Work Set Estimation  
#
#-------------------------------------------------------------------------------

import balloon_stat
import time
import math
import os

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

  # fsm states
INIT_STATE = 4
FAST_STATE = 0 
COOL_STATE = 2
SLOW_STATE = 1
TERMINATE  = 3
INVALID_STATE = -1;

 # PAGE SHIFT USED IN GUEST  DRIVER 
PGOFF = 12

  #error handles (to be extended in later releases)
SUCCESS = 0
ERROR   = -1
DEBUG  = 0

#------------------------------------ START OF System Critical Parameters----------------------------------------------

#  The following fast and slow state parameters which have been used has been tabulated

#  FAST_STATE		SLOW_STATE
#  0.05			0.01
#  0.01			0.005
#  0.01			0.0025
#  0.01			0.00025
	
SLOW_RATE  = .00025
#SLOW_RATE  = .025
#SLOW_RATE  = .0025
#FAST_RATE  = .1
FAST_RATE  = .05

# Free Ram Limit is a critical system parameter. The following ram limits has been tried      
FREE_RAM_LIMIT          = 5

# Cool Time Out Period in Seconds
COOL_TIME_OUT 	 	= 30

# Cool Time Out Period in Seconds
SLOW_TIME_OUT 	 	= 5

# Acceptable degree of change in committed_AS 
LIMIT_CAS_VAR           = 150 << 20

# to  maintain the min_free_bytes
BALLOON_MEM_LIMIT       = 400 << 20

#------------------------------------ END OF System Critical Parameters-------------------------------------------------
#Update rates from the guest Much impact has not been seen by increasing the update rates. See report

FAST_EPOCH              = 1
SLOW_EPOCH              = 1 
COOL_EPOCH              = 1

#INIT TIMINGS
KERNEL_BOOT_TIME        = 15  #sec

MIN_PAGES 		= 32

#For Print
fsm_state = ['FAST_STATE' , 'COOL_STATE' , 'SLOW_STATE']
kick_rate = [ FAST_EPOCH, COOL_EPOCH , SLOW_EPOCH]
swap_rate = ['N','H']
 
# Globals all old(s) are the previous MEASUREMENT and new(s) the current MEASUREMENT

old_bz	=-1    
new_bz	=-1
del_bz	=-1
old_cas =-1
new_cas =-1
del_cas =-1
old_swp =-1
old_swp_out = -1
new_swp_out = -1
del_swp_out = -1
new_swp =-1
swp_kck =0
swp_clk =-1
old_swp_in=-1
new_swp_in=-1
del_swp_in=-1
old_majflt=-1
new_majflt=-1
old_miniflt=-1
new_miniflt=-1
del_miniflt=-1
old_rflt=-1
new_rflt=-1
del_rflt=-1
swap_space=0
old_rbtime=0
new_rbtime=0
rb_scale=1
avg=0
# SCP
old_active_pg = -1
new_active_pg = -1
del_active_pg = 0
  # Experiment Start Time (For logging)
f=0

INIT_TIME=-1

# This fucntion  
#                1) Initializes self object parameters to default and sets fsm to FAST STATE
#                2) Kicks the guest virtio driver
#                3) Polls the guest driver for stats
#                4) Initlialize the balloon to the current CAS
#                5) Updates the new(s) globals with values
#                6) Finally update the difference table

def __kinit(self, qemu) :

	global old_bz
	global old_swp 
	global old_swp_in
	global old_majflt
	global old_miniflt
	global old_swp_out
	global old_cas
	global old_rflt
	#SCP
	global old_active_pg
	global new_rflt
	global del_swp
	global del_swp_out
	global del_majflt
	global del_miniflt
	#SCP
	global del_active_pg
	global INIT_TIME
	global f
	global q

	if DEBUG == 0 :
		print 'kinit'

	# Default Values

	self.state 		     = FAST_STATE
	self.fast_rate		     = FAST_RATE
	self.slow_rate		     = SLOW_RATE
	self.fast_epoch		     = -1
	self.cool_epoch		     = -1
	self.slow_epoch		     = -1
	self.do_wss		     = False
	self.wss                     = -1
        self.guest_interface         = qemu;
	self.total_ram               = -1
	self.rds                     = -1
	self.dma_rds		     = -1;
	self.rflt_rds		     = -1;
	self.miniflt                 = -1;
	#SCP
	self.majflt                  = -1;
	avg			     = 0;

	while self.total_ram <= 0 :
	      if DEBUG == 0 :
	         print 'KVM_AUTO_BALLON INIT : kicking guest driver'
	      time.sleep(KERNEL_BOOT_TIME)
	      kset_kickrate(self)
	      if kread_stat(self) == ERROR :
	         print 'ERR kread_stat'
                 return ERROR
	print 'Balloon Active '
        f=open("WSS_LOG_"+str(time.time()),"w");

	__ksave(self)
	# After Today discussion with Brian
	#self.desired_bz		     = (self.committed_as >> PGOFF ) << PGOFF
	self.desired_bz	     = self.balloon_size
	if kis_crit(self) == True :
           self.desired_bz=kfloor(self)
        kset_bz(self)
	kread_stat(self)
	knew(self)
	INIT_TIME                    = time.time()
	print 'Started Logging\n'
	kupdate_table(self)
	if (del_swp > 0 or (del_rflt  > 0 )): 
	   self.state = COOL_STATE

	return SUCCESS

# This fucntion should be at the init
def __ksave(self) :

	global old_bz
	global old_cas
	global old_swp
	global old_swp_out
	global old_swp_in
	global old_majflt
	global old_miniflt
	global old_rflt

	old_bz		             = self.balloon_size # should be equal to the total ram
	old_swp			     = self.pswpin + self.pswpout;
	old_swp_out		     = self.pswpout
	old_swp_in		     = self.pswpin
	old_majflt                   = self.majflt
	old_miniflt                  = self.miniflt;
	old_cas			     = self.committed_as;
	old_rflt		     = self.rflt_rds;
	
        return SUCCESS

# Update Measurements	

def knew(self) :

	global new_bz
	global new_swp
	global new_swp_out
	global new_swp_in
	global new_majflt
	global new_miniflt
	global new_cas
	global new_rflt

	new_bz		             = self.balloon_size
	new_swp			     = self.pswpin + self.pswpout;
	new_swp_out		     = self.pswpout
	new_swp_in		     = self.pswpin
	new_majflt                   = self.majflt
	new_cas			     = self.committed_as;
	new_rflt		     = self.rflt_rds;	
	new_miniflt                  = self.miniflt;
	return SUCCESS


# This function reads stats generated by the Guest Balloon driver 
# as well as from QEMU User-Space IDE device driver for refault stats

def kread_stat(self) :

	if DEBUG ==1 :
		print '[ kread_stat ]'

        ret                          = QMP_query_balloon(self);
	if ret == None :
	   print 'ERR :[ kread_stat ]'    
           return ERROR
        balloon_stat.parse_balloon_stat(ret);	

	
        self.pswpin                  = balloon_stat.read_balloon_stat(PSWPIN);
        self.pswpout                 = balloon_stat.read_balloon_stat(PSWPOUT);
        self.freeram                 = balloon_stat.read_balloon_stat(FREERAM);
        self.committed_as            = balloon_stat.read_balloon_stat(COMMITTED)*1024;
        self.balloon_size            = balloon_stat.read_balloon_stat(ACTUAL);
        self.total_ram               = balloon_stat.read_balloon_stat(TOTALRAM);
        self.majflt                  = balloon_stat.read_balloon_stat(PGMAJFAULT); #now number of guest active pages
        self.rflt_rds                = balloon_stat.read_balloon_stat(PGFAULT);
	self.miniflt                 = balloon_stat.read_balloon_stat(PGFAULT);

	if DEBUG ==1 :
	   print ' [ kread_stat ] Total RAM : '    + str(self.total_ram)

	return SUCCESS

# This function 
#	1) update the restore_size variable
#       2) compute the delta of parameters
#       3) update old and new values for the next set of measuremt
#          msr-->new--->old-->restore 

def kupdate_table(self) :

	global old_bz
	global new_bz
	global del_bz
	global old_cas
	global new_cas
	global del_cas
	global old_swp
	global old_swp_out
	global old_swp_in
	global old_majflt
	global old_miniflt
	global old_rflt
	global new_rflt
	global new_swp
	global new_swp_out
	global new_swp_in
	global new_majflt
	global new_miniflt
	global del_swp
	global del_swp_out
	global del_swp_in
	global del_majflt
	global swp_kck
	global kick_rate
	global swap_rate
	global del_rflt
	global INIT_TIME
	global f
	global avg

	del_bz			     = old_bz-new_bz
	self.restore_bz              = old_bz
	old_bz                       = new_bz

	del_cas			     = min(new_cas-old_cas,self.total_ram) 
	old_cas			     = new_cas

	del_swp			     = new_swp-old_swp
	old_swp			     = new_swp
	
	del_swp_out		     = new_swp_out-old_swp_out
	old_swp_out		     = new_swp_out

	del_swp_in		     = new_swp_in-old_swp_in
	old_swp_in		     = new_swp_in

	del_majflt		     = new_majflt-old_majflt
	old_majflt                   = new_majflt

	del_miniflt		     = new_miniflt-old_miniflt
	old_miniflt                  = new_miniflt

	del_rflt		     = new_rflt-old_rflt
	old_rflt                     = new_rflt

	avg                          = (avg+del_majflt)/2;

	#only for logging
	string_line  = str(self.state*1000)+" "
	string_line  = string_line + str(kick_rate[self.state])+ " "
	string_line  = string_line + str(self.restore_bz/(1024*1024))+"\t"
	string_line  = string_line + str(long(self.desired_bz/(1024*1024)))+"\t"
	string_line  = string_line + str(self.balloon_size/(1024*1024))+"\t"
	string_line  = string_line + str(del_bz/(1024*1024))+"M\t"
	string_line  = string_line + str(del_swp_in/1024)+"K\t"
	string_line  = string_line + str(del_swp_out/1024)+"K\t"
	string_line  = string_line + str(del_majflt)+"\t"
	string_line  = string_line + str(avg)+"\t"
	string_line  = string_line + str(del_rflt*4)+"K\t"
	string_line  = string_line + str(self.freeram/(1024*1024))+"\t"
	string_line  = string_line + str(self.committed_as/(1024*1024))+"\t"
	string_line  = string_line + str(time.time()-INIT_TIME)
        print string_line
        
	f.write(string_line+str("\n"));
	return SUCCESS
 
def kis_setkick(self) :
	if self.state == FAST_STATE and self.fast_epoch == FAST_EPOCH :
	      return True 
	if self.state == COOL_STATE and self.cool_epoch == COOL_EPOCH :
	      return True 
	if self.state == SLOW_STATE and  self.slow_epoch == SLOW_EPOCH :
	      return True 
	return False

# Invalidate the Update Rate for a FSM State.
def kunset_kickrate(self):
	
	if self.state == FAST_STATE :
	   self.fast_epoch = -1	
	if self.state == COOL_STATE :
	   self.cool_epoch = -1	
	if self.state == SLOW_STATE :
	   self.slow_epoch = -1	
	
# Set the Update Rate for a FSM State
def kset_kickrate(self) :

	global FAST_EPOCH
	global COOL_EPOCH
	global SLOW_EPOCH

	if self.state == FAST_STATE : 
	   self.fast_epoch	     = FAST_EPOCH
	   ret 			     = QMP_balloon_set_epoch(self,self.fast_epoch);
	elif self.state == COOL_STATE :
	   self.cool_epoch 	     = COOL_EPOCH
	   ret			     = QMP_balloon_set_epoch(self,self.cool_epoch);
	elif self.state == SLOW_STATE :	
	   self.slow_epoch	     = SLOW_EPOCH
	   ret			     = QMP_balloon_set_epoch(self,self.slow_epoch);
        if ret == ERROR :
	   print 'BUG[kset_kickrate]'
	   sys.exit(0)
	return SUCCESS

# This function is called to inflate the balloon

def kset_bz(self) :

	global new_bz
        ret = QMP_set_balloon_target(self,self.desired_bz);
        if ret == ERROR :
	   print 'BUG [ kset_bz]'
	   sys.exit(0)
        return SUCCESS

# This function is called to deflate the balloon
# The deflate function is based on three parameters :
#	a) Swap
#	b) Refault
#	c) Increase in Active Memory

def kest_rollback(self) :

	global del_rflt
	global del_majflt
	global del_swp
	global del_swp_out
	global new_cas
	global del_cas
	global avg

	if del_cas >= LIMIT_CAS_VAR :
	   if avg > 0 :	
	      #self.desired_bz = (min(max(new_cas,self.balloon_size)+del_swp_out+del_rflt*4*1024+avg*4*1024 + (100 << 20)*(200 << 20)/self.freeram, self.total_ram)/1024)*1024 	
	      self.desired_bz = (min(max(new_cas,self.balloon_size), self.total_ram)/1024)*1024 	
	   else :
	      #self.desired_bz = (min(max(new_cas,self.balloon_size)+del_swp_out+del_rflt*4*1024 + (100 << 20)*(200 << 20)/self.freeram, self.total_ram)/1024)*1024 	
	      self.desired_bz = (min(max(new_cas,self.balloon_size), self.total_ram)/1024)*1024 	
	else :
           if avg > 0 :
	      self.desired_bz = (min(self.balloon_size + del_swp_out + del_rflt*4*1024 + max(del_cas,0)+(avg*4*1024) + (10 << 20)*(200 << 20)/(self.freeram), self.total_ram) >> PGOFF ) << PGOFF 
	   else :
	      self.desired_bz = (min(self.balloon_size + del_swp_out + del_rflt*4*1024 + max(del_cas,0) + (10 << 20)*(200 << 20)/(self.freeram), self.total_ram) >> PGOFF ) << PGOFF 

        return SUCCESS

# Estimate balloon size
def kest_bz(self) :

	global old_bz

	if self.state == INIT_STATE :
           self.desired_bz             = self.committed_as;
	elif self.state == FAST_STATE :
	   r = self.fast_rate
           self.desired_bz             = (long(old_bz - (self.freeram *r)) >> PGOFF ) << PGOFF;
	elif self.state == SLOW_STATE :
	   r = self.slow_rate
           self.desired_bz             = (long(old_bz - (self.freeram *r)) >> PGOFF ) << PGOFF;
	else :
	   print 'BUG [kest_bz]'
	   sys.exit(0)	
	return SUCCESS

# FSM  Initialization State
# This function is called only if the CAS is more than
# the current balloon-target 

def kre_init_bz(self) :

        global old_bz
        global del_cas 
        global new_cas 
	if del_cas < 0 :
	   print 'BUG del_cas < 0 '
	   sys.exit(0)
	
	self.state = FAST_STATE
	if kis_setkick(self) == False :
	   kset_kickrate(self)
	self.desired_bz	    = ((new_cas >> PGOFF) << PGOFF);#base new cal frm here
	if kis_crit(self) == True :
           self.desired_bz=kfloor(self)
	kset_bz(self)
	kread_stat(self)
	knew(self)
	kupdate_table(self)
	return SUCCESS

def kis_crit(self) :
	if self.desired_bz < BALLOON_MEM_LIMIT:
	   return True
	else :
	   return False	

def kfloor(self) :
        return BALLOON_MEM_LIMIT


# Core of Ballooning

# Transition From Fast State

def kfaststate(self) :
        global del_swp
	global del_rflt
	global del_majflt
	global del_cas
	global new_cas
	global avg

	self.state = FAST_STATE
	if kis_setkick(self) == False :
	   kset_kickrate(self)

	if del_cas > LIMIT_CAS_VAR  and self.balloon_size < new_cas :
	   kre_init_bz(self)
	   return FAST_STATE

	elif (del_swp_out > 0) or ((del_rflt > 0) and ((100 * self.freeram/self.total_ram) < FREE_RAM_LIMIT)): 
	#elif (del_swp_out > 0) or (del_rflt > 0) : 
	   kunset_kickrate(self)
	   return COOL_STATE

	kest_bz(self)
	if kis_crit(self) == True :
	      self.desired_bz=kfloor(self)
	kset_bz(self)
	kread_stat(self)
	knew(self)
	kupdate_table(self)

	if ((100 * self.freeram/self.total_ram) < FREE_RAM_LIMIT):
	   kunset_kickrate(self)
	   return SLOW_STATE

	elif ((100 * self.freeram/self.total_ram) < FREE_RAM_LIMIT) and avg  > MIN_PAGES:
	   kunset_kickrate(self)
	   return COOL_STATE

	else :
	   return FAST_STATE

# Transition to Cool State
ZTIMER   = 0
def kcoolstate(self) :
	global del_cas
	global new_cas
	global del_swp
	global del_rflt
	global del_majflt
	global ZTIMER
	global avg

	self.state = COOL_STATE
	kset_kickrate(self)

	if del_cas > LIMIT_CAS_VAR and new_cas > self.balloon_size: 

	   ZTIMER=0
           kunset_kickrate(self)
           kre_init_bz(self)
           return FAST_STATE

	elif (del_swp_out > 0) or ((del_rflt > 0)  and ((100 * self.freeram/self.total_ram) < FREE_RAM_LIMIT)):
	#elif (del_swp_out > 0) or (del_rflt > 0) :  

	   ZTIMER=0
	   kest_rollback(self)
	   if kis_crit(self) == True :
	      self.desired_bz=kfloor(self)
	   kset_bz(self)
	   kread_stat(self)
	   knew(self)
	   kupdate_table(self)
	   #time.sleep(COOL_EPOCH)	
	   return COOL_STATE

	else :

	   ZTIMER = ZTIMER + 1
	   if avg > MIN_PAGES and ((100 * self.freeram/self.total_ram) < FREE_RAM_LIMIT):
	      ZTIMER = 0	
	   kread_stat(self)
	   knew(self)
	   kupdate_table(self)

	   if ZTIMER > COOL_TIME_OUT :
	      ZTIMER=0
	      time.sleep(COOL_EPOCH)	
	      kunset_kickrate(self)
	      return SLOW_STATE	
	   else :
	      time.sleep(COOL_EPOCH)	
	      return COOL_STATE	

# Transition from Slow State
STIMER=0
def kslowstate(self) :
	global del_cas
	global del_rflt 
	global del_majflt
	global del_swp
	global new_cas
	global avg
	global STIMER

	self.state = SLOW_STATE
	if kis_setkick(self) == False :
	   kset_kickrate(self)

	kest_bz(self)
	if kis_crit(self) == True :
	   self.desired_bz=kfloor(self)
	kset_bz(self)
	kread_stat(self)
	knew(self)
	kupdate_table(self)

	STIMER=STIMER+1
        if STIMER > SLOW_TIME_OUT  :
	      STIMER = 0
	      kunset_kickrate(self)
	      return FAST_STATE
	if avg > MIN_PAGES :
	   STIMER=0

	if del_cas > LIMIT_CAS_VAR and self.balloon_size < new_cas :
		 STIMER = 0
	         kunset_kickrate(self)
	         kre_init_bz(self)
	         return FAST_STATE
        elif (del_swp_out > 0) or ((del_rflt > 0) and ((100 * self.freeram/self.total_ram) < FREE_RAM_LIMIT)) :  
        #elif (del_swp_out > 0) or (del_rflt > 0)  :  
		 STIMER = 0
	   	 kunset_kickrate(self)
           	 return COOL_STATE;
	elif ((100 * self.freeram/self.total_ram) > FREE_RAM_LIMIT) :
		 STIMER = 0
	         kunset_kickrate(self)
	         return FAST_STATE
	else :
		 return SLOW_STATE
	       
def kmainloop(self,qemu) :

       __kinit(self,qemu)
                        
       while True :
        ret = kread_stat(self);
        knew(self)
        ret = kupdate_table(self);
        time.sleep(1) 
        
       while True :

          next_state = kselectstate(self);
          if next_state == INVALID_STATE :
             return INVALID_STATE;
          elif next_state == TERMINATE  :
             break;
          elif next_state == ERROR :
             return ERR; 
	  else:
	     self.state = next_state

       self.actual_wss  = self.balloon_size;  
       print 'WSS (kb) : ' + str(self.actual_wss/1024)
       return self.actual_wss 

def kselectstate(self) :
	if self.state == FAST_STATE :
	   return kfaststate(self)
	elif self.state == COOL_STATE :
	   return kcoolstate(self)
	elif self.state == SLOW_STATE :
	   return kslowstate(self)
	else:
	   print 'BUG[kselectstate] '

# QMP Support Functions

def QMP_set_balloon_target(self,value) :
        cmdline = "balloon value=";
	
        new_val = int(value);
        cmdline+=str(new_val);
        #print cmdline
        ret     = self.guest_interface._execute_cmd(cmdline);
	time.sleep(1)
        return 	SUCCESS;

def QMP_query_balloon(self) :
        cmdline = "query-balloon"
        #print cmdline
        ret     = self.guest_interface._execute_cmd(cmdline)
	return ret;
        
def QMP_balloon_set_epoch(self, val) :
        cmdline = "balloon-set-epoch value="
	new_val = int(val);
        cmdline+= str(new_val)
        #print cmdline
        ret = self.guest_interface._execute_cmd(cmdline)
        return SUCCESS
def QMP_query_ideinfo(self) :
        cmdline = "query-ideinfo"
        #print cmdline
        ret     = self.guest_interface._execute_cmd(cmdline)
        return ret	
	

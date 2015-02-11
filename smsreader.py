#!/bin/env python2

import os
import pickle
import time

import gammu

class Color:
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    DARK_CYAN = '\033[36m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = "\033[1m"
    UNDERLINE = '\033[4m'
    END = "\033[0m"
    
class SMS():
    
    def __init__(self, subj, from_no, date, msg, udh = None):
        self.subj = subj
        self.from_no = from_no
        self.date = date
        self.msg = msg
        self.udh = udh
    
    def __eq__(self, sms2):
        try:
            if self.subj != sms2.subj or self.from_no != sms2.from_no \
                or self.date != sms2.date or self.msg != sms2.msg \
                or self.udh != sms2.udh:
                return False
        except AttributeError:
            return False
        return True
    
    def __repr__(self):
        return "Subj : %s, From: %s, Date: %s" % (
                self.subj, self.from_no, self.date.strftime('%Y-%m-%d %H:%M:%S'))


class CSMS():
    
    def __init__(self, parts_count):
        self.parts_count = parts_count
        self.parts = {}
    
    def addpart(self, sms):
        partid = sms.udh['PartNumber']
        self.parts[partid] = sms
        
    def getfullsms(self):
        if self.parts_count == len(self.parts):
            smsparts = [None] * self.parts_count
            for key, value in self.parts.items():
                smsparts[key - 1] = value
                
            msgparts = []
            for i in smsparts:
                msgparts.append(i.msg)
            sms = SMS(smsparts[0].subj, smsparts[0].from_no, smsparts[-1].date, 
                      "".join(msgparts))
            return sms
        else:
            return None 
            
class CSMSManager():
    
    def __init__(self):
        self.csmsmap = {}
    
    def addCSMSpart(self, sms):
        id = sms.udh['ID16bit'] if sms.udh['ID16bit'] != -1 else sms.udh['ID8bit']
        
        try:
            self.csmsmap[id].addpart(sms)
        except KeyError:
            csms = CSMS(sms.udh['AllParts'])
            csms.addpart(sms)
            self.csmsmap[id] = csms 
                                   
    def getreadyCSMS(self):
        smses = []
        dels = []
        for key, value in self.csmsmap.items():
           sms = value.getfullsms()
           if sms:
               dels.append(key)
               smses.append(sms)
        for d in dels:
            del self.csmsmap[d]
        return smses 
                

class SMSReader():
    
    def __init__(self):
        sms_folder = os.getcwd()
        if not os.access(sms_folder + '/inbox', os.F_OK):
            os.mkdir(sms_folder + '/inbox')
        
        self.sms_folder = sms_folder
        self.sm = gammu.StateMachine()
        self.sm.ReadConfig(sms_folder + "/gammurc")
        
        self.csmsmanager = CSMSManager()
        
        self._lastreadsms = self.lastreadsms()
        self.location_flag = 0
        self.start_flag = 1
    
    def lastreadsms(self, sms=None):
        if sms:
            with open(self.sms_folder + "/lastmsg.pickle", "w") as f:
                pickle.dump(sms, f)
            self._lastreadsms = sms
        else:
            if os.access(self.sms_folder + "/lastmsg.pickle", os.F_OK):
                with open(self.sms_folder + "/lastmsg.pickle") as f:    
                    return pickle.load(f)
    
    def smstofile(self, sms):
        filename = sms.from_no + "_" + sms.date.strftime("%Y-%m-%d_%H:%M:%S")
        ext = ".sms"
        t = filename
        count = 1
        while True:
            if os.access(self.sms_folder + '/' + 'inbox/' + t + ext, os.F_OK):
                t = filename + "_" + str(count)
                count += 1
            else:
                break
        fullfile = self.sms_folder + '/' + 'inbox/' + t + ext
        print Color.BOLD + "Writing SMS to file: " + Color.END + str(sms) + Color.BOLD +  "\nFile location : " + Color.END + str(fullfile)  
        with open(fullfile, "w") as f:
            f.write(sms.from_no)
            f.write("\n")
            f.write(sms.msg)
        
    def start(self):
        self.connect()
        try:          
            while True:  
                smses = self.readinbox()
                if len(smses) > 0:
                    self.lastreadsms(smses[0])
                    for sms in smses:
                        if sms.udh:
                            self.csmsmanager.addCSMSpart(sms)
                        else:
                            self.smstofile(sms)
                    for sms in self.csmsmanager.getreadyCSMS():
                        self.smstofile(sms)
                print "Sleeping for 30 seconds..."
                time.sleep(30)
        finally:
            self.disconnect()
        
    def connect(self):
        self.sm.Init()

    def disconnect(self):
        self.sm.Terminate()
    
    def readinbox(self):
        print "Reading Inbox .."
        smses = []
        while True:
            sms = self._readsms()
            if sms:
                smses.append(sms)
            else:
                break
        return smses

    def _readsms(self):
        try:
            output = self.sm.GetNextSMS(6, self.start_flag, self.location_flag)
            sms = SMS(subj = output[0]['Name'],
                      from_no = output[0]['Number'],
                      date = output[0]['DateTime'],
                      msg = output[0]['Text'],
                      udh = output[0]['UDH'] if output[0]['UDH']["AllParts"] > 0 else None) 
            print Color.BOLD + "Read : " + Color.END + repr(sms)
            if sms == self._lastreadsms:
                print Color.BOLD + "SMS read is same as last read SMS. Skip further SMS reading in Inbox..." + Color.END
                self.start_flag = 1
                self.location_flag = 0
                return None
            else:
                if self.start_flag == 1 and self.location_flag == 0:
                    self.start_flag = 0
                    self.location_flag = 1    
                return sms
        except gammu.ERR_EMPTY:
            if self.start_flag == 0 and self.location_flag == 1:
                self.start_flag = 1
                self.location_flag = 0
            return None
            
                
if __name__ == '__main__':
    smsr = SMSReader('/content/SMS')
    smsr.start()

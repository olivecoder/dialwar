#!/bin/python

# dialwar.py
# Robert Almeida, 2008.12.09
# (c) MaresTelecom

import sys
import exceptions
import logging

from twisted.internet import task
from twisted.internet import reactor
from twisted.web import server, resource
from twisted.python import log
from Asterisk.Manager import Manager
from random import randint

default_host = '172.16.0.251'
default_port = 5038
default_user = 'dialwar'
default_pass = 'ferroada'
default_channel = 'Zap/r7'
default_context = 'dialwar'
dw = None


class dwManager(Manager):
    '''Asterisk Manager API Extension'''
    # comment to use with asterisk or uncomment to callweaver
    # _AST_BANNER = 'CallWeaver Call Manager/1.0\r\n'
    def on_Event(self, Event):
        # print repr(Event)
        Manager.on_Event(self, Event)


class DialWar:
    '''Asterisk Dialwar
    Dial loop using Asterisk Manager API
    Robert Almeida, 2007.12.08
    (c)MaresTelecom
    '''
    ast_addr = None
    ast_user = None
    ast_pass = None
    context = 'dialwar'
    channel = None
    max_calls = 0
    start_phone = None
    end_phone = None
    man = None
    loop = None
    callerid = 'dialwar'
    account = 'DialWar'
    running = False
    restarting = False
    period = 5.0
    timeout = 45000 # ms

    def __init__(self, addr=(default_host, default_port),
                 user=default_user, pwd=default_pass,
                 chan=default_channel, cont=default_context):
        '''Start asterisk manager api parameters'''
        self.loop = task.LoopingCall(self.doIteration)
        self.ast_addr = addr
        self.ast_user = user
        self.ast_pass = pwd
        self.context = cont
        self.channel = chan
        self.callerid = ''

    def set(self, start_phone, end_phone=start_phone, channel=None, max_calls=None):
        '''Set parameters and start connectin and dial loop'''
        if len(str(start_phone))<8 or len(str(start_phone))<8:
            raise exceptions.TypeErrorException('phone number shall at least 8 digits')
        if max_calls:
            self.max_calls = max_calls
        if channel:
            self.channel = channel
        self.start_phone = start_phone
        self.end_phone = end_phone

    def start(self):
        '''Start connectin and dial loop'''
        if self.running:
            return False
        try:
            print "DialWar: trying to start"
            self.man = dwManager(self.ast_addr, self.ast_user, self.ast_pass);
            self.loop.start(self.period)
            self.running = True
            self.restarting = False
            print "DialWar: started"
        except:
            print "DialWar: START FAILURE. DEFERING"
            reactor.callLater(10,self.restart)
        return self.running

    def restart(self):
        if not self.restarting:
            self.restarting = True
            self.stop()
            reactor.callLater(10,self.start)
            return True
        else:
            return False

    def stop(self):
        '''Stop connection and dial loop'''
        self.running = False
        print "DialWar: stopping"
        try:
            if self.loop:
                self.loop.stop()
        except:
            pass
        try:
            if self.man:
                self.man.close()
                self.man = None
        except:
            pass
        print "DialWar: stopped"
        return self.running==False
    
    def activeCalls(self):
        '''Return active phone calls on dialwar context'''
        counter = 0
        try:
            ch = self.man.Status()
            for k, v in ch.iteritems():
                if v.has_key('Account'):
                    if v['Account']==self.account:
                        counter += 1
                    elif v.has_key('Context'):
                        if v['Context']==self.context:
                            counter += 1
                        elif v.has_key('State'):
                            if v['State']=='Dialing':
                                counter += 1
        except:
            print "STATUS ERROR. TRYING RESTART"
            self.restart()
            counter=None
        return counter

    def doIteration(self):
        '''Dial loop iteration'''
        if not self.running:
            return False
        current_calls=self.activeCalls()
        if current_calls==None:
            return False
        i = self.max_calls - current_calls
        while i>0:
            print i
            i -= 1
            phone = str(randint(self.start_phone,self.end_phone))
            try:
                self.man.Originate(channel=self.channel+'/'+phone,
                                   context=self.context, extension='s', priority=1,
                                   account=self.account, timeout=self.timeout, 
                                   caller_id=self.callerid, async=True)
            except:
                print "ORIGINATE ERROR. TRYING RESTART"
                self.restart()
                break
        return True



class Root(resource.Resource):
    isLeaf = True
    def render(self, request):
        request.redirect("help")
        return ""


class DWResource(resource.Resource):
    isLeaf = True
    html_title  = "DialWar Web Interface"
    html_header = "<HTML><TITLE>%s</TITLE><BODY>"
    # html_footer = "<BR><BR><BR><P><SMALL>(c)2008 MaresTelecom</SMALL></P></BODY></HTML>"
    html_footer = "</BODY></HTML>"

    def header(self):
        return self.html_header % self.html_title

    def footer(self):
        return self.html_footer

    def body(self,body=""):
        return self.header()+"<BODY>"+body+"</BODY>"+self.footer()
    

class Help(DWResource):
    def render(self, request):
        for k, v in root.children.iteritems():
            request.write(repr(k)+"<BR>")
        return ""

class Get(DWResource):
    def render(self, request):
        request.write(self.header())
        dwAtt = dw.__dict__
        for k in request.postpath:
            if k in dwAtt:
                request.write("%s: %s<BR>" % (k,repr(dwAtt[k])))
            else:
                request.write("%s: UNDEFINED<BR>" % k)
        request.write(self.footer())
        return ""

    
class Set(DWResource):
    def render(self, request):
        request.write(self.header())
        dwAtt = dw.__dict__
        for k,v in request.args.iteritems():
            if k in dwAtt:
                request.write("OLD: %s=%s<BR>" % (k,repr(dwAtt[k])))
                dwAtt[k]=type(dwAtt[k])(v[0]) # cast
                request.write("NEW: %s=%s<BR>" % (k,repr(dwAtt[k])))
            else:
                request.write(k+" -> ERROR<BR>")
        request.write(self.footer())
        return ""


class Start(DWResource):
    def render(self, request):
        if not dw.running:
            if dw.start():
                return self.body("OK: STARTED")
            else:
                return self.body("ERROR: FAIL!")
        else:
            return self.body("ERROR: ALREADY RUNNING!")
        

class Stop(DWResource):
    def render(self, request):
        if dw.running:
            if dw.stop():
                return self.body("OK: STOPPED")
            else:
                return self. body("ERROR: FAIL!")
        else:
            return self.body("ERROR: ALREADY STOPPED!")


class Restart(DWResource):
    def render(self, request):
        if dw.restart():
            return self.body("OK: STOPPED AND TRYING START AGAIN")
        else:
            return self.body("ERROR: FAIL!")
        

class Status(DWResource):
    def render(self, request):
        if dw.running:
            return self.body("RUNNING: Active calls: %i" % dw.activeCalls())
        else:
            return self.body("STOPPED")

class Ping(DWResource):
    def render(self, request):
        if dw.man <> None:
            if dw.man.Ping():
                return self.body("OK")
        return self.body("ERROR")


def main(argv):
    global dw
    global root
    argc=len(argv)
    print "Starting DialWar object"
    log.msg("Starting DialWar object")
    dw = DialWar()
    if argc==5:
        dw.set(int(argv[1]),int(argv[2]),argv[3],int(argv[4]))
    elif argc==4:
        dw.set(int(argv[1]),int(argv[2]),argv[3])
    elif argc==3:
        dw.set(int(argv[1]),int(argv[2]))
    else:
        print "Use:\n%s <start-phone-number> <end-phone-number> [channel] [max-concurrents-calls]" % argv[0]
        sys.exit(1)
    reactor.callLater(4,dw.start)

    root = resource.Resource()
    root.putChild("",Root())
    root.putChild("help",Help())
    root.putChild("get",Get())
    root.putChild("set",Set())
    root.putChild("stop",Stop())
    root.putChild("start",Start())
    root.putChild("ping",Ping())
    root.putChild("restart",Restart())
    root.putChild("status",Status())
    reactor.listenTCP(8001, server.Site(root))
    log.msg("Starting twisted web server")
    print "Starting twisted web server"
    reactor.run()
    log.msg("Twisted web server stoping")
    return


if __name__ == '__main__':
    print "started"
    main([ sys.argv[0], 34449000, 34449099,'zap/r7', 4])
    print "finished"

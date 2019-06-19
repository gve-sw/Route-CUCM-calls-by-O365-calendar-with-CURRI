"""
Copyright (c) 2019 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
               https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import socket
from socketserver import BaseServer
#from OpenSSL import SSL
import threading
import string,os,sys
from saxXacmlHandler import *
# for o365 stuff
from O365 import Account
from O365 import EventShowAs
from O365 import oauth_authentication_flow
import datetime as dt
from config import client_id, client_secret, tenant_id 


CONNECTION_INFO = {
    'scopes': ['offline_access', 'message_all', 'https://graph.microsoft.com/User.Read.All', 'https://graph.microsoft.com/Calendars.Read.Shared'],
    'client_id': client_id,
    'client_secret': client_secret,
    'tenant_id': tenant_id     
    #Even we don't have multiple tenants for our o365 account we still have to use the tenant id
    #instead of "common" or otherwise we cannot autherize and get a token.
    }


# This is the CURRI part of the script which is getting an XML request and is sending an XML response

# NOTE: the above packages are part of the Python install with the exception of saxXacmlHandler. saxXacmlHandler is the simple
#       XACML parser which parses the routing request.

# the following are the canned XACML responses for continue, continue with announcement, deny, divert, notapplicable and indeterminate
# these response are to demonstrate valid XACML responses as can be seen in the DO_POST processing below. They come from the sample curri code 
# from devnet. Not all of them are used this office365 example app.
# NOTE:     rejectResponse specifies the user_unavailable annoucement ID. That announcement should say something like:
#           "I'm in a meeting. Please try again later"
#           continueWithAnnouncementResponse specifies the in_meeting annoucement ID. That announcement should say something like: 
#           "I'm just in a meeting. Stay on the line. My colleagues will help you in a moment"
#               
#
#      Please change those IDs below to specify any other announcemnt you might already have configured on your CUCM setup
#      If you do not wish to or are unable to record new ones

continueResponse = '<?xml encoding="UTF-8" version="1.0"?><Response><Result><Decision>Permit</Decision><Status></Status><Obligations><Obligation FulfillOn="Permit" ObligationId="urn:cisco:xacml:policy-attribute"><AttributeAssignment AttributeId="Policy:simplecontinue"><AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string">&lt;cixml ver="1.0"&gt;&lt;continue&gt;&lt;/continue&gt; &lt;/cixml&gt;</AttributeValue></AttributeAssignment></Obligation></Obligations></Result></Response>'

# this is the same as the above response, yet the cixml is not encoded
continueResponseUnencodedCixml = '<?xml encoding="UTF-8" version="1.0"?><Response><Result><Decision>Permit</Decision><Status></Status><Obligations><Obligation FulfillOn="Permit" ObligationId="urn:cisco:xacml:policy-attribute"><AttributeAssignment AttributeId="Policy:simplecontinue"><AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string"><cixml ver="1.0"><continue></continue></cixml></AttributeValue></AttributeAssignment></Obligation></Obligations></Result></Response>'

continueWithAnnouncementResponseAndModCalled = '<?xml encoding="UTF-8" version="1.0"?><Response><Result><Decision>Permit</Decision><Status></Status><Obligations><Obligation FulfillOn="Permit" ObligationId="urn:cisco:xacml:policy-attribute"><AttributeAssignment AttributeId="Policy:simplecontinue"><AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string">&lt;cixml ver="1.0"&gt;&lt;continue&gt;&lt;modify callednumber="{alternate_destination}"/&gt;&lt;greeting identification="in_vergadering"/&gt;&lt;/continue&gt; &lt;/cixml&gt;</AttributeValue></AttributeAssignment></Obligation></Obligations></Result></Response>'

continueWithAnnouncementResponse = '<?xml encoding="UTF-8" version="1.0"?><Response><Result><Decision>Permit</Decision><Status></Status><Obligations><Obligation FulfillOn="Permit" ObligationId="urn:cisco:xacml:policy-attribute"><AttributeAssignment AttributeId="Policy:simplecontinue"><AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string">&lt;cixml ver="1.0"&gt;&lt;continue&gt;&lt;greeting identification="in_meeting"/&gt;&lt;/continue&gt; &lt;/cixml&gt;</AttributeValue></AttributeAssignment></Obligation></Obligations></Result></Response>'

continueWithModifyIngEdResponse = '<?xml encoding="UTF-8" version="1.0"?><Response><Result><Decision>Permit</Decision><Status></Status><Obligations><Obligation FulfillOn="Permit" ObligationId="urn:cisco:xacml:policy-attribute"><AttributeAssignment AttributeId="Policy:simplecontinue"><AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string">&lt;cixml ver="1.0"&gt;&lt;continue&gt;&lt;modify callingnumber="1000" callednumber="61002"/&gt;&lt;/continue&gt; &lt;/cixml&gt;</AttributeValue></AttributeAssignment></Obligation></Obligations></Result></Response>'

denyResponse = '<?xml encoding="UTF-8" version="1.0"?><Response><Result><Decision>Deny</Decision><Status></Status><Obligations><Obligation FulfillOn="Deny" ObligationId="urn:cisco:xacml:response-qualifier"><AttributeAssignment AttributeId="urn:cisco:xacml:is-resource"><AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string">resource</AttributeValue></AttributeAssignment></Obligation></Obligations></Result></Response>'

rejectResponse = '<?xml encoding="UTF-8" version="1.0"?><Response><Result><Decision>Deny</Decision><Status></Status><Obligations><Obligation FulfillOn="Deny" ObligationId="deny.simple"><AttributeAssignment AttributeId="Policy:deny.simple"><AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string">&lt;cixml ver="1.0"&gt;&lt;reject&gt;&lt;announce identification="user_unavailable"/&gt;&lt;/reject&gt; &lt;reason&gt;chaperon&lt;/reason&gt;&lt;/cixml&gt;</AttributeValue></AttributeAssignment></Obligation></Obligations></Result></Response>'

divertResponse = """<?xml encoding="UTF-8" version="1.0"?> <Response><Result><Decision>Permit</Decision><Obligations><Obligation FulfillOn="Permit" ObligationId="continue.simple"><AttributeAssignment AttributeId="Policy:continue.simple"><AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string">&lt;cixml ver="1.0"&gt;&lt;divert&gt;&lt;destination&gt;{alternate_destination}&lt;/destination&gt;&lt;/divert&gt;&lt;reason&gt;chaperone&lt;/reason&gt;&lt;/cixml&gt;</AttributeValue></AttributeAssignment></Obligation></Obligations></Result></Response>"""

# this is the same as above, except that the cixml is not encoded
divertResponseUnencodedCixml = '<?xml encoding="UTF-8" version="1.0"?> <Response><Result><Decision>Permit</Decision><Obligations><Obligation FulfillOn="Permit" ObligationId="continue.simple"><AttributeAssignment AttributeId="Policy:continue.simple"><AttributeValue DataType="http://www.w3.org/2001/XMLSchema#string"><cixml ver="1.0"><divert><destination>1001</destination></divert><reason>chaperone</reason></cixml></AttributeValue></AttributeAssignment></Obligation></Obligations></Result></Response>'

notApplicableResponse = '<?xml encoding="UTF-8" version="1.0"?> <Response> <Result> <Decision>NotApplicable</Decision> <Status> <StatusCode Value="The PDP is not protecting the application requested for, please associate the application with the Entitlement Server in the PAP and retry"/> </Status> <Obligations> <Obligation ObligationId="PutInCache" FulfillOn="Deny"> <AttributeAssignment AttributeId="resource" DataType="http://www.w3.org/2001/XMLSchema#anyURI">CISCO:UC:VoiceOrVideoCall</AttributeAssignment> </Obligation>  </Obligations> </Result> </Response>'

indeterminateResponse = '<?xml encoding="UTF-8" version="1.0"?> :<Response><Result ResourceId=""><Decision>Indeterminate</Decision><Status><StatusCode Value="urn:cisco:xacml:status:missing-attribute"/><StatusMessage>Required subjectid,resourceid,actionid not present in the request</StatusMessage><StatusDetail>Request failed</StatusDetail></Status></Result></Response>'

# this is the base HTTP request handler, which includes methods for DO_HEAD, DO_GET and DO_POST
# the DO_POST parses the XACML request utilizing the saxXacmlParser
class MyHandler(BaseHTTPRequestHandler):
    def setup(s):
        s.connection = s.request
        # s.rfile = socket._fileobject(s.request, "rb", s.rbufsize)    # this is python 2 code
        # s.wfile = socket._fileobject(s.request, "wb", s.wbufsize)    # this is python 2 code
        s.rfile = socket.socket.makefile(s.request, mode="rb", buffering=s.rbufsize)   # not sure if this is the correct way to port the former socket _fileobject but it seems to work
        s.wfile = socket.socket.makefile(s.request, mode="wb", buffering=s.wbufsize)

    def do_HEAD(s):
        s.send_response(200)
        s.send_header("Content-type", "text/html")
        s.send_header("Connection", "Keep-Alive")
        s.send_header("Keep-Alive", "timeout = 20000   max = 100")
        s.end_headers()
        message =  threading.currentThread().getName()
        print("currentThread", message)

    def do_GET(s):
        """Respond to a GET request."""
        s.send_response(200)
        topic = s.path
        print("TOPIC", topic)
        if s.path.endswith(".jpg"):
            print(curdir + sep + s.path)
            f = open(curdir + sep + s.path,"b")
            s.send_header('Content-type',   'image/jpg')
            s.end_headers()
            s.wfile.write(f.read())
            f.close()
        if topic in ['/favicon.ico']:
            f = open(os.getcwd() + '/' + s.path,"r")
            s.send_header('Content-type', 'image/ico')
            s.end_headers()
            s.wfile.write(f.read())
            f.close()
            return
        s.send_header("Content-type", "text/html")
        s.end_headers()
        s.wfile.write("<html><head><title>Simple Python Http Server</title></head>")
        s.wfile.write("<body><p>This is a test.</p>")
        s.wfile.write("<p>You accessed path: %s</p>" % s.path)
        s.wfile.write("</body></html>")

    def do_POST(s):
        global alternate_destination
        message =  threading.currentThread().getName()
        print(time.asctime(), "do_POST", "currentThread", message)
        parser = xml.sax.make_parser()
        xacmlParser = XacmlHandler()
        parser.setContentHandler(xacmlParser)
        try:
            length = int(s.headers.get('content-length'))  # getheader() should be get() when using Python3
            print('length ', length)
            postdata = s.rfile.read(length)
            print(postdata)
            fd = open('tempXacmlReq.xml', "wb")  # needed to use the b for byte as the postdata is a byte string
            fd.write(postdata)  
            fd.close()
        except:
            pass

        parser.parse("tempXacmlReq.xml")

        global contacts
        global account
        global user_principle
        global calendar_state

        # get all directory contacts
        #contacts = get_all_contacts(account)     # only necessary if we don't use the get_all_contacts_dict(account) call in the main function.

        print("called number: {}".format(xacmlParser.calledNumber()))
        user_principle_name = get_upn(contacts, xacmlParser.calledNumber()) # get_upn(contacts, called_number) will return user principle name if called number
        # is found as a contact's business phone otherwise it returns None 
        #print(user_principle_name)
        calendar_state = check_calendar_state(account, user_principle_name) # check_calendar_state will return a string: 'isOof', 'isBusy' or 'isFree'
        print(calendar_state)

        if calendar_state == "isBusy":    
            #send the call to voicemail
            print("Alternate_destination: {}".format(alternate_destination))
            print('send response', divertResponse.format(alternate_destination=alternate_destination))
            MyHandler.send_xml(s, bytes(divertResponse.format(alternate_destination=alternate_destination), "UTF-8"))              # a byte like object is required and not a string so it needs to be converted
        elif calendar_state == "isWorkingElsewhere":
            print('send response', rejectResponse)
            MyHandler.send_xml(s, bytes(rejectResponse, "UTF-8"))
        elif calendar_state == "isOof":
            # Suggested custom announcement: "Sorry, I'm in a meeting. Please try again later." 
            print('send response', rejectResponse)
            MyHandler.send_xml(s, bytes(rejectResponse, "UTF-8"))
        elif calendar_state == "isTentative":
            # Suggested custom announcement: "I'm just in a meeting. Stay on the line. My colleagues will help you in a moment"
            # Plays the custom announcement and continues to ring the called user's extension so you have to turn on a call forward all to the hunt pilot or other colleague's extension.
            # call forward no answer and busy could also be configured to a hunt pilot for example.
            # We could use AXL to set this call forward all destination but the problem is that when the user changes his o365 calendar to Free or has not meeting that his forward all
            # will stay active until he removes it himself via ucmuser page, jabber, phone or other method.
            print('send response', continueWithAnnouncementResponse)
            MyHandler.send_xml(s, bytes(continueWithAnnouncementResponse, "UTF-8"))

        else:
            print('send response', continueResponse)
            MyHandler.send_xml(s, bytes(continueResponse, "UTF-8"))

    def send_xml(s, text, code=200):
        s.send_response(code)
        s.send_header('Content-type', 'text/xml; charset="utf-8"')
        s.send_header('Content-Length', str(len(text)))
        s.send_header("Connection", "Keep-Alive")
        s.send_header("Keep-Alive", "timeout = 20000   max = 100")
        s.end_headers()
        s.wfile.write(text)
        s.wfile.flush()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    threading.daemon_threads = True


def o365_connect(**kwargs):
    """Connect to O365 and return an Account object"""
    credentials = (kwargs['client_id'], kwargs['client_secret'])
    
    #seems like next two lines only have to run once for the app! But we do have to find out how to automatically re-generate
    # tokens
    #result = oauth_authentication_flow(kwargs['client_id'], kwargs['client_secret'], kwargs['scopes', tenant_id=kwargs['tenant_id'])
    #print("auth flow result=",result)

    account = Account(credentials)

    if not account.is_authenticated:  # will check if there is a token and has not expired
        # ask for a login. After logging in, please paste the URL to which the login re-directed as an response
        # to the prompt in the terminal window and press enter. The new token text file will be generated in the same
        # directory where this python script is running from.
        account.authenticate(scopes=kwargs['scopes'])

    return account


def check_calendar_state(account, upn):
    schedule = account.schedule(resource=upn)
    calendar = schedule.get_calendar(calendar_name='Calendar')

    calendar.name = 'Calendar'
    #calendar.update()


    q = calendar.new_query('start').less_equal(dt.datetime.now())
    q.chain('and').on_attribute('end').greater_equal(dt.datetime.now())

    nowmeetings = calendar.get_events(query=q, include_recurring=True)  # include_recurring=True will include repeated events on the result set.
    
    isBusy=EventShowAs.Busy
    isOof=EventShowAs.Oof
    isFree=EventShowAs.Free
    isWorkingElsewhere = EventShowAs.WorkingElsewhere
    isTentative = EventShowAs.Tentative

    global alternate_destination
    
    for event in nowmeetings:
        # Getting the free/busy/out of office state from the events in the calendar of the user
        # we will return from the function as soon as we have a match and will not look anymore
        # to the other events even if there are more.
        # First we check if a phonenumber is given in the subject of the meeting
        alternate_destination = event.subject.split(":")[-1].strip()    # get the phone number to divert to via the subject of the event. Number has to follow after ":"
        #check if alternate_destination is given in the subject line. If not we default to voicemail
        try:
            int(alternate_destination)
        except ValueError:
            alternate_destination = "voicemail"
        #print(alternate_destination)
        print("show_as: ",event.show_as)
        if event.show_as == isOof:
            print("is out of office!")
            return "isOof"
        elif event.show_as == isBusy:
            print("is busy in an event!")
            return "isBusy"
        elif event.show_as == isWorkingElsewhere:
            print("is working elsewhere!")
            return "isWorkingElsewhere"
        elif event.show_as == isTentative:
            print("is tentative!")
            return "isTentative"
        else:
            print("is free")
            return "isFree"
        
    return "calendarEmpty"


def get_all_contacts(account):
    """Get all the contacts in the directory and return custom generator object"""
    # Global Address List (GAL) does not really exist but the concept is provided by the Users API:
    global_address_list = account.address_book(address_book='gal')

    # start a new query:
    q = global_address_list.new_query()


    return global_address_list.get_contacts(query=q)

def get_all_contacts_dict(account):
    """Get all the contacts in the directory and return a dictionary with business phones list as value and mail address as key"""
    # Global Address List (GAL) does not really exist but the concept is provided by the Users API:
    global_address_list = account.address_book(address_book='gal')

    # start a new query:
    q = global_address_list.new_query()

    contacts = {}
    
    contacts_generator = global_address_list.get_contacts(query=q)

    for contact in contacts_generator:
        phones = contact.business_phones
        contacts[contact.main_email] = phones

    return contacts
        

def get_upn(contacts, called_number):
    global user_principle_name
    called_number = '+' + called_number  # as the business_phones start with + we need to prefix our called_number with +
    # this is only necessary when the CUCM is using E.164 format without the +
    # check if contacts is a dict or a generator object
    if isinstance(contacts, dict):
        for mail, phones in contacts.items():
            for phone in phones:
                phone = phone.replace(" ", "")   # we have to remove the spaces in business_phone in order to be able to match with called_number
                if called_number == phone:
                    user_principle_name = mail
    else:   # custom generator object received via get_all_contacts(account)
        for contact in contacts:
            # print(contact.full_name)
            # print(contact.business_phones)
    #        try:
            for business_phone in contact.business_phones:
                business_phone = business_phone.replace(" ", "")   # we have to remove the spaces in business_phone in order to be able to match with called_number
                #print(business_phone)
                if called_number == business_phone:
                    user_principle_name = contact.main_email   # this python library does not seems to expose all properties of the user api
                    # https://docs.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0 so since userPrincipalName is not available I will use the mail property
                    # which is named main_email in the python library
    #        except:
                #print("business phones list is empty")
    #            pass

    if user_principle_name:
        print(user_principle_name)
        return user_principle_name
    else:
        print("None")
        return None





if __name__ == '__main__':
    # connect to O365
    global account
    account = o365_connect(**CONNECTION_INFO)
    #print(account)

    # get all directory contacts
    global contacts
    contacts = get_all_contacts_dict(account)   # daily sync with Azure AD has to be still programmed otherwise we could use get_all_contacts(account) which makes a REST call.
    #print(contacts)
    
    # validate input
    args = sys.argv[1:]
    REQARGS = 3
    
    if len(args) < REQARGS:
        print("Usage:",sys.argv[0], "<HOST_NAME> <PORT> http")
        sys.exit(1)

    HOST_NAME = sys.argv[1]
    PORT      = sys.argv[2]
    PORT_NUM  = int(PORT)
    PROTO     = sys.argv[3]
    
    print("HTTP://HOST_NAME:PORT", PROTO, '://', HOST_NAME, ':', PORT)

    if PROTO == 'http' or PROTO == 'HTTP':
        httpd = ThreadedHTTPServer((HOST_NAME, PORT_NUM), MyHandler)
    else:
        print('invalid proto', PROTO, 'required http')
        sys.exit(1)

    print(time.asctime(), "HTTP CURRI Server Started - %s:%s" % (HOST_NAME, PORT))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
        httpd.server_close()
        
    print(time.asctime(), "Server Stopped - %s:%s" % (HOST_NAME, PORT))

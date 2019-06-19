
#% Copyright (c) 2013 by Cisco Systems, Inc.
#  ver 1.1
#

import string
import xml.sax
from xml.sax.handler import *

class XacmlHandler(ContentHandler):
    """Crude extractor for XACML document"""
    def __init__(self):
        self.isCallingNumber = 0
        self.isCalledNumber = 0
        self.isTransformedCgpn = 0
        self.isTransformedCdpn = 0
        self.CallingNumber = 0
        self.CalledNumber = 0
        self.TransformedCgpn = 0
        self.TransformedCdpn = 0
        
    def startDocument(self):
        print('--- Begin Document ---')
        
    def startElement(self, name, attrs):
        if name == 'Attribute':
            self.attrs = attrs.get('AttributeId')
            print('AttributeId', self.attrs)
        elif name == 'AttributeValue':
            if self.attrs == 'urn:Cisco:uc:1.0:callingnumber':
                self.isCallingNumber = 1
            elif self.attrs == 'urn:Cisco:uc:1.0:callednumber':
                self.isCalledNumber = 1
            elif self.attrs == 'urn:Cisco:uc:1.0:transformedcgpn':
                self.isTransformedCgpn = 1
            elif self.attrs == 'urn:Cisco:uc:1.0:transformedcdpn':
                self.isTransformedCdpn = 1
                
    def endElement(self, name):
        if name == 'Request':
            # format xacml response based on called/calling numbers
            print('endElement Request')
            
    def characters(self, ch):
        if self.isCallingNumber == 1:
             self.CallingNumber = ch
             print('CallingNumber ' + ch)
             self.isCallingNumber = 0
        if self.isCalledNumber == 1:
             self.CalledNumber = ch
             print('CalledNubmer ' + ch)
             self.isCalledNumber = 0
        if self.isTransformedCgpn == 1:
             self.TransformedCgpn = ch
             print('TransformedCgpn ' + ch)
             self.isTransformedCgpn = 0
        if self.isTransformedCdpn == 1:
             self.TransformedCdpn = ch
             print('TransformedCdpn ' + ch)
             self.isTransformedCdpn = 0

    def callingNumber(self): return self.CallingNumber

    def calledNumber(self): return self.CalledNumber

    def transformedCgpn(self): return self.TransformedCgpn

    def transformedCdpn(self): return self.TransformedCdpn

if __name__ == '__main__':
    parser = xml.sax.make_parser()
    handler = XacmlHandler()
    parser.setContentHandler(handler)
    parser.parse("sampleXacmlReq.xml")

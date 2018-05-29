#!/usr/bin/python3
import array
import hashlib
import re
import sys
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup
# =============================================================================
CALL_LOG = "/tmp/call_log"
HOST     = "192.168.178.1"
PSK      = "PASS"
# =============================================================================

class Crawler(object):
    def __init__(self, host, psk, timeline):
        self.host = host
        self.psk = psk
        self.timeline = timeline
        self.calls = []
        self.new_calls()

    def getChallenge(self):
        chall = re.compile('"challenge": *"(?P<challenge>\w+)",')
        for line in urllib.request.urlopen("http://%s" % (self.host)).readlines():
            m = chall.search(line.decode('utf-8'))
            if m:
                return m.group('challenge')
        assert False, "There should always be a challenge"

    def calcResp(self, challenge):
        m = hashlib.md5()
        pre = challenge+"-"+self.psk
        pre_arr = array.array('H', [ord(i) for i in pre])
        m.update(pre_arr.tobytes())
        dgst = "".join(["%.2x"%i for i in m.digest()])
        return "%s-%s" % (challenge, dgst)

    def getSID(self):
        crypto_resp = self.calcResp(self.getChallenge())
        url = "http://%s/" % (self.host)
        post = "response=%s&lp=&username=" % (crypto_resp)
        rsid = re.compile('"sid": *"(?P<sid>\w+)"')
        for line in urllib.request.urlopen(url, data=post.encode('ascii')):
            m = rsid.search(line.decode('utf-8'))
            if m:
                return m.group('sid')
        assert False, "There should always be a sid"

    def new_calls(self):
        sid = self.getSID()
        url = "http://%s/data.lua" % (self.host)
        post = "xhr=1&sid=%s&lang=de&no_sidrenew=&page=dialLi" % (sid)
        html = urllib.request.urlopen(url, data=post.encode('ascii')).read()
        soup = BeautifulSoup(html, "html.parser")
        self.parse_calls(soup)

    def call_desc(self, call):
        return "%s %s" % (call["time"], call["number"])

    def call_msg(self, call):
        return "%s %s: %s\n" % (call["event"], call["time"], call["desc"])

    def parse_calls(self, soup):
        last_call = self.timeline.getLast()
        for call_soup in soup.select('table#uiCalls > tr'):
            call = {
                    'event': call_soup.select("td:nth-of-type(1)")[0].get('class')[0] ,
                    'time' : call_soup.select("td:nth-of-type(1)")[0].get('datalabel') ,
                    'desc' : call_soup.select("td:nth-of-type(3)")[0].get('title')
            }
            try:
                call['number'] = call['desc'].split(' = ')[-1]
            except AttributeError:
                call['number'] = '9999999999999999999'
                call['desc'] = 'Unbekannt'

            call_desc = self.call_desc(call)
            if call_desc == last_call:
                break
            else:
                self.calls.append(call)

    def sendList(self):
        for call in self.calls[::-1]:
            msg = self.call_msg(call).encode('ascii', 'ignore')
            sys.stdout.buffer.write(msg)
        if len(self.calls) > 0:
            self.timeline.setLast(self.call_desc(self.calls[0]))

class Timeline(object):
    def __init__(self, path):
        self.path = path

    def getLast(self):
        with open(self.path, 'r') as f:
            try:
                last_call = f.readlines()[-1].replace('\n', '')
            except IndexError:
                last_call = "NEW MILESTONE"
        return last_call

    def setLast(self, text):
        with open(self.path, 'a') as f:
            f.write("%s\n"%(text))

if __name__ == '__main__':
    t = Timeline(CALL_LOG)
    c = Crawler( HOST, PSK, t)
    c.sendList()

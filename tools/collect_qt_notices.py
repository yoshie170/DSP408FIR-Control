"""Explicit maintainer refresh of upstream license texts. Not run at app/build startup.

Only HTTPS doc.qt.io attribution pages linked from the matching Qt6 index
and OpenSSL's LICENSE.txt are read; no downloaded code is executed.
"""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from urllib.request import urlopen,Request
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
INDEX='https://doc.qt.io/qt-6/licenses-used-in-qt.html'
MODULES={'Qt Core','Qt GUI','Qt Network','Qt PDF','Qt Qml','Qt Quick',
         'Qt Quick 3D','Qt Quick Controls','Qt SVG','Qt Virtual Keyboard','Qt Widgets'}


class Index(HTMLParser):
    def __init__(self):super().__init__();self.heading=False;self.module='';self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='h2':self.heading=True;self.module=''
        if tag=='a' and self.module in MODULES:
            href=dict(attrs).get('href','')
            if 'attribution' in href:self.links.append(urljoin(INDEX,href))
    def handle_data(self,data):
        if self.heading:self.module+=data
    def handle_endtag(self,tag):
        if tag=='h2':self.heading=False;self.module=self.module.strip()


class Body(HTMLParser):
    def __init__(self):super().__init__();self.depth=0;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag=='div':
            if self.depth:self.depth+=1
            elif 'descr' in dict(attrs).get('class','').split():self.depth=1
        if self.depth and tag in ('p','br','pre','h1','h2','h3','li','tr'):self.parts.append('\n')
    def handle_data(self,data):
        if self.depth:self.parts.append(data)
    def handle_endtag(self,tag):
        if tag=='div' and self.depth:self.depth-=1
        if self.depth and tag in ('p','pre','li'):self.parts.append('\n')


def download(url):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in ('doc.qt.io','raw.githubusercontent.com'):
        raise ValueError('Unapproved license source')
    with urlopen(Request(url,headers={'User-Agent':'DSP408FIR-License-Collector/1.0'}),timeout=30) as reply:
        data=reply.read(4*1024*1024+1)
    if len(data)>4*1024*1024:raise ValueError('License page too large')
    return data.decode('utf-8')


def refresh():
    index=download(INDEX)
    if 'Qt 6.12.0' not in index:raise ValueError('Review collector for the installed Qt6.12.0 before refreshing')
    parser=Index();parser.feed(index);urls=sorted(set(parser.links))
    if len(urls)<20:raise ValueError('Attribution index did not provide expected modules')
    def convert(url):
        raw=download(url);body=Body();body.feed(raw);text=''.join(body.parts).strip()
        if len(text)<60:raise ValueError('License body missing: '+url)
        return url,re.sub(r'\n{4,}','\n\n\n',text)
    with ThreadPoolExecutor(max_workers=6) as pool:pages=list(pool.map(convert,urls))
    target=ROOT/'dsp408/assets/licenses';(target/'Qt').mkdir(exist_ok=True)
    text=('Qt6.12.0 — upstream third-party attributions\n'
          'Copyrights and license texts below belong to the respective upstream authors.\n'
          'Covers the Qt module families present in the Windows bundle; upstream lists include\n'
          'conditional/platform-specific components which may be inactive in this build.\n'
          'Source index: '+INDEX+'\n\n')
    for url,body in pages:text+='='*72+'\nSource: '+url+'\n\n'+body+'\n\n'
    (target/'Qt/THIRD_PARTY_NOTICES.txt').write_text(text,encoding='utf-8')
    openssl='https://raw.githubusercontent.com/openssl/openssl/openssl-3.5.9/LICENSE.txt'
    license=download(openssl)
    if 'Apache License' not in license:raise ValueError('Unexpected OpenSSL license')
    (target/'OpenSSL').mkdir(exist_ok=True)
    (target/'OpenSSL/LICENSE.txt').write_text(license,encoding='utf-8')
    # Hash canonical UTF-8/LF text, independent of Windows checkout newlines.
    manifest={'qt_version':'6.12.0','index':INDEX,'modules':sorted(MODULES),'sources':urls,'openssl_source':openssl,
              'qt_notice_sha256':hashlib.sha256(text.encode()).hexdigest()}
    (target/'Qt/sources.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(f'Collected {len(urls)} Qt attribution pages and OpenSSL license ({len(text)} characters)')


if __name__=='__main__':refresh()

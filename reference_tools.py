"""Public-reference inspection. No cookies, scripts, credentials or AI service."""
import base64, http.client, ipaddress, re, socket, ssl
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin

LIMIT=6*1024*1024

def public_target(url):
 u=urlsplit(url)
 if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.port not in (None,80,443):raise ValueError('Use a public http(s) URL without credentials and with a standard port.')
 addresses=socket.getaddrinfo(u.hostname,u.port or (443 if u.scheme=='https' else 80),type=socket.SOCK_STREAM)
 if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise ValueError('Private, local and reserved network addresses are blocked. Upload a reference image instead.')
 return u,addresses[0][4][0]

def fetch_public(url):
 for _ in range(4):
  u,ip=public_target(url);port=u.port or (443 if u.scheme=='https' else 80)
  # Connect to the validated address directly; TLS still verifies the original hostname.
  sock=socket.create_connection((ip,port),timeout=10)
  try:
   if u.scheme=='https':sock=ssl.create_default_context().wrap_socket(sock,server_hostname=u.hostname)
   conn=http.client.HTTPConnection(u.hostname,port,timeout=10);conn.sock=sock
   path=u.path or '/'
   if u.query:path+='?'+u.query
   conn.request('GET',path,headers={'Host':u.netloc,'User-Agent':'ShankysReferencePreview/1.0','Accept':'text/html,image/png,image/jpeg,image/webp','Accept-Encoding':'identity'})
   response=conn.getresponse()
   if response.status in (301,302,303,307,308):
    location=response.getheader('Location')
    if not location:raise ValueError('Reference redirect has no destination.')
    url=urljoin(url,location);continue
   if response.status!=200:raise ValueError('This reference is unavailable or requires sign-in. Upload its screenshot instead.')
   kind=(response.getheader('Content-Type') or '').split(';')[0].lower()
   if kind not in ('text/html','application/xhtml+xml','text/css','image/png','image/jpeg','image/webp'):raise ValueError('Use a website page or PNG, JPEG or WebP reference.')
   if int(response.getheader('Content-Length') or 0)>LIMIT:raise ValueError('Reference exceeds the 6 MB download limit.')
   body=response.read(LIMIT+1)
   if len(body)>LIMIT:raise ValueError('Reference exceeds the 6 MB download limit.')
   return url,kind,body
  finally:sock.close()
 raise ValueError('Too many redirects. Upload a screenshot instead.')

class ReferenceParser(HTMLParser):
 def __init__(self):
  super().__init__();self.title='';self.headings=[];self.images=[];self.styles=[];self.description='';self.og='';self.capture=None;self.skip=0
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag in ('script','noscript'):self.skip+=1
  if tag in ('title','h1','h2','h3','style'):self.capture=[tag,'']
  if tag=='meta':
   name=a.get('property',a.get('name','')).lower()
   if name=='og:image':self.og=a.get('content','')
   if name=='description':self.description=a.get('content','')[:500]
  if tag=='img' and a.get('src'):self.images.append(a['src'])
  if tag=='link' and a.get('rel')=='stylesheet' and a.get('href'):self.styles.append(a['href'])
 def handle_data(self,data):
  if self.capture and not self.skip:self.capture[1]+=data
 def handle_endtag(self,tag):
  if tag in ('script','noscript'):self.skip=max(0,self.skip-1)
  if self.capture and self.capture[0]==tag:
   text=' '.join(self.capture[1].split())
   if tag=='title':self.title=text[:160]
   elif tag in ('h1','h2','h3') and text:self.headings.append(text[:200])
   self.capture=None

def inspect_reference(url):
 final,kind,body=fetch_public(url)
 if kind.startswith('image/'):
  return {'kind':'image','url':final,'data':'data:'+kind+';base64,'+base64.b64encode(body).decode()}
 source=body.decode('utf-8',errors='replace');p=ReferenceParser();p.feed(source)
 if 'pinterest.' in urlsplit(final).hostname or urlsplit(final).hostname.endswith('pin.it'):
  if not p.og:raise ValueError('Pinterest did not expose the pin image publicly. Save the pin image or screenshot and upload it here.')
  image_url,image_kind,image_body=fetch_public(urljoin(final,p.og))
  if not image_kind.startswith('image/'):raise ValueError('Pinterest image unavailable. Upload its screenshot instead.')
  return {'kind':'image','url':final,'data':'data:'+image_kind+';base64,'+base64.b64encode(image_body).decode()}
 for sheet in p.styles[:2]:
  try:
   _,mime,raw=fetch_public(urljoin(final,sheet))
   if mime=='text/css':source+='\n'+raw.decode('utf-8',errors='replace')
  except (ValueError,OSError,http.client.HTTPException):pass
 images=[]
 for path in ([p.og] if p.og else [])+p.images:
  if len(images)>=3:break
  try:
   _,mime,raw=fetch_public(urljoin(final,path))
   if mime.startswith('image/'):images.append('data:'+mime+';base64,'+base64.b64encode(raw).decode())
  except (ValueError,OSError,http.client.HTTPException):pass
 colors=list(dict.fromkeys(re.findall(r'#[0-9a-fA-F]{6}\b',source)))[:12]
 if not p.headings and not p.title:raise ValueError('No public page content found. This page may require sign-in or JavaScript. Upload a screenshot instead.')
 return {'kind':'website','url':final,'title':p.title,'headings':p.headings[:8],'description':p.description,'colors':colors,'images':images,'grid':bool(re.search(r'display\s*:\s*grid|class=[\"\'][^\"\']*(?:grid|cards|gallery)',source,re.I)),'note':'Public HTML headings, inline colours and available images; original scripts, forms and backend are excluded.'}

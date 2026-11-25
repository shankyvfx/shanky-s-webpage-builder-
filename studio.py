import source_save
"""Shankys Website Builder — Python 3 standard-library local editor with explicit opt-in provider API requests."""

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from reference_tools import inspect_reference
import ai_providers
import site_structure
import file_cleanup

from pathlib import Path

from urllib.parse import urlparse, unquote, parse_qs

import html, base64, difflib, hashlib, json, mimetypes, os, secrets, shutil, subprocess, sys, threading, time, uuid, webbrowser, zipfile, io

APP=Path(__file__).resolve().parent

HOME=APP/'workspace'; HOME.mkdir(exist_ok=True)

KEY_FILE=HOME/'.local-session-key'

KEY=KEY_FILE.read_text().strip() if KEY_FILE.exists() else secrets.token_urlsafe(32)

KEY_FILE.write_text(KEY)

PORT=int(os.environ.get('STUDIO_PORT','8937')); PREVIEW=PORT+1

SKIP={'.git','node_modules','.env','.aws','.codex','.openai','.next','.cache','__pycache__'}

MAX_TOTAL=400*1024*1024

LOCK=threading.RLock()

def jsonread(p,default=None):

 try:return json.loads(p.read_text(encoding='utf-8'))

 except (OSError,ValueError):return default



def safe(root,relative):

 p=(root/relative).resolve()

 if not p.is_relative_to(root.resolve()):raise ValueError('This path is outside the website folder.')

 return p



def project(pid):

 if not pid or not pid.isalnum():raise ValueError('Choose a project first.')

 p=HOME/pid

 if not (p/'project.json').exists():raise ValueError('Project not found.')

 return p



def info(p):

 data=jsonread(p/'project.json',{});data['pages']=sorted(str(x.relative_to(p/'site')).replace('\\','/') for x in (p/'site').rglob('*.html'))

 data['saveFolder']=data.get('saveFolder') or (data.get('source') if Path(data.get('source','')).is_absolute() and not Path(data.get('source','')).resolve().is_relative_to(APP.resolve()) else None)

 data['previewOrigin']=f'http://127.0.0.1:{PREVIEW}'

 return data



def staticroot(path):

 for candidate in [path,path/'dist',path/'out',path/'build',path/'public']:

  if (candidate/'index.html').is_file():return candidate

 raise ValueError('No static index.html found. Export/build your framework website first, then open its dist, out or build folder.')



def importfolder(source):

 source=staticroot(Path(source).expanduser().resolve())

 if HOME.resolve().is_relative_to(source):raise ValueError('Choose the website folder, not the Studio application folder.')

 pid=uuid.uuid4().hex;dest=HOME/pid; files=[];total=0

 for p in source.rglob('*'):

  rel=p.relative_to(source)

  if p.is_symlink() or any(part in SKIP or part.startswith('.env') for part in rel.parts):continue

  if p.is_file():

   total+=p.stat().st_size

   if total>MAX_TOTAL:raise ValueError('This first version supports websites up to 400 MB.')

   files.append((p,rel))

 try:

  for p,rel in files:

   out=dest/'site'/rel;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)

  shutil.copytree(dest/'site',dest/'original')

  data={'id':pid,'name':source.name,'source':str(source),'created':time.time(),'lastSaved':None}

  (dest/'project.json').write_text(json.dumps(data),encoding='utf-8')

  return info(dest)

 except Exception:

  if dest.exists():shutil.rmtree(dest)

  raise



def blankhtml(title):

 return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>body{margin:0;background:#f7f5f0;color:#242424;font-family:Arial,sans-serif;line-height:1.6}main{box-sizing:border-box;min-height:100vh;padding:64px 7%;max-width:1200px;margin:auto}h1{font-size:48px;line-height:1.1}p{font-size:20px;max-width:680px}img{max-width:100%;height:auto}@media(max-width:600px){main{padding:40px 6%}h1{font-size:36px}}</style></head><body><main id="page"><h1>'+html.escape(title)+'</h1><p>Select this text to make it yours. Add text or images from the editor toolbar.</p></main></body></html>'



def newproject(name):

 pid=uuid.uuid4().hex;p=HOME/pid;(p/'site').mkdir(parents=True);(p/'original').mkdir();site_structure.initialize(p/'site',name);source=site_structure.organize_html(p/'site','index.html',blankhtml(name))

 (p/'site/index.html').write_text(source,encoding='utf-8');(p/'original/index.html').write_text(source,encoding='utf-8')

 (p/'project.json').write_text(json.dumps({'id':pid,'name':name,'source':'Created in Shankys Website Builder','structure':site_structure.LAYOUT,'created':time.time(),'lastSaved':None}),encoding='utf-8');return info(p)



def pickfolder():

 code='import tkinter as t;from tkinter import filedialog;r=t.Tk();r.withdraw();r.attributes("-topmost",True);p=filedialog.askdirectory(title="Choose your static website folder");r.destroy();print(p)'

 result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

 return result.stdout.strip()



class Handler(BaseHTTPRequestHandler):

 def log_message(self,*args):pass

 def response(self,data,status=200,kind='application/json'):

  if kind=='application/json':data=json.dumps(data,ensure_ascii=False).encode()

  if isinstance(data,str):data=data.encode('utf-8')

  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)

 def file(self,p):

  if p.is_dir():p=p/'index.html'

  if not p.is_file():return self.response({'error':'File not found'},404)

  self.response(p.read_bytes(),kind=mimetypes.guess_type(str(p))[0] or 'application/octet-stream')

 def do_GET(self):

  try:

   u=urlparse(self.path);route=unquote(u.path);q=parse_qs(u.query)

   if route.startswith('/site/'):

    parts=route.split('/',3);return self.file(safe(project(parts[2])/'site',parts[3] if len(parts)>3 else 'index.html'))

   if self.server.server_port==PREVIEW:return self.response({'error':'Preview only'},404)

   if route=='/api/session':return self.response({'key':KEY,'projects':[info(p) for p in HOME.iterdir() if (p/'project.json').exists()]})

   if route=='/api/project':return self.response(info(project(q['id'][0])))

   if route=='/api/page':

    p=project(q['id'][0]);rel=q['page'][0];f=safe(p/'site',rel)

    if f.suffix.lower()!='.html':raise ValueError('Only HTML pages can be edited.')

    return self.response({'html':f.read_text(encoding='utf-8-sig'),'revision':hashlib.sha256(f.read_bytes()).hexdigest()})

   if route=='/api/review':

    p=project(q['id'][0]);rel=q['page'][0];old=safe(p/'original',rel);new=safe(p/'site',rel)

    a=old.read_text(encoding='utf-8-sig').splitlines() if old.exists() else []

    return self.response({'diff':'\n'.join(difflib.unified_diff(a,new.read_text(encoding='utf-8-sig').splitlines(),fromfile='Original/'+rel,tofile='Saved/'+rel,lineterm=''))})

   if route=='/api/export':

    p=project(q['id'][0]);buf=io.BytesIO()

    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:

     for f in (p/'site').rglob('*'):

      if f.is_file():z.write(f,f.relative_to(p/'site'))
      elif f.is_dir():z.writestr(f.relative_to(p/'site').as_posix()+'/',b'')

    self.send_response(200);self.send_header('Content-Type','application/zip');self.send_header('Content-Disposition','attachment; filename="website-export.zip"');self.send_header('Content-Length',str(buf.tell()));self.end_headers();self.wfile.write(buf.getvalue());return

   if route in ('/','/index.html'):return self.file(APP/'app/index.html')

   if route=='/assets/icons/builder-icon.svg':return self.file(APP/'app/assets/icons/builder-icon.svg')

   if route in ('/app.js','/style.css','/reference.js'):return self.file(APP/'app'/route[1:])

   self.response({'error':'Not found'},404)

  except Exception as e:self.response({'error':str(e)},400)

 def do_POST(self):

  if self.server.server_port==PREVIEW:return self.response({'error':'Preview is read-only'},403)

  if self.headers.get('X-Studio-Key')!=KEY:return self.response({'error':'Open Studio in its local browser tab.'},403)

  origin=self.headers.get('Origin')

  if origin and origin!=f'http://127.0.0.1:{PORT}':return self.response({'error':'Request origin rejected.'},403)

  try:

   n=int(self.headers.get('Content-Length','0'))

   if n>40*1024*1024:raise ValueError('File is too large.')

   data=json.loads(self.rfile.read(n));route=urlparse(self.path).path

   with LOCK:

    if route=='/api/cleanup/scan':return self.response(file_cleanup.scan(project(data['id'])))
    if route=='/api/cleanup/trash':return self.response(file_cleanup.move_to_trash(project(data['id']),data.get('token',''),data.get('paths',[])))
    if route=='/api/cleanup/restore':return self.response(file_cleanup.restore(project(data['id'])))
    if route=='/api/reference/review-html':
     reference=data.get('reference',{});images=[reference['data']] if reference.get('kind')=='image' else reference.get('images',[])[:3]
     for image in images:
      if not isinstance(image,str) or not image.startswith(('data:image/png;base64,','data:image/jpeg;base64,','data:image/webp;base64,')):raise ValueError('Use a supported local reference image.')
      if len(image)>7*1024*1024:raise ValueError('Reference image is too large. Resize it below 5 MB.')
      base64.b64decode(image.split(',',1)[1],validate=True)
     draft=ai_providers.clean_draft(data.get('html',''),images)
     if reference.get('exactDimensions'):draft=ai_providers.lock_reference_canvas(draft,*ai_providers.reference_dimensions(reference))
     return self.response({'html':draft,'local':True})
    if route=='/api/ai/status':return self.response(ai_providers.state(data.get('provider')))
    if route=='/api/ai/connect':return self.response(ai_providers.connect(data.get('provider'),data.get('key','')))
    if route=='/api/ai/disconnect':return self.response(ai_providers.disconnect(data.get('provider')))
    if route=='/api/ai/start':return self.response(ai_providers.start_job(data))
    if route=='/api/ai/poll':return self.response(ai_providers.poll_job(data.get('id')))
    if route=='/api/ai/cancel':return self.response(ai_providers.cancel_job(data.get('id')))
    if route=='/api/reference':return self.response(inspect_reference(data.get('url','')))

    if route=='/api/browse':

     folder=pickfolder();return self.response(importfolder(folder) if folder else {'cancelled':True})

    if route=='/api/open':return self.response(importfolder(data['path']))


    if route=='/api/import-zip':

     raw=base64.b64decode(data['data']);temp=HOME/('import-'+uuid.uuid4().hex);temp.mkdir()

     try:

      with zipfile.ZipFile(io.BytesIO(raw)) as z:

       if sum(f.file_size for f in z.infolist())>MAX_TOTAL:raise ValueError('ZIP is larger than 400 MB.')

       for f in z.infolist():

        rel=Path(f.filename)

        if any(part in SKIP or part.startswith('.env') for part in rel.parts):continue

        target=safe(temp,f.filename)

        if not f.is_dir():target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(f))

      source=temp

      if not (source/'index.html').exists():

       dirs=[x for x in temp.iterdir() if x.is_dir()]

       if len(dirs)==1:source=dirs[0]

      result=importfolder(source);result['name']=Path(data.get('name','Imported website')).stem

      meta=project(result['id'])/'project.json';record=jsonread(meta);record['name']=result['name'];record['source']='ZIP import';meta.write_text(json.dumps(record),encoding='utf-8')

      return self.response(info(meta.parent))

     finally:shutil.rmtree(temp)

    if route=='/api/save-folder':
     p=project(data['id']);folder=pickfolder()
     if not folder:return self.response({'cancelled':True})
     root=Path(folder).resolve()
     if root.is_relative_to(APP.resolve()):raise ValueError('Choose a website folder outside the builder application.')
     meta=jsonread(p/'project.json');meta['saveFolder']=str(root);(p/'project.json').write_text(json.dumps(meta),encoding='utf-8');return self.response({'folder':str(root)})

    if route=='/api/save':

     p=project(data['id']);f=safe(p/'site',data['page'])

     if f.suffix.lower()!='.html' or not f.exists():raise ValueError('Choose an existing HTML page.')

     if hashlib.sha256(f.read_bytes()).hexdigest()!=data['revision']:raise ValueError('The file changed since it was opened. Reopen this page before saving to avoid overwriting another edit.')

     html=data['html']

     if '<html' not in html.lower():raise ValueError('Invalid HTML document.')

     history=p/'history'/str(time.time_ns());history.mkdir(parents=True);(history/'before.html').write_bytes(f.read_bytes());(history/'page.txt').write_text(data['page'])

     if jsonread(p/'project.json',{}).get('structure')==site_structure.LAYOUT:html=site_structure.organize_html(p/'site',data['page'],html)

     tmp=f.with_suffix('.studio-tmp');tmp.write_text(html,encoding='utf-8');os.replace(tmp,f)

     meta=jsonread(p/'project.json');meta['lastSaved']=time.time();(p/'project.json').write_text(json.dumps(meta),encoding='utf-8')

     target=info(p).get('saveFolder');sourceResult=None;sourceError=None
     if target:
      try:sourceResult=source_save.sync(p,target)
      except Exception as error:sourceError=str(error)
     return self.response({'revision':hashlib.sha256(f.read_bytes()).hexdigest(),'saved':True,'source':sourceResult,'sourceError':sourceError})

    if route=='/api/image':

     p=project(data['id']);raw=base64.b64decode(data['data']);ext=Path(data['name']).suffix.lower()

     if ext not in ('.jpg','.jpeg','.png','.webp','.gif','.avif'):raise ValueError('Use a JPG, PNG, WebP, GIF or AVIF image.')

     if len(raw)>20*1024*1024:raise ValueError('Choose an image smaller than 20 MB.')

     rel=site_structure.image_path(p/'site',data['name'],data.get('category','uploads'));f=safe(p/'site',rel);f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(raw);return self.response({'path':rel})

    if route=='/api/new-project':return self.response(newproject(data.get('name','My new website').strip()[:120] or 'My new website'))

    if route=='/api/new-page':

     p=project(data['id']);name=site_structure.page_name(data['name'])

     if not name.endswith('.html'):name+='.html'

     if Path(name).name!=name or any(c in name for c in '<>:"/\\|?*') or name.startswith('.'):raise ValueError('Use a simple HTML filename without folders.')

     current=safe(p/'site',data.get('page','index.html'));dest=((p/'site/pages') if jsonread(p/'project.json',{}).get('structure')==site_structure.LAYOUT else current.parent)/name;dest.parent.mkdir(parents=True,exist_ok=True)

     if dest.exists():raise ValueError('That page already exists.')

     source=blankhtml(Path(name).stem.replace('-',' ').title());rel=dest.relative_to(p/'site').as_posix();source=site_structure.organize_html(p/'site',rel,source) if jsonread(p/'project.json',{}).get('structure')==site_structure.LAYOUT else source;dest.write_text(source,encoding='utf-8');baseline=safe(p/'original',rel);baseline.parent.mkdir(parents=True,exist_ok=True);baseline.write_text(source,encoding='utf-8')

     return self.response({'page':rel,'project':info(p)})

    if route=='/api/revert':

     p=project(data['id']);rel=data['page'];f=safe(p/'site',rel);original=safe(p/'original',rel)

     if not original.is_file():raise ValueError('No original snapshot exists for this page.')

     h=p/'history'/str(time.time_ns());h.mkdir(parents=True);(h/'before.html').write_bytes(f.read_bytes());(h/'page.txt').write_text(rel)

     f.write_bytes(original.read_bytes());return self.response({'reverted':True})

    if route=='/api/duplicate':

     p=project(data['id']);source=safe(p/'site',data['page']);name=site_structure.page_name(data['name'])

     if not name.endswith('.html'):name+='.html'

     if Path(name).name!=name or any(c in name for c in '<>:"/\\|?*') or name.startswith('.'):raise ValueError('Use a simple filename such as services-copy.html, without folders.')

     dest=((p/'site/pages') if jsonread(p/'project.json',{}).get('structure')==site_structure.LAYOUT and source.parent==p/'site' else source.parent)/name;dest.parent.mkdir(parents=True,exist_ok=True)

     if dest.exists():raise ValueError('That page filename already exists. Choose another name.')

     rel=dest.relative_to(p/'site').as_posix();contents=source.read_text(encoding='utf-8');contents=site_structure.rebase_html(contents,data['page'],rel);dest.write_text(contents,encoding='utf-8')

     baseline=safe(p/'original',rel);baseline.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,baseline)

     return self.response({'page':rel,'project':info(p)})

    if route=='/api/restore':

     p=project(data['id']);items=sorted((p/'history').glob('*')) if (p/'history').exists() else []

     items=[x for x in items if (x/'page.txt').read_text()==data['page']]

     if not items:raise ValueError('No saved history for this page yet.')

     h=items[-1];f=safe(p/'site',data['page']);current=f.read_bytes();f.write_bytes((h/'before.html').read_bytes());(h/'before.html').write_bytes(current)

     return self.response({'restored':True})

    self.response({'error':'Unknown operation'},404)

  except Exception as e:self.response({'error':str(e)},400)



def main():

 try:

  preview=ThreadingHTTPServer(('127.0.0.1',PREVIEW),Handler);server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)

 except OSError:

  print('Studio ports are busy. Close the previous Studio window, or set STUDIO_PORT to another port.');return

 threading.Thread(target=preview.serve_forever,daemon=True).start()

 print(f'Shankys Website Builder: http://127.0.0.1:{PORT}',flush=True)

 if '--no-browser' not in sys.argv:webbrowser.open(f'http://127.0.0.1:{PORT}')

 try:server.serve_forever()

 except KeyboardInterrupt:pass

 finally:server.server_close();preview.shutdown()

if __name__=='__main__':main()


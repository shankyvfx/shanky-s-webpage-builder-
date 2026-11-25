"""Conservative orphan-upload review with project-local, restorable quarantine."""
import hashlib,json,os,re,threading,time,uuid
from pathlib import Path
CACHE={};GUARD=threading.RLock();IMAGE={'.png','.jpg','.jpeg','.webp','.gif','.avif','.svg'};TEXT={'.html','.htm','.css','.js','.mjs','.json','.svg','.webmanifest','.xml','.md','.txt'}
def inside(root,relative):
 path=(root/relative).resolve()
 if not path.is_relative_to(root.resolve()):raise ValueError('Cleanup path is outside the website.')
 return path

def inventory(site):
 return {p.relative_to(site).as_posix():(p.stat().st_size,p.stat().st_mtime_ns) for p in site.rglob('*') if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(site.resolve())}

def scan(project):
 site=project/'site';before=inventory(site);text=[];reasons=[];total=0
 reference_paths=[site/name for name in before]
 for folder in ('original','history'):
  root=project/folder
  if root.exists():reference_paths.extend(p for p in root.rglob('*') if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(project.resolve()))
 for p in reference_paths:
  if p.suffix.lower() in TEXT:
   total+=p.stat().st_size
   if p.stat().st_size>5*1024*1024 or total>30*1024*1024:reasons.append('Some reference files are too large to inspect safely.');break
   text.append(p.read_text(encoding='utf-8',errors='ignore'))
 content='\n'.join(text);dynamic=bool(re.search(r'\.src\s*=|setAttribute\s*\(\s*[\"\'](?:src|srcset)[\"\']|(?:fetch|import)\s*\(\s*(?![\"\'])|url\(\s*var\(',content,re.I))
 if dynamic:reasons.append('Scripts or styles build resource paths dynamically, so uncertain image files are protected.')
 candidates=[];recent=0;referenced=0
 for name,(size,modified) in before.items():
  if not (name.startswith(('assets/images/uploads/','assets/images/references/','studio-assets/')) and Path(name).suffix.lower() in IMAGE):continue
  if time.time()-modified/1e9<86400:recent+=1;continue
  filename=Path(name).name
  if filename in content or name in content:referenced+=1;continue
  if reasons:continue
  candidates.append({'path':name,'bytes':size,'sha256':hashlib.sha256((site/name).read_bytes()).hexdigest()})
 if inventory(site)!=before:raise ValueError('The website changed during the scan. Scan again after saving.')
 token=uuid.uuid4().hex
 with GUARD:
  for key in list(CACHE):
   if time.time()-CACHE[key]['created']>900:del CACHE[key]
  CACHE[token]={'project':str(project.resolve()),'inventory':before,'candidates':candidates,'created':time.time()}
 return {'token':token,'candidates':[{'path':c['path'],'bytes':c['bytes']} for c in candidates],'reasons':list(dict.fromkeys(reasons)),'recentProtected':recent,'referencedProtected':referenced,'protected':'Pages, stylesheets, scripts, fonts, icons, documents and uploads from the last 24 hours are never moved.','trashAvailable':latest_trash(project) is not None}

def move_to_trash(project,token,selected):
 with GUARD:
  snapshot=CACHE.get(token)
  if not snapshot or snapshot['project']!=str(project.resolve()) or time.time()-snapshot['created']>900:raise ValueError('Cleanup review expired. Scan again.')
  site=project/'site'
  if inventory(site)!=snapshot['inventory']:raise ValueError('The website changed after review. Save and scan again; nothing was moved.')
  allowed={c['path']:c for c in snapshot['candidates']};selected=list(dict.fromkeys(selected))
  if not selected or any(name not in allowed for name in selected):raise ValueError('Select only files listed in this cleanup review.')
  for name in selected:
   p=inside(site,name)
   if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=allowed[name]['sha256']:raise ValueError('A reviewed file changed. Scan again; nothing was moved.')
  batch=inside(project,'trash')/str(time.time_ns());files=batch/'files';files.mkdir(parents=True);moved=[]
  try:
   for name in selected:
    source=inside(site,name);dest=inside(files,name);dest.parent.mkdir(parents=True,exist_ok=True);os.replace(source,dest);moved.append(name)
   (batch/'manifest.json').write_text(json.dumps({'state':'trashed','created':time.time(),'files':selected}),encoding='utf-8')
  except Exception:
   for name in reversed(moved):
    target=inside(site,name);target.parent.mkdir(parents=True,exist_ok=True);os.replace(inside(files,name),target)
   raise
  CACHE.pop(token,None)
 return {'moved':len(moved),'trashAvailable':True,'message':'Selected unused uploads moved to project Trash. They are excluded from website export.'}

def latest_trash(project):
 trash=inside(project,'trash')
 if not trash.exists():return None
 for batch in sorted(trash.iterdir(),reverse=True):
  manifest=batch/'manifest.json'
  if not batch.is_symlink() and manifest.is_file():
   data=json.loads(manifest.read_text(encoding='utf-8'))
   if data.get('state')=='trashed':return batch,data
 return None

def restore(project):
 found=latest_trash(project)
 if not found:raise ValueError('There is no cleanup batch to restore.')
 batch,data=found;site=project/'site';files=batch/'files';restored=[]
 for name in data['files']:
  if inside(site,name).exists():raise ValueError('A restored filename would overwrite a current file. Nothing was restored.')
  if not inside(files,name).is_file():raise ValueError('A trash file is missing. Nothing was restored.')
 try:
  for name in data['files']:
   target=inside(site,name);target.parent.mkdir(parents=True,exist_ok=True);os.replace(inside(files,name),target);restored.append(name)
 except Exception:
  for name in reversed(restored):
   target=inside(files,name);target.parent.mkdir(parents=True,exist_ok=True);os.replace(inside(site,name),target)
  raise
 data['state']='restored';data['restored']=time.time();(batch/'manifest.json').write_text(json.dumps(data),encoding='utf-8');return {'restored':len(restored),'trashAvailable':latest_trash(project) is not None}

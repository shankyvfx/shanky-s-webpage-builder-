"""Conflict-checked, backed-up writes to an explicitly opened website folder."""
import hashlib,json,os,time,shutil
from pathlib import Path
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
def sync(project,folder):
 root=Path(folder).resolve();site=(project/'site').resolve()
 if not root.is_dir():raise ValueError('The save folder is unavailable. Reopen the folder or choose another save folder.')
 if root==Path(root.anchor) or root==site or root.is_relative_to(project.resolve()):raise ValueError('Choose a separate website folder.')
 statefile=project/'source-state.json';state=json.loads(statefile.read_text()) if statefile.exists() else {}
 if state.get('folder')!=str(root):state={'folder':str(root),'hashes':{p.relative_to(project/'original').as_posix():digest(p) for p in (project/'original').rglob('*') if p.is_file()}}
 changes=[]
 for src in site.rglob('*'):
  if not src.is_file() or src.is_symlink():continue
  rel=src.relative_to(site).as_posix();dst=root/rel
  if not dst.resolve().is_relative_to(root):raise ValueError('An unsafe folder link prevents saving: '+rel)
  new=digest(src);old=digest(dst)
  if new==old:continue
  if new==state['hashes'].get(rel):continue # An untouched working file must not overwrite an external edit.
  if old!=state['hashes'].get(rel):raise ValueError('Original file changed outside the builder: '+rel+'. Reopen that folder before overwriting it.')
  changes.append((src,dst,rel,old))
 backup=project/'source-backups'/str(time.time_ns());done=[]
 try:
  for src,dst,rel,old in changes:
   if digest(dst)!=old:raise ValueError('The original file changed during saving: '+rel)
   if old is not None:
    b=backup/rel;b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dst,b)
   dst.parent.mkdir(parents=True,exist_ok=True);tmp=dst.with_name(dst.name+'.shankys-save-tmp');shutil.copy2(src,tmp);os.replace(tmp,dst);done.append((dst,rel,old))
 except Exception:
  for dst,rel,old in reversed(done):
   if old is None:dst.unlink(missing_ok=True)
   else:shutil.copy2(backup/rel,dst)
  raise
 state['hashes']={p.relative_to(site).as_posix():digest(p) for p in site.rglob('*') if p.is_file() and not p.is_symlink()};statefile.write_text(json.dumps(state));return {'folder':str(root),'written':len(changes)}

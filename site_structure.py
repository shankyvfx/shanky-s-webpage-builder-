"""Conventional, collision-safe paths for newly created static websites."""
import html, posixpath, re, unicodedata
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
LAYOUT='organized-v1'
def slug(value,fallback='page'):
 value=unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode().lower();value=re.sub(r'[^a-z0-9]+','-',value).strip('-')[:80] or fallback
 if value in {'con','prn','aux','nul',*('com'+str(i) for i in range(1,10)),*('lpt'+str(i) for i in range(1,10))}:value+='-page'
 return value

def page_name(value):
 value=str(value).strip().replace('\\','/')
 if '/' in value or value.startswith('.') or not value:raise ValueError('Use a page name such as About Us, without folders.')
 return slug(Path(value).stem if value.lower().endswith('.html') else value)+'.html'

def relative_asset(page,asset):return posixpath.relpath(asset,posixpath.dirname(page) or '.')
def rebase_url(value,old_page,new_page):
 u=urlsplit(value)
 if not value or value.startswith(('#','/')) or u.scheme or u.netloc:return value
 absolute=posixpath.normpath(posixpath.join(posixpath.dirname(old_page),u.path));path=posixpath.relpath(absolute,posixpath.dirname(new_page) or '.')
 return urlunsplit(('', '',path,u.query,u.fragment))
def rebase_css(css,old_page,new_page):
 return re.sub(r'url\(\s*([\"\']?)(.*?)\1\s*\)',lambda m:'url("'+rebase_url(m[2],old_page,new_page)+'")',css,flags=re.I)
def rebase_html(source,old_page,new_page):
 source=re.sub(r'\b(href|src|poster|action)\s*=\s*([\"\'])(.*?)\2',lambda m:m[1]+'='+m[2]+html.escape(rebase_url(html.unescape(m[3]),old_page,new_page),quote=True)+m[2],source,flags=re.I)
 return re.sub(r'\bstyle\s*=\s*([\"\'])(.*?)\1',lambda m:'style='+m[1]+html.escape(rebase_css(html.unescape(m[2]),old_page,new_page),quote=True)+m[1],source,flags=re.I)

def write_asset(site,relative,content):
 path=site/relative;path.parent.mkdir(parents=True,exist_ok=True);candidate=path;number=1
 while candidate.exists() and candidate.read_text(encoding='utf-8')!=content:number+=1;candidate=path.with_name(path.stem+'-'+str(number).zfill(3)+path.suffix)
 if not candidate.exists():candidate.write_text(content,encoding='utf-8')
 return candidate.relative_to(site).as_posix()

def organize_html(site,page,source):
 stem=slug(posixpath.splitext(page)[0].replace('/','-'),'home');stem='home' if page=='index.html' else stem.removeprefix('pages-');counts={'css':0,'js':0}
 def stylesheet(match):
  attrs,css=match[1],match[2];counts['css']+=1
  identity=re.search(r'\bid\s*=\s*[\"\']([^\"\']+)',attrs,re.I);suffix='-'+slug(identity[1].removeprefix('studio-')) if identity else ('' if counts['css']==1 else '-'+str(counts['css']))
  rel='assets/css/'+stem+suffix+'.css';rel=write_asset(site,rel,rebase_css(css,page,rel)+'\n');return '<link rel="stylesheet"'+(' id="'+html.escape(identity[1],quote=True)+'"' if identity else '')+' href="'+relative_asset(page,rel)+'">'
 source=re.sub(r'<style\b([^>]*)>([\s\S]*?)</style\s*>',stylesheet,source,flags=re.I)
 def script(match):
  attrs,code=match[1],match[2]
  if re.search(r'\bsrc\s*=',attrs,re.I) or not code.strip():return match[0]
  kind=re.search(r'\btype\s*=\s*[\"\']([^\"\']+)',attrs,re.I)
  if kind and kind[1] not in ('module','text/javascript','application/javascript'):return match[0]
  counts['js']+=1;identity=re.search(r'\bid\s*=\s*[\"\']([^\"\']+)',attrs,re.I);suffix='-'+slug(identity[1].removeprefix('studio-')) if identity else '-'+str(counts['js']);rel='assets/js/'+stem+suffix+'.js';rel=write_asset(site,rel,code+'\n');return '<script'+attrs+' src="'+relative_asset(page,rel)+'"></script>'
 source=re.sub(r'<script\b([^>]*)>([\s\S]*?)</script\s*>',script,source,flags=re.I)
 # Generated drafts permit inline CSS; permit their extracted same-origin stylesheet too.
 source=source.replace("style-src 'unsafe-inline'","style-src 'self' 'unsafe-inline'")
 return source

def initialize(site,name):
 for directory in ('pages','assets/css','assets/js','assets/images/uploads','assets/images/references','assets/fonts','assets/icons','docs'):(site/directory).mkdir(parents=True,exist_ok=True)
 (site/'assets/js/main.js').write_text('// Add site-wide browser behaviour here.\n',encoding='utf-8')
 (site/'README.md').write_text('# '+str(name).replace('\n',' ')+'\n\nStatic website created with Shankys Website Builder.\n\n- index.html: home page\n- pages/: additional pages in lowercase-kebab-case.html\n- assets/css/: page stylesheets\n- assets/js/: browser scripts\n- assets/images/uploads/: uploaded photographs\n- assets/images/references/: reference image assets\n- assets/fonts/ and assets/icons/: custom fonts and icons\n- docs/: editing notes\n\nServe this folder with a static web server. Keep relative paths intact. Visual editor overrides may remain as inline styles; structured stylesheets hold the underlying design. No API credentials are part of this website.\n',encoding='utf-8')
 (site/'docs/editing-guide.md').write_text('# Editing guide\n\nUse descriptive lowercase names separated by hyphens. Additional pages belong in pages/. Keep a complete copy when deploying; images, styles and scripts are separate assets. New upload names receive -002, -003 etc. when a name already exists.\n',encoding='utf-8')

def image_path(site,filename,category='uploads'):
 category=category if category in ('uploads','references') else 'uploads';stem=slug(Path(filename).stem,'photo')
 if re.fullmatch(r'[a-f0-9]{16,}',stem):stem='photo'
 ext=Path(filename).suffix.lower();base=Path('assets/images')/category;number=1;path=base/(stem+ext)
 while (site/path).exists():number+=1;path=base/(stem+'-'+str(number).zfill(3)+ext)
 return path.as_posix()

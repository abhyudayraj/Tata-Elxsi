"""Local LabelOps prototype: OpenCV artwork comparison + optional LLM review."""
from __future__ import annotations
import base64, json, os, re, threading, time, uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageStat
import io

ROOT = Path(__file__).resolve().parent
WEB = ROOT / 'outputs' / 'index.html'
DATA = ROOT / 'work' / 'labelops-data.json'
UPLOADS = ROOT / 'work' / 'uploads'
UPLOADS.mkdir(parents=True, exist_ok=True)
DATA.parent.mkdir(parents=True, exist_ok=True)
MAX_BODY = 18 * 1024 * 1024
MAX_UPLOAD_BODY = 38 * 1024 * 1024
LOCK = threading.Lock()

def load_env_file():
    env_file=ROOT/'.env'
    if not env_file.exists(): return
    for line in env_file.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        key,value=line.split('=',1); key=key.strip(); value=value.strip().strip('"').strip("'")
        if key and key not in os.environ: os.environ[key]=value

load_env_file()

def seed():
    return {
      'requests': [
        {'id':'ECO-2026-0142','title':'Add MRI safety statement','product':'CardioFlex Stent System','markets':['US','EU'],'status':'In review','updated':'Today, 09:42','owner':'A. Morgan','description':'Add approved MR-conditional safety statement.'},
        {'id':'ECO-2026-0138','title':'UDI carrier size correction','product':'NovaDx Analyzer','markets':['US','EU','Japan'],'status':'Needs attention','updated':'Today, 08:16','owner':'J. Patel','description':'Verify UDI carrier sizing against source.'},
        {'id':'ECO-2026-0131','title':'Packaging material update','product':'OrthoGuide Instrument Set','markets':['EU','China'],'status':'In review','updated':'Yesterday','owner':'L. Chen','description':'Packaging change impact assessment.'},
        {'id':'ECO-2026-0125','title':'IFU translation revision','product':'Vascular Access Kit','markets':['US','EU'],'status':'Approved','updated':'Oct 09','owner':'M. Rivera','description':'Controlled translation update.'}
      ],
      'audit': [{'time':'Today, 09:42','actor':'A. Morgan','event':'Impact assessment requested for MRI safety statement','ref':'ECO-2026-0142'}],
      'comparisons': []
    }

def load_data():
    if not DATA.exists():
        d=seed(); save_data(d); return d
    try: return json.loads(DATA.read_text(encoding='utf-8'))
    except Exception: return seed()

def save_data(d): DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')

def audit(d, actor, event, ref):
    d['audit'].insert(0,{'time':datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z'),'actor':actor,'event':event,'ref':ref})

def safe_image(raw, name):
    if len(raw)>MAX_BODY: raise ValueError('Image exceeds the 18 MB limit')
    try:
        img=Image.open(io.BytesIO(raw)).convert('RGB')
        if img.width*img.height > 28_000_000: raise ValueError('Image dimensions exceed the 28 megapixel limit')
        return img
    except ValueError: raise
    except Exception as e: raise ValueError(f'Could not read image {name}: use PNG, JPG or WEBP') from e

def img_data(img, fmt='PNG'):
    b=io.BytesIO(); img.save(b,format=fmt); return 'data:image/'+fmt.lower()+';base64,'+base64.b64encode(b.getvalue()).decode('ascii')

def compare_artwork(base_raw, revised_raw, base_name, revised_name):
    a=safe_image(base_raw,base_name); b=safe_image(revised_raw,revised_name)
    same_size=a.size==b.size
    if not same_size:
        b=b.resize(a.size,Image.Resampling.LANCZOS)
    # OpenCV is used when available; Pillow fallback keeps the local demo runnable.
    cv_backend=False; regions=[]
    try:
        import cv2, numpy as np
        aa=cv2.cvtColor(np.array(a),cv2.COLOR_RGB2GRAY); bb=cv2.cvtColor(np.array(b),cv2.COLOR_RGB2GRAY)
        delta=cv2.absdiff(aa,bb); _,mask=cv2.threshold(delta,24,255,cv2.THRESH_BINARY)
        mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8)); mask=cv2.dilate(mask,np.ones((5,5),np.uint8),iterations=1)
        contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        total=a.width*a.height; changed=int(cv2.countNonZero(mask));
        for cnt in sorted(contours,key=cv2.contourArea,reverse=True):
            x,y,w,h=cv2.boundingRect(cnt); area=w*h
            if area<max(32,total*0.000025): continue
            regions.append({'x':round(x/a.width,4),'y':round(y/a.height,4),'w':round(w/a.width,4),'h':round(h/a.height,4),'area':area})
            if len(regions)>=20: break
        overlay=cv2.cvtColor(np.array(b),cv2.COLOR_RGB2RGBA)
        tint=np.zeros_like(overlay); tint[:,:,:3]=(231,73,81); tint[:,:,3]=110
        full=np.zeros((a.height,a.width),dtype=np.uint8)
        for r in regions:
            x=int(r['x']*a.width);y=int(r['y']*a.height);w=int(r['w']*a.width);h=int(r['h']*a.height); cv2.rectangle(overlay,(x,y),(x+w,y+h),(233,68,74,230),max(2,int(a.width/700)))
        cv_backend=True
    except ImportError:
        g1=a.convert('L').filter(ImageFilter.GaussianBlur(1.1)); g2=b.convert('L').filter(ImageFilter.GaussianBlur(1.1)); diff=ImageChops.difference(g1,g2).point(lambda p:255 if p>24 else 0)
        changed=sum(ImageStat.Stat(diff).mean)/255*(a.width*a.height); total=a.width*a.height
        # connected components, using Pillow fallback: a single bounding region on changed pixels.
        box=diff.getbbox()
        if box:
            x,y,x2,y2=box; regions=[{'x':x/a.width,'y':y/a.height,'w':(x2-x)/a.width,'h':(y2-y)/a.height,'area':(x2-x)*(y2-y)}]
        overlay=b.convert('RGBA')
        if box:
            from PIL import ImageDraw
            ImageDraw.Draw(overlay).rectangle(box,outline=(230,65,75,255),width=max(2,a.width//700))
    pct=round(min(100,changed/total*100),2) if total else 0
    result={'id':'CMP-'+datetime.now().strftime('%Y%m%d')+'-'+uuid.uuid4().hex[:6].upper(),'createdAt':datetime.now().astimezone().isoformat(timespec='seconds'),'baselineName':Path(base_name).name,'revisedName':Path(revised_name).name,'width':a.width,'height':a.height,'sameDimensions':same_size,'changedPercent':pct,'regionCount':len(regions),'regions':regions,'engine':'OpenCV' if cv_backend else 'Pillow fallback','baselinePreview':img_data(a),'revisedPreview':img_data(b),'overlay':img_data(overlay),'status':'Needs human review','notes':[]}
    if not same_size: result['notes'].append('Image dimensions differ; revised artwork was resized for visual comparison. Confirm print dimensions separately.')
    if pct>0: result['notes'].append('Difference detection is a visual screening aid. Inspect every highlighted region and confirm text, symbols, UDI and layout against controlled sources.')
    else: result['notes'].append('No changes crossed the current visual threshold. This does not establish that the files or label content are identical.')
    return result

def llm_review(payload):
    key=os.getenv('LLM_API_KEY','').strip(); base=os.getenv('LLM_BASE_URL','https://api.openai.com/v1').rstrip('/'); model=os.getenv('LLM_MODEL','gpt-4o-mini')
    if not key: return {'mode':'rules-only','model':None,'summary':'No LLM configured. This result uses only image-difference metadata; it is not a compliance assessment.','findings':['Review each highlighted area visually.','Check product identifiers, UDI, warnings, symbols, languages and revision against approved source records.','Obtain Regulatory Affairs and Quality approval before release.'],'configured':False}
    try:
        import requests
        prompt={'comparison':{k:payload.get(k) for k in ['baselineName','revisedName','width','height','sameDimensions','changedPercent','regionCount','regions','notes']},'instruction':'Provide a concise, cautious artwork-review triage. Treat region boxes as normalized image coordinates. Do not claim regulatory compliance or infer text not supplied. Return JSON with summary (string), findings (array of strings), and severity (low|medium|high). Explicitly require human review.'}
        res=requests.post(base+'/chat/completions',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},json={'model':model,'temperature':0.1,'messages':[{'role':'system','content':'You assist medical-device labeling reviewers. You are advisory only; never approve or release labeling. State uncertainty.'},{'role':'user','content':json.dumps(prompt)}]},timeout=75)
        res.raise_for_status(); content=res.json()['choices'][0]['message']['content'];
        try: body=json.loads(re.sub(r'^```(?:json)?\s*|\s*```$','',content.strip()))
        except Exception: body={'summary':content[:1800],'findings':['Review the model response manually.'],'severity':'medium'}
        return {'mode':'llm-assisted','model':model,'configured':True,**body}
    except Exception as e: return {'mode':'llm-error','model':model,'configured':True,'summary':'LLM request failed; image comparison remains available.','findings':[str(e)[:400],'Review the artwork manually and check server logs.'],'severity':'unknown'}

class Handler(BaseHTTPRequestHandler):
    server_version='LabelOpsLocal/1.0'
    def log_message(self,fmt,*args): print('[%s] %s'%(self.log_date_time_string(),fmt%args))
    def respond(self,code,obj,ctype='application/json; charset=utf-8'):
        data=obj if isinstance(obj,bytes) else json.dumps(obj,ensure_ascii=False).encode('utf-8')
        self.send_response(code); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(data))); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(data)
    def read_json(self):
        n=int(self.headers.get('Content-Length','0'))
        if n>MAX_BODY: raise ValueError('Request exceeds size limit')
        return json.loads(self.rfile.read(n) or b'{}')
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/':
            try: self.respond(200,WEB.read_bytes(),'text/html; charset=utf-8')
            except Exception: self.respond(500,{'error':'outputs/index.html missing'})
        elif path=='/api/health': self.respond(200,{'ok':True,'opencv':self.opencv_available(),'llmConfigured':bool(os.getenv('LLM_API_KEY')),'mode':'local-demo'})
        elif path=='/api/state':
            with LOCK: self.respond(200,load_data())
        elif path=='/api/config': self.respond(200,{'llmConfigured':bool(os.getenv('LLM_API_KEY')),'model':os.getenv('LLM_MODEL','gpt-4o-mini'),'opencv':self.opencv_available()})
        else: self.respond(404,{'error':'Not found'})
    def do_POST(self):
        path=urlparse(self.path).path
        try:
            if path=='/api/change-requests':
                b=self.read_json()
                for k in ['title','product','description']:
                    if not str(b.get(k,'')).strip(): return self.respond(400,{'error':f'{k} is required'})
                with LOCK:
                    d=load_data(); rid='ECO-'+datetime.now().strftime('%Y')+'-'+str(int(time.time()*1000))[-6:]
                    row={'id':rid,'title':str(b['title'])[:160],'product':str(b['product'])[:160],'markets':b.get('markets',[]),'description':str(b['description'])[:2500],'status':'Draft','updated':'Just now','owner':'Local user'}
                    d['requests'].insert(0,row); audit(d,'Local user','Created change request: '+row['title'],rid); save_data(d)
                return self.respond(201,row)
            if path=='/api/compare':
                n=int(self.headers.get('Content-Length','0'))
                if n>MAX_UPLOAD_BODY: return self.respond(413,{'error':'Combined upload exceeds 36 MB'})
                ctype=self.headers.get('Content-Type','')
                if not ctype.startswith('multipart/form-data'): return self.respond(415,{'error':'Use multipart form data'})
                body=self.rfile.read(n); boundary=re.search(r'boundary=(?:"([^"]+)"|([^;]+))',ctype)
                if not boundary: return self.respond(400,{'error':'Missing multipart boundary'})
                bd=(boundary.group(1) or boundary.group(2)).encode(); parts=body.split(b'--'+bd); files={}
                for part in parts:
                    if b'\r\n\r\n' not in part: continue
                    head,data=part.split(b'\r\n\r\n',1); data=data.removesuffix(b'\r\n').removesuffix(b'--\r\n').removesuffix(b'--')
                    m=re.search(rb'name="(baseline|revised)"; filename="([^"]*)"',head)
                    if m:
                        if len(data)>MAX_BODY: return self.respond(413,{'error':'Each image must be no larger than 18 MB'})
                        files[m.group(1).decode()]=(m.group(2).decode(errors='replace'),data)
                if 'baseline' not in files or 'revised' not in files: return self.respond(400,{'error':'Upload both baseline and revised artwork files'})
                result=compare_artwork(files['baseline'][1],files['revised'][1],files['baseline'][0],files['revised'][0]); result['review']=llm_review(result)
                with LOCK:
                    d=load_data(); d['comparisons'].insert(0,result); d['comparisons']=d['comparisons'][:30]; audit(d,'Local user',f"Compared artwork: {result['changedPercent']}% visual difference",result['id']); save_data(d)
                return self.respond(200,result)
            if path=='/api/audit':
                b=self.read_json(); withlock=LOCK
                with withlock:
                    d=load_data(); audit(d,str(b.get('actor','Local user'))[:80],str(b.get('event','Workspace event'))[:300],str(b.get('ref','-'))[:80]); save_data(d)
                return self.respond(201,{'ok':True})
            self.respond(404,{'error':'Not found'})
        except ValueError as e: self.respond(400,{'error':str(e)})
        except Exception as e: self.respond(500,{'error':str(e)[:600]})
    @staticmethod
    def opencv_available():
        try: import cv2; return True
        except ImportError: return False

def main():
    host=os.getenv('APP_HOST','127.0.0.1'); port=int(os.getenv('APP_PORT','8765'))
    httpd=ThreadingHTTPServer((host,port),Handler); print(f'LabelOps running at http://{host}:{port}'); print('OpenCV:',Handler.opencv_available(),'| LLM configured:',bool(os.getenv('LLM_API_KEY'))); print('Press Ctrl+C to stop.');
    try: httpd.serve_forever()
    except KeyboardInterrupt: print('\nStopping LabelOps...')
    finally: httpd.server_close()
if __name__=='__main__': main()

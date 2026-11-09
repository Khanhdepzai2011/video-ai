"""KAZ Factory V4: video draft generator, not an automatic publisher."""
from __future__ import annotations
import argparse, asyncio, csv, json, re, shutil, subprocess
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
W,H=540,960

def font(size):
    for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','C:/Windows/Fonts/arial.ttf']:
        if Path(p).exists(): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def run(cmd):
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)

def stamp(seconds):
    ms=round(seconds*1000)
    h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

def wrap(text,draw,f,width):
    lines=[]; cur=''
    for word in text.split():
        new=(cur+' '+word).strip()
        if draw.textbbox((0,0),new,font=f)[2]<=width:cur=new
        else:
            if cur:lines.append(cur)
            cur=word
    if cur:lines.append(cur)
    return lines

def cover(path,title,index):
    im=Image.new('RGB',(W,H)); d=ImageDraw.Draw(im)
    for y in range(H):
        k=y/H; d.line((0,y,W,y),fill=(int(11+27*k),int(25+33*k),int(57+52*k)))
    d.rounded_rectangle((28,258,512,725),radius=26,fill=(13,22,43),outline=(89,161,232),width=3)
    d.text((38,85),f'KAZ FACTORY / EP {index:03}',font=font(24),fill=(162,213,255))
    for j,line in enumerate(wrap(title,d,font(37),430)[:6]):
        d.text((46,345+j*60),line,font=font(37),fill='white')
    d.text((45,852),'KIEN THUC / KHAM PHA',font=font(21),fill=(194,210,237))
    im.save(path)

def photo(src,out):
    with Image.open(src) as im:
        im=im.convert('RGB')
        ratio=max(W/im.width,H/im.height)
        w,h=round(im.width*ratio),round(im.height*ratio)
        im=im.resize((w,h),Image.Resampling.LANCZOS)
        x=(w-W)//2;y=(h-H)//2
        im.crop((x,y,x+W,y+H)).save(out)

def draft_script(topic):
    # General unverified writing template. Not an LLM response.
    return (f'Hôm nay chúng ta cùng khám phá chủ đề: {topic}. '
            f'Trước tiên, hãy hiểu bối cảnh và các khái niệm quan trọng. '
            f'Tiếp theo, thử quan sát một ví dụ thực tế và so sánh những góc nhìn khác nhau. '
            f'Khi gặp thông tin mới, cần kiểm tra nguồn và xem dữ kiện có đáng tin cậy hay không. '
            f'Cuối cùng, bạn muốn tìm hiểu sâu hơn điều gì về chủ đề thú vị này?')

def srt_file(path,script,duration):
    parts=[x.strip() for x in re.split(r'(?<=[.!?;:])\s+',script.strip()) if x.strip()]
    if not parts:parts=[script.strip()]
    lengths=[max(1,len(x)) for x in parts];total=sum(lengths);cursor=0
    with path.open('w',encoding='utf-8') as f:
        for i,part in enumerate(parts):
            end=duration if i==len(parts)-1 else cursor+duration*lengths[i]/total
            f.write(f'{i+1}\n{stamp(cursor)} --> {stamp(end)}\n{part}\n\n')
            cursor=end

def tts(script,path):
    import edge_tts
    async def speak():
        await edge_tts.Communicate(script,voice='vi-VN-HoaiMyNeural').save(str(path))
    asyncio.run(speak())

def audio_duration(path):
    p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)],capture_output=True,text=True,check=True)
    return float(p.stdout.strip())

def render(image,audio,subtitles,out,duration,burn):
    # One frame with gentle zoom/crop motion, using CPU-only FFmpeg.
    vf="scale=610:1084,crop=540:960:x='35+15*sin(n/110)':y='60+20*cos(n/135)',fps=20,format=yuv420p"
    if burn:
        p=str(subtitles.resolve()).replace('\\','/').replace(':','\\:').replace("'","\\'")
        vf+=f",subtitles='{p}':force_style='Fontname=DejaVu Sans,Fontsize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00222222,Outline=2,Alignment=2,MarginV=85'"
    cmd=['ffmpeg','-y','-hide_banner','-loglevel','error','-loop','1','-framerate','20','-i',str(image)]
    if audio:cmd+=['-i',str(audio)]
    else:cmd+=['-f','lavfi','-i','anullsrc=r=44100:cl=stereo']
    cmd+=['-t',str(duration),'-vf',vf,'-c:v','libx264','-preset','ultrafast','-crf','29','-r','20','-pix_fmt','yuv420p','-map','0:v:0','-map','1:a:0','-c:a','aac','-b:a','96k','-movflags','+faststart',str(out)]
    run(cmd)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--count',type=int,default=1)
    ap.add_argument('--date',default=None)
    ap.add_argument('--duration',type=int,default=42)
    ap.add_argument('--voice',choices=['none','edge'],default='none')
    ap.add_argument('--start',default='06:00')
    ap.add_argument('--burn-subs',action='store_true')
    args=ap.parse_args()
    if not (1<=args.count<=50 and 35<=args.duration<=50):ap.error('Count 1-50; duration 35-50')
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):ap.error('ffmpeg and ffprobe required')
    topics=[s.strip() for s in (ROOT/'topics/topics.txt').read_text(encoding='utf-8').splitlines() if s.strip() and not s.startswith('#')]
    if not topics:ap.error('No topics available')
    date=args.date or datetime.now().strftime('%Y-%m-%d')
    start=datetime.strptime(f'{date} {args.start}','%Y-%m-%d %H:%M')
    root=Path('output')/date;root.mkdir(parents=True,exist_ok=True)
    rows=[]
    for i in range(args.count):
        title=topics[i%len(topics)]
        folder=root/f'video_{i+1:03d}';folder.mkdir(exist_ok=True)
        script=draft_script(title)
        (folder/'script.txt').write_text(script,encoding='utf-8')
        pic=folder/'cover.png'
        asset=ROOT/'assets'/f'video_{i+1:03d}.png'
        if asset.is_file():photo(asset,pic);image_source='LICENSED_ASSET'
        else:cover(pic,title,i+1);image_source='GRAPHIC_TEMPLATE'
        audio=None
        if args.voice=='edge':
            audio=folder/'voice.mp3'
            tts(script,audio)
            length=audio_duration(audio)
            if length>args.duration:raise RuntimeError(f'TTS audio {length:.1f}s exceeds target {args.duration}s; revise script')
        subs=folder/'subtitles.srt';srt_file(subs,script,args.duration)
        out=folder/'video.mp4';render(pic,audio,subs,out,args.duration,args.burn_subs)
        schedule=start+timedelta(seconds=17*3600*i/args.count)
        rows.append(dict(file=str(out.relative_to(root)),thumbnail=str(pic.relative_to(root)),
            subtitles=str(subs.relative_to(root)),title=title,caption=f'{title} — nội dung cần kiểm chứng trước khi đăng.',
            hashtags='#KhamPha #KienThuc #Shorts',scheduled_local=schedule.strftime('%Y-%m-%d %H:%M:%S'),
            timezone='Asia/Ho_Chi_Minh',platforms='TikTok;YouTube Shorts;Facebook Reels',
            status='REVIEW_REQUIRED',image_source=image_source,voice_source='EDGE_TTS' if audio else 'NONE',
            subtitle_timing='APPROXIMATE',published=False))
        print(f'Created {i+1}/{args.count}: {out}',flush=True)
    with (root/'schedule.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (root/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Drafts ready for review:',root)

if __name__=='__main__':main()

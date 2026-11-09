"""KAZ V5: six-scene cinematic draft generator using freely licensed Commons media."""
import argparse, asyncio, csv, html, json, math, random, re, subprocess, time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageOps

ROOT=Path(__file__).resolve().parent
API="https://commons.wikimedia.org/w/api.php"
UA={"User-Agent":"KAZ-Cinematic-Educational/1.0 (video draft generator; contact via github.com/Khanhdepzai2011/video-ai)"}
W,H=540,960

def cmd(args):
    p=subprocess.run(args,capture_output=True,text=True)
    if p.returncode: raise RuntimeError("FFmpeg: "+p.stderr[-2500:])
    return p.stdout

def font(size):
    for path in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf","C:/Windows/Fonts/arialbd.ttf"]:
        if Path(path).exists():return ImageFont.truetype(path,size)
    return ImageFont.load_default()

def get_media(query,seen):
    params={"action":"query","generator":"search","gsrsearch":query+" filetype:bitmap","gsrnamespace":6,
            "gsrlimit":20,"prop":"imageinfo","iiprop":"url|size|extmetadata","format":"json","iiurlwidth":900}
    data=requests.get(API,params=params,headers=UA,timeout=30).json()
    options=[]
    for page in data.get("query",{}).get("pages",{}).values():
        info=(page.get("imageinfo") or [{}])[0]
        url=info.get("thumburl") or info.get("url","")
        meta=info.get("extmetadata",{})
        license_name=html.unescape(re.sub("<[^>]+>","",meta.get("LicenseShortName",{}).get("value",""))).strip()
        if not url.lower().split("?")[0].endswith((".jpg",".jpeg",".png",".webp")):continue
        if info.get("width",0)<500 or info.get("height",0)<500:continue
        if not any(k in license_name.lower() for k in ("cc by","cc0","public domain","pdm")):continue
        if page.get("title") in seen:continue
        options.append((page,info,url,license_name))
    if not options:raise RuntimeError("No eligible licensed photograph for: "+query)
    # Deterministic ranking; avoid unrelated random photos.
    terms=[w.lower() for w in re.findall(r"[a-zA-Z]+",query) if len(w)>3]
    def score(entry):
        page=entry[0]
        title=page.get("title","").lower()
        return sum(3 for w in terms if w in title)
    options.sort(key=lambda entry:(-score(entry),entry[0].get("title","")))
    return options[0]

def download_photo(query,path,seen):
    page,info,url,license_name=get_media(query,seen)
    data=requests.get(url,headers=UA,timeout=60)
    data.raise_for_status()
    if len(data.content)>14_000_000:raise RuntimeError("Image too large")
    from io import BytesIO
    with Image.open(BytesIO(data.content)) as im:
        im=ImageOps.exif_transpose(im).convert("RGB")
        im=ImageOps.fit(im,(650,1150),method=Image.Resampling.LANCZOS,centering=(.5,.5))
        im=ImageEnhance.Contrast(im).enhance(1.12)
        im.save(path,quality=89)
    seen.add(page["title"])
    m=info.get("extmetadata",{})
    def field(k):
        return html.unescape(re.sub("<[^>]+>","",m.get(k,{}).get("value",""))).strip()
    return {"title":page["title"],"source":"https://commons.wikimedia.org/wiki/"+page["title"].replace(" ","_"),
            "license":license_name,"artist":field("Artist"),"credit":field("Credit"),
            "license_url":field("LicenseUrl"),"query":query}

async def make_voice(text,out):
    import edge_tts
    comm=edge_tts.Communicate(text,voice="vi-VN-NamMinhNeural",rate="+7%")
    with out.open("wb") as f:
        async for event in comm.stream():
            if event["type"]=="audio":f.write(event["data"])
    if out.stat().st_size<1000:raise RuntimeError("No audio returned by Edge TTS")

def duration(path):
    return float(cmd(["ffprobe","-v","error","-show_entries","format=duration","-of",
                      "default=noprint_wrappers=1:nokey=1",str(path)]).strip())

def ass_stamp(s):
    h=int(s//3600);m=int(s%3600//60);sec=s%60
    return f"{h}:{m:02}:{sec:05.2f}"

def ass_escape(s):
    return s.replace("\\","").replace("{","(").replace("}",")").replace("\n"," ")

def subtitles(text,path,total):
    words=text.split()
    # Approximate word timing based on word length, not forced audio alignment.
    weights=[max(2,len(w)) for w in words]
    unit=total/sum(weights)
    header="""[Script Info]
ScriptType: v4.00+
PlayResX: 540
PlayResY: 960
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,DejaVu Sans,30,&H00FFFFFF,&H0000D7FF,&H00101010,&H90000000,-1,0,0,0,100,100,0,0,1,3,1,2,32,32,118,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events=[];elapsed=0
    for i in range(0,len(words),5):
        ws=words[i:i+5];start=elapsed;chunks=[]
        for j,w in enumerate(ws):
            length=weights[i+j]*unit;elapsed+=length
            chunks.append(r"{\k"+str(max(1,round(length*100)))+"}"+ass_escape(w))
        events.append(f"Dialogue: 0,{ass_stamp(start)},{ass_stamp(min(total,elapsed))},Karaoke,,0,0,0,,{' '.join(chunks)}")
    path.write_text(header+"\n".join(events)+"\n",encoding="utf-8")

def thumb(image,title,path):
    with Image.open(image) as source:
        im=ImageOps.fit(source.convert("RGB"),(W,H))
    shade=Image.new("RGBA",(W,H),(0,0,0,0));d=ImageDraw.Draw(shade)
    for y in range(H):
        alpha=int(20+190*max(0,(y-250)/710))
        d.line((0,y,W,y),fill=(0,7,18,alpha))
    im=Image.alpha_composite(im.convert("RGBA"),shade)
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((30,80,255,129),radius=12,fill=(7,32,53,220))
    d.text((44,88),"KAZ  /  KHÁM PHÁ",font=font(18),fill=(255,214,65))
    words=title.split();lines=[];current=""
    for w in words:
        test=(current+" "+w).strip()
        if d.textbbox((0,0),test,font=font(40))[2]<W-70:current=test
        else:lines.append(current);current=w
    if current:lines.append(current)
    for j,line in enumerate(lines[:5]):
        d.text((35,610+j*62),line,font=font(40),fill="white",stroke_width=3,stroke_fill=(0,0,0))
    im.convert("RGB").save(path,quality=92)

def scene_durations(scenes,total):
    # Scene length follows narration length, not equal slices.
    weights=[max(10,len(scene["narration"].split())) for scene in scenes]
    lengths=[total*w/sum(weights) for w in weights]
    return lengths

def render_scenes(images,out,seconds,scene_lengths):
    # 6 moving scenes with crossfades, 0.45 second overlap.
    n=len(images);transition=.35
    lengths=[x+transition if i<n-1 else x for i,x in enumerate(scene_lengths)]
    inputs=[]
    for image,length in zip(images,lengths):
        inputs+=["-loop","1","-framerate","20","-t",f"{length:.3f}","-i",str(image)]
    filters=[]
    for i in range(n):
        # Alternating subtle Ken Burns crop with safe dimensions.
        dx="35+12*sin(n/38)" if i%2 else "35+12*cos(n/42)"
        filters.append(f"[{i}:v]scale=610:1084,crop=540:960:x='{dx}':y='60+14*sin(n/48)',"
                       f"fps=20,setsar=1,format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS[v{i}]")
    prev="v0"
    for i in range(1,n):
        label=f"x{i}"
        offset=sum(scene_lengths[:i])
        filters.append(f"[{prev}][v{i}]xfade=transition=fade:duration={transition}:offset={offset:.3f}[{label}]")
        prev=label
    cmd(["ffmpeg","-y","-hide_banner","-loglevel","error",*inputs,"-filter_complex",";".join(filters),
         "-map",f"[{prev}]","-t",f"{seconds:.3f}","-c:v","libx264","-preset","veryfast",
         "-crf","25","-pix_fmt","yuv420p","-an",str(out)])

def mux(silent,audio,ass,out,target):
    escaped=str(ass.resolve()).replace("\\","/").replace(":","\\:")
    cmd(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(silent),"-i",str(audio),
         "-filter_complex",f"[0:v]subtitles=filename='{escaped}'[v]",
         "-map","[v]","-map","1:a:0","-t",f"{target:.3f}","-c:v","libx264",
         "-preset","veryfast","-crf","25","-c:a","aac","-b:a","128k","-movflags","+faststart",str(out)])

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--count",type=int,default=1)
    parser.add_argument("--duration",type=int,default=45)
    args=parser.parse_args()
    topics=json.loads((ROOT/"v5_topics.json").read_text(encoding="utf-8"))
    if not 1<=args.count<=len(topics):parser.error("Count must fit reviewed topic library")
    if not 35<=args.duration<=50:parser.error("Duration must be 35-50 seconds")
    out=Path("output-v5")/datetime.utcnow().strftime("%Y-%m-%d")
    out.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for i,topic in enumerate(topics[:args.count]):
        work=out/f"video_{i+1:03}";work.mkdir(exist_ok=True)
        scenes=topic["scenes"]
        narration=" ".join(scene["narration"] for scene in scenes)
        (work/"script.txt").write_text(narration,encoding="utf-8")
        voice=work/"voice.mp3"
        asyncio.run(make_voice(narration,voice))
        speech=duration(voice)
        if speech>args.duration:
            raise RuntimeError(f"Narration {speech:.1f}s exceeds {args.duration}s; increase duration or shorten script")
        # Align visuals and subtitles with spoken narration, allowing a final visual hold.
        seen=set();images=[];credits=[]
        for j,scene in enumerate(scenes):
            query=scene["query"]
            image=work/f"scene_{j+1:02}.jpg"
            credit=download_photo(query,image,seen)
            # Reject clearly off-topic search results instead of quietly showing them.
            name=credit["title"].lower()
            if not any(k.lower() in name for k in scene["keywords"]):
                raise RuntimeError(f"Scene {j+1} mismatch: expected {scene['visual']}, got {credit['title']}")
            credit.update({"scene":j+1,"narration":scene["narration"],"visual_intent":scene["visual"]})
            credits.append(credit)
            images.append(image)
        (work/"attribution.json").write_text(json.dumps(credits,ensure_ascii=False,indent=2),encoding="utf-8")
        subtitles(narration,work/"karaoke.ass",speech)
        lengths=scene_durations(scenes,args.duration)
        timeline=[];cursor=0
        for j,(scene,length) in enumerate(zip(scenes,lengths)):
            timeline.append({"scene":j+1,"start":round(cursor,2),"end":round(cursor+length,2),
                             "narration":scene["narration"],"visual":scene["visual"]})
            cursor+=length
        (work/"scene_timeline.json").write_text(json.dumps(timeline,ensure_ascii=False,indent=2),encoding="utf-8")
        thumb(images[0],topic["title"],work/"thumbnail.jpg")
        silent=work/"scenes.mp4"
        render_scenes(images,silent,args.duration,lengths)
        mux(silent,voice,work/"karaoke.ass",work/"video.mp4",args.duration)
        silent.unlink()
        item={"title":topic["title"],"video":str(work/"video.mp4"),"thumbnail":str(work/"thumbnail.jpg"),
              "duration":args.duration,"narration_seconds":round(speech,2),"scenes":6,
              "subtitle_sync":"estimated","status":"REVIEW_REQUIRED","published":False}
        manifest.append(item)
        print("SUCCESS",item["video"],flush=True)
    (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    with (out/"schedule.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=manifest[0].keys());writer.writeheader();writer.writerows(manifest)
if __name__=="__main__":main()

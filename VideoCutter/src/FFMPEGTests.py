'''
Created on Nov 26, 2016

@author: matze
'''
from FFMPEGTools import FFStreamProbe,FFPacketProbe,OSTools,FFmpegVersion,FormatMapGenerator
import os
import subprocess
#from subprocess import Popen
#from datetime import timedelta
import re
#import fcntl
#from time import sleep
#from numpy import block

'''
Slow way to get the i frames in json:
ffprobe -show_frames -select_streams v -print_format json=c=1 sourceFile

'''

'''
if __name__ == "__main__":
    m = FFMPEGCutter("/home/matze/Videos/T3.m2t","/home/matze/Videos/T3x.mp4")
    starttd = timedelta(seconds=5)
    endtd = timedelta(seconds=700)
    m.cutPart(starttd, endtd, 0)

'''
                           

#WORKS!
def execute(cmd):
    popen = subprocess.Popen(cmd, stdout=subprocess.PIPE,stderr=subprocess.STDOUT, universal_newlines=True)
    for stdout_line in iter(popen.stdout.readline, ""):
        yield stdout_line 
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd)

def testParse():
   
    text="35903,*:P:129201120 (2627310857) D:129201120 (2627310857) Pt:1435.568 Dt:1435.568 idx: (1) dur 2880 (2880) size: 1536 flags: 1"
   
    m = re.search('[0-9]+',text)
    frame = m.group(0)
    m = re.search('Dt:[0-9]+.[0-9]',text)
    p1 = m.group(0)
    dts = p1[3:]

    print('Frame: %s DTS %s'%(frame,dts))

def testPath():
    p= OSTools().getWorkingDirectory();
    print (p)
    tail="ffmpeg/bin/remux5"
    fn = os.path.join(p,tail)
    ok= os.path.isfile(fn)
    print(fn," ok:",ok)

def testNonblockingRead():
    #cmd=["/usr/bin/ffmpeg","-i","/home/matze/Videos/pur/purX.m2t","-y","/home/matze/Videos/pur/xx.mpg"]
    cmd=["/usr/bin/pfmpeg","-i","/home/matze/Videos/pur/purX.m2t","-y","/home/matze/Videos/pur/xx.mpg"]
    #pFFmpeg = subprocess.Popen(cmd , stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True)
    #pFFmpeg = subprocess.Popen(cmd , stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for path in execute(cmd):
            print(path,end="")
    except Exception as error:
        print("Error : %s"%(error))

#     while pFFmpeg.poll() is None:
#         #?sleep(0.2)   
#         if not non_block_read("Test:",pFFmpeg.stdout):
#             print("Cutting part %s failed"%("x"))
#             return False

  
def testFrameProbe():
    #m=FFStreamProbe("/home/matze/Videos/Handy-M4-Test/MOV_0296.MP4")
    #m=FFStreamProbe("/media/matze/Datastore/Videos/VCR/KiKA/11_13_19_25-pur+.m2t")
    #m=FFStreamProbe("/media/matze/Datastore/Videos/VCR/3sat_HD/11_24_07_00-nano.m2t")
    #m=FFStreamProbe("/media/matze/Datastore/Videos/6.Folge Craftattack.mp4")
    #m=FFStreamProbe("/home/matze/Videos/20051210-w50s.flv")
    #m=FFStreamProbe("/home/matze/Videos/recme/sample.3gp")
    #m=FFStreamProbe("/home/matze/Videos/handbrake.txt")
    #m=FFStreamProbe("/home/matze/Videos/CT.m2t")
    m=FFStreamProbe("/media/disk1/makemkv/title_t00.mkv")

    m.printCodecInfo()
    m.formatInfo._print()
    print ("getAspect2 ",m.getAspectRatio())
    
    container = m.formatInfo
    print ("-------- container: -------------")
    print ("formats:",container.formatNames())
    print ("bit-rate kb:",container.getBitRate())
    print ("duration:",container.getDuration())
    print ("size kb:",container.getSizeKB())
    print ("is TS:",m.isTransportStream())
    
    print ("-------- langMApping: -------------")
    langmap = m.getLanguageMapping()
    for key,index in langmap.items():
        print("lang:%s @ %d"%(key,index))
    
    
    print ("-------- all streams -------------"  )  
    for s in m.streams:
        print ("##########################")
        print ("Index:",s.getStreamIndex())
        print ("getCodec:",s.getCodec())
        print ("getLanguage:",s.getLanguage())
        print ("getCodecTimeBase: ",s.getCodecTimeBase())
        print ("getTimeBase: ",s.getTimeBase())
        print ("getAspect ",s.getAspectRatio())
        print ("getFrameRate: ",s.getFrameRate())
        print ("getDuration: ",s.duration())
        print ("getWidth: ",s.getWidth())
        print ("getHeight: ",s.getHeight())
        print ("isAudio: ",s.isAudio())
        print ("isVideo: ",s.isVideo())

def testPacketProbe(filename):    
    #p = FFPacketProbe(filename,0,None)
    FFPacketProbe(filename,"00:00:32.00",20)

def testFFmpegVersion():
    fv= FFmpegVersion()
    val=str(fv.version)[:1]
    print(">>"+val)

def testregex():
    #text = "46648 P:1866.05 D:1866.05 25.70%"
    text = "49 D:0.96 [00:00.00] 5.05%"
    #m= re.search("([0-9]+) D:([0-9.]+)([0-9:0-9.0-9]+) ([0-9.]+)%",text)
    #m= re.search("([0-9]+) D:([0-9.]+) (.+) ([0-9.]+)%",text)
    regexp = re.compile("([0-9]+) D:([0-9.]+) \[(.+)\] ([0-9.]+)%")
    m= regexp.search(text)
    print(m.group(0))
    frame = m.group(1)
    dts = m.group(3)
    progress = int(round(float(m.group(4)))) 
    print("F:%s dts: %s  per: %d"%(frame,dts,progress))

def stringToSeconds(string):
    items = string.split(":")
    hrs = items[0].split('=')[1]
    mins= items[1]
    sec = items[2].split('.')[0]
    return int(hrs)*3600+int(mins)*60+int(sec)


def testCMDffmpegRegex():
    #ext = "frame= 1637 fps=0.0 q=-1.0 Lsize=   28826kB time=00:01:05.70 bitrate=3593.8kbits/s speed= 144x"
    text = "frame= 1508 fps=0.0 q=-1.0 size=   26546kB time=00:01:00.52 bitrate=3593.0kbits/s speed= 121x"

    m = re.search('frame=[ ]*[0-9]+',text)
    print(m.group(0))
    m = re.search('time=[ ]*[0-9:.]+',text)
    print(m.group(0))
    x=stringToSeconds(m.group(0))
    print(x)
    items = m.group(0).split(":")
    hrs = str(items[0].split('=')[1])
    mins= str(items[1])
    sec = str(items[2].split('.')[0])
    total = int(hrs)*3600+int(mins)*60+int(sec)
    perc = (total/100.0)*100
    print("secs:%d %3.2f"%(total,perc))

import json
def createunidueISO692Map():
    #read the iso file
    HomeDir = os.path.dirname(__file__)
    DataDir=os.path.join(HomeDir,"data")
    path = os.path.join(DataDir,"unidueIso692.json")
    outpath = os.path.join(DataDir,"countryIso692.json")
    result=[]
    alphaToLang={}
    langToAlpha={}    
    result.append(alphaToLang)
    result.append(langToAlpha)
    with open(path,'r')as f:
        block1 = json.load(f) #Array 2
    
    map1 = block1[1]
    mapLang= map1["items"]
    for lang,langMap in mapLang.items():
        txt=langMap['en']
        full=txt.split('(')[0]
        code=langMap["iso3"].lower()
        print("lang %s = full: %s iso: %s"%(lang,full,code))
        alphaToLang[code]=full
        langToAlpha[full]=code
    
    with open(outpath,'w')as outfile:
        json.dump(result,outfile)

def convertIso639():
    #read the iso file
    HomeDir = os.path.dirname(__file__)
    DataDir=os.path.join(HomeDir,"data")
    path = os.path.join(DataDir,"iso639-2.json")
    outpath = os.path.join(DataDir,"countryIso639.json")
    result=[]
    alphaToLang={}
    langToAlpha={}    
    result.append(alphaToLang)
    result.append(langToAlpha)
    with open(path,'r')as f:
        block1 = json.load(f) #dict with 2/3 lettercodes
    
    for code,dict1 in block1.items():
        if len(code)==3:
            engName = dict1["int"][0]
            nativeName = dict1["native"][0]
            alphaToLang[code]=engName
            langToAlpha[engName]=code
        print("lang %s = eng: %s navtive: %s"%(code,engName,nativeName))

    with open(outpath,'w')as outfile:
        json.dump(result,outfile)    

#########################################################
    '''
    ffmpeg -h muxer=... the CONTAINER data (with default V/a codecs)
    == format_name in VideoFormatInfo (list) 
    3gp -> Common extensions: 3gp (h263, amr_nb)
    avi  ->Common extensions: avi. (mpeg4,mp3)
    matroska -> Common extensions: mkv,mk3d,mka,mks. (h264,vorbis)
    mp2  -> Common extensions: mp2,m2a,mpa.(audio only: mp2)
    mpegts -> Common extensions: ts,m2t,m2ts,mts. (mpeg2video, mp2)
    mpeg -> Common extensions: mpg,mpeg (mpeg1video, mp2) (not mp2 video...)
    mp4 = -> Common extensions: mp4,m4p,m4v (h264,aac)
    webm =   Common extensions: webm (vp9,opus)
    vob = Common extensions: vob (mpeg2video,mp2)
    dvd  Common extensions:dvd (mpeg2video,mp2)
    mpeg1video -> Common extensions: mpg,mpeg,m1v (mpeg1video -raw!)
    mpeg2video -> Common extensions: m2v (mpeg2video -raw!)
    mov -> Common extensions: mov,mp4,m4a,3gp,3g2,mj2    
    flv ->Common extensions:flv (flv1,mp3)
    ogg ->Common extensions:ogg (theora,vorbis)
    '''
    def _setupConversionTable(self):
        ##todo NEED FORMAT CONTAINER, NOT CODEC -c    
        self._convTable={} #codec vs extension? should be container!
        self._convTable["mpeg2video"]="mpg"
        self._convTable["mpeg1video"]="mpg"
        self._convTable["h264"]="mp4"
        self._convTable["hevc"]="mp4"
        self._convTable["msmpeg4v1"]="avi"
        self._convTable["msmpeg4v2"]="avi"
        self._convTable["msmpeg4v3"]="avi"
        self._convTable["rawvideo"]="swf"
        self._convTable["vp6f"]="flv"
        self._convTable["vc1"]="mkv" #only decode / remux can't handle the audio sync!
        self._convTable["vp8"]="webm"
        self._convTable["vp9"]="webm"
        self._convTable["mpeg4"]="mp4" #or mov,m4a,3gp,3g2,mj2 as EXTENSION..

        #self._convTable["ansi"]="txt"
        #TODO the conversion MUST be a combination of audio and video
        #e.g Opus can't be put into mp4 
        '''
        Container  Audio formats supported
        MKV/MKA    Vorbis, MP2, MP3, LC-AAC, HE-AAC, WMAv1, WMAv2, AC3, eAC3, Opus
        MP4/M4A    MP2, MP3, LC-AAC, HE-AAC, AC3
        FLV/F4V    MP3, LC-AAC, HE-AAC
        3GP/3G2    LC-AAC, HE-AAC
        MPG        MP2, MP3
        PS/TS Stream    MP2, MP3, LC-AAC, HE-AAC, AC3
        M2TS       AC3, eAC3
        VOB        MP2, AC3
        RMVB       Vorbis, HE-AAC
        WebM       Vorbis, Opus
        OGG        Vorbis, Opus 
        '''
    '''
    describes which audio codecs are alowwed in which container (ffmpeg-codecs)
    D..... = Decoding supported
    .E.... = Encoding supported
    ..V... = Video codec
    ..A... = Audio codec
    ..S... = Subtitle codec
    ...I.. = Intra frame-only codec
    ....L. = Lossy compression
    .....S = Lossless compression    
    DEA.L. aac    AAC (Advanced Audio Coding) (decoders: aac aac_fixed )
    D.A.L. mp1    MP1 (MPEG audio layer 1) (decoders: mp1 mp1float )    
    DEA.L. mp2    MP2 (MPEG audio layer 2) (decoders: mp2 mp2float ) (encoders: mp2 mp2fixed )
    DEA.L. mp3    MP3 (MPEG audio layer 3) (decoders: mp3float mp3 ) (encoders: libmp3lame )
    DEA.L. ac3    ATSC A/52A (AC-3) (decoders: ac3 ac3_fixed ) (encoders: ac3 ac3_fixed )
    DEA.L. vorbis Vorbis (decoders: vorbis libvorbis ) (encoders: vorbis libvorbis )
    DEAI.S flac   FLAC (Free Lossless Audio Codec)
    DEA.LS dts    DCA (DTS Coherent Acoustics) (decoders: dca ) (encoders: dca )
    DEAI.S alac   ALAC (Apple Lossless Audio Codec)    
    DEA.L. opus   Opus (Opus Interactive Audio Codec) (decoders: opus libopus ) (encoders: opus libopus )

    
    '''
    def audioCodecMapping(self):
        codecTable={} #format -> audio codec
        codecTable["3gp"]=["aac"]
        codecTable["avi"]=["mp1","mp2","mp3","aac","ac3"]
        codecTable["matroska"]=["mp1","mp2","mp3","aac","ac3","vorbis","opus","flac"]
        codecTable["mpegts"]=["mp1","mp2","mp3"]
        codecTable["mpeg"]=["mp1","mp2","mp3"]
        codecTable["vob"]=["mp2"]
        codecTable["dvd"]=["mp1","mp2","mp3"]
        codecTable["mp4"]=["mp1","mp2","mp3","aac","ac3","dts","opus","alac"]
        codecTable["mov"]=["mp1","mp2","mp3","aac","ac3","dts","opus","alac"]
        codecTable["webm"]=["opus","flac"]
        codecTable["flv"]=["mp3","aac"]
        codecTable["ogg"]=["opus","vorbis","flac"]
        return codecTable;
    
    '''
    (ffmpeg-formats are the MUXER/Container- NOT Codecs)
    E 3gp             3GP (3GPP file format)
    DE avi             AVI (Audio Video Interleaved)
    E matroska        Matroska
    D  matroska,webm   Matroska / WebM
    E webm            WebM
    E mp2             MP2 (MPEG audio layer 2)
    DE mp3             MP3 (MPEG audio layer 3)
    E dvd             MPEG-2 PS (DVD VOB)
    DE m4v             raw MPEG-4 video
    E mp2             MP2 (MPEG audio layer 2)
    DE mp3             MP3 (MPEG audio layer 3)
    E mp4             MP4 (MPEG-4 Part 14)
    DE mpeg            MPEG-1 Systems / MPEG program stream
    E mpeg1video      raw MPEG-1 video
    E mpeg2video      raw MPEG-2 video
    DE mpegts          MPEG-TS (MPEG-2 Transport Stream)
    D  mpegvideo       raw MPEG video
    E vob             MPEG-2 PS (VOB)
    D  mov,mp4,m4a,3gp,3g2,mj2 QuickTime / MOV

    Lists the video codecs for each container ->wikipeadia...
    '''
    def videoCodecMapping(self):   
        codecTable={} #format -> video codec
        codecTable["3gp"]=["mp4","h263","vc1"]
        codecTable["avi"]=["mpeg1video","mpeg2video","wmv?","vc1","theora","mp4","h264","h265","vp8","vp9"]
        codecTable["matroska"]=["mpeg1video","mpeg2video","wmv?","vc1","theora","mp4","h264","h265","vp8","vp9"]
        codecTable["mpegts"]=["mpeg1video","mpeg2video","mp4","h264"]
        codecTable["mpeg"]=["mpeg1video","mpeg2video","mp4","h264"]
        codecTable["vob"]=["mpeg1video","mpeg2video"]
        codecTable["dvd"]=["mpeg1video","mpeg2video"]
        codecTable["mp4"]=["mpeg1video","mpeg2video","wmv?","vc1","theora","mp4","h264","h265","vp8","vp9"]
        codecTable["mov"]=["mpeg1video","mpeg2video","wmv?","vc1","theora","mp4","h264","h265","vp8","vp9"]
        codecTable["webm"]=["vp8","vp9"]
        codecTable["flv"]=["mp4","h264","vp6"]
        codecTable["ogg"]=["theora"] 
        return codecTable;
    

#########################################################
def testFormatMapping():
    gen = FormatMapGenerator()
    fmtmp4= gen.table["mp4"];
    print(fmtmp4.audioCodecs)
    print(fmtmp4.videoCodecs)
    print(fmtmp4.extensions)
    print("Test codecs mp3 and h264 %s"%fmtmp4.containsCodecs("h264","mp3"))
    print("Test codecs vorbis and h264 %s"%fmtmp4.containsCodecs("h264","vorbis"))
    ext= gen.extensionsFor("h264","aac")
    print("Extension for:(h264,aac)%s"%ext)
    
    dlg = gen.getDialogFileExtensionsFor("h264","aac")
    print("DLG Extension for:(h264,aac)%s"%dlg)
    
        
if __name__ == '__main__':
    #testCMDffmpegRegex()
    #testregex()
    #testFFmpegVersion()
    #testPath()
    #testParse()
    #testNonblockingRead()
    #testFrameProbe()
    #testPacketProbe("/home/matze/Videos/pur/purX.m2t")
    #createIso692Map()
    #convertIso639()
    testFormatMapping()
    ''' 
        #Very slow!!!
        f = FFFrameProbe("xxx")
        print len(f.frames)
    '''
        
'''
Search for audio sync
-video_track_timescale
? ffmpeg -i segment1.mov -af apad -c:v copy <audio encoding params> -shortest -avoid_negative_ts make_zero -fflags +genpts padded1.mov
? ffmpeg -y -ss 00:00:02.750 -i input.MOV -c copy -t 00:00:05.880 -avoid_negative_ts make_zero -fflags +genpts segment.MOV
-async?
-apad: reencoding - very slow! do not use
-mpegts_copyts 1 : test for cutting. 
Example
we have two cuts. First cut checked with 
ffprobe -show_entries format=start_time:stream=start_time -of compact /tmp/vc_0.m2t
program|stream|start_time=4.857222
stream|start_time=1.422111

stream|start_time=4.857222
stream|start_time=1.422111
format|start_time=1.422111

means: 3 seconds audio before video starts.
proove: -shortest needs to be in the CUT, not the join.
joined file has exactly 3.4 seconds video delay 
'''             
#----------- documatation -------------

'''
>> Header info very fast
ffprobe -select_streams v:0 -show_streams Videos/007Test.mp4 -v quiet
[STREAM]
index=0
codec_name=h264
codec_long_name=H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10
profile=High
codec_type=video
codec_time_base=1/100
codec_tag_string=avc1
codec_tag=0x31637661
width=1280
height=720
has_b_frames=0
sample_aspect_ratio=1:1
display_aspect_ratio=16:9
pix_fmt=yuv420p
level=40
color_range=tv
color_space=bt709
timecode=N/A
id=N/A
r_frame_rate=50/1
avg_frame_rate=50/1
time_base=1/90000
start_pts=44730
start_time=0.497000
duration_ts=27415800
duration=304.620000
bit_rate=7576497
max_bit_rate=N/A
bits_per_raw_sample=8
nb_frames=15231
nb_read_frames=N/A
nb_read_packets=N/A
DISPOSITION:default=1
DISPOSITION:dub=0
DISPOSITION:original=0
DISPOSITION:comment=0
DISPOSITION:lyrics=0
DISPOSITION:karaoke=0
DISPOSITION:forced=0
DISPOSITION:hearing_impaired=0
DISPOSITION:visual_impaired=0
DISPOSITION:clean_effects=0
DISPOSITION:attached_pic=0
TAG:language=und
TAG:handler_name=VideoHandler
[/STREAM]

add -count_Frames (takes very long!) and you get:
nb_frames=15231
nb_read_frames=15228

#line by line thru pipe: makes progress posible
p = subprocess.Popen(["ls"], stdout=subprocess.PIPE)
while True:
    line = p.stdout.readline()
    if not line:
        break
    print line

'''
    

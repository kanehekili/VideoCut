'''
Created on Nov 26, 2016

@author: matze
'''
from FFMPEGTools import FFStreamProbe,FFPacketProbe,OSTools
import os
import subprocess
from subprocess import Popen
from datetime import timedelta
import re
import fcntl
from time import sleep

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
                           

def non_block_read(prefix,output):
    fd = output.fileno()
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    text = "."
    try:
        text = output.read()
        if text is None:
            print("-")
            return
        else:
            print(text)
        m = re.search('frame=[ ]*[0-9]+',text)
        p1 = m.group(0)
        m = re.search('time=[ ]*[0-9:.]+',text)
        p2 = m.group(0)
        self.say(prefix+" "+p1+" - "+p2)
        log(prefix,'frame %s time %s'%(p1,p2))
    except:
        if len(text)>5:
            print ("<"+text)   
    if "failed" in text:
        #TODO needs to be logged
        print ("?????"+text)
        self.say(prefix+" !Conversion failed!")
        return False
    else:
        return True 
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
    m=FFStreamProbe("/home/matze/Videos/pur/purX.m2t")

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
    
    print ("-------- all streams -------------"  )  
    for s in m.streams:
        print ("Index:",s.getStreamIndex())
        print ("getCodec:",s.getCodec())
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

if __name__ == '__main__':
    testPath()
    #testParse()
    #testNonblockingRead()
    #testFrameProbe()
    #testPacketProbe("/home/matze/Videos/pur/purX.m2t")

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
    

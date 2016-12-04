'''
Created on Nov 26, 2016

@author: matze
'''
from FFMPEGTools import FFStreamProbe


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

# class MarkerListEntry(QWidget):
#     def __init__(self,frame,ratio,videoCutEntry=None):
#         QWidget.__init__(self,None)
#         self._entry=videoCutEntry
#         self._ratio=ratio
#         self._createUI(frame,videoCutEntry)
#     
#     def _createUI(self,frame,entry):
#         self._modeLabel = QLabel(entry.modeString)
#         self.modeLabel.setStyleSheet('''QLabel { background-color : red; color : blue; }''')
#         self._timeLabel = QLabel(entry.getTimeString())
#         self._frameLabel = QLabel(str(entry.frameNumber))
#         self._ico = MarkerIcon(frame,self._ratio*SIZE_ICON,SIZE_ICON)
#         vbox = QVBoxLayout()
#         vbox.addWidget(self._modeLabel)
#         vbox.addWidget(self._timeLabel)
#         vbox.addWidget(self._frameLabel)
#         vbox.setSpacing(0)
#         vbox.setContentsMargins(0,0,0,0)
# #        self.setLayout(vbox)
#          
#         hbox = QHBoxLayout()
#         hbox.setContentsMargins(0,0,0,0)
#         hbox.addWidget(self._ico)
#         hbox.addLayout(vbox)
#         self.setLayout(hbox)
#         self.adjustSize()
#         
#         
# #     def paintEvent(self, event):
# #         print" Marker paint"
# #         QWidget.paintEvent(self,event)
#         
#         
#         
# class MarkerIcon(QWidget):
#     def __init__(self,frame,width,height):
#         QWidget.__init__(self,None)
#         self._image = CVImage(frame)
#         self.ico_dim = QRect(0, 0,width,height)
#         #self.setGeometry(0,0,width,height)
# 
#     def paintEvent(self, event):
#         print "Marker icon paint"
#         painter = QPainter(self)
#         painter.drawImage(self.ico_dim, self._image)
# 
#     def sizeHint(self):
#         print "Marker:",QSize(self.ico_dim.width(),self.ico_dim.height())
#         return QSize(self.ico_dim.width(),self.ico_dim.height())



if __name__ == '__main__':
    #m=FFStreamProbe("/home/matze/Videos/Handy-M4-Test/MOV_0296.MP4")
    #m=FFStreamProbe("/media/matze/Datastore/Videos/VCR/KiKA/11_13_19_25-pur+.m2t")
    #m=FFStreamProbe("/media/matze/Datastore/Videos/VCR/3sat_HD/11_24_07_00-nano.m2t")
    m=FFStreamProbe("/media/matze/Datastore/Videos/6.Folge Craftattack.mp4")
    #m=FFStreamProbe("/home/matze/Videos/20051210-w50s.flv")
    #m=FFStreamProbe("/home/matze/Videos/recme/sample.3gp")
    #m=FFStreamProbe("/home/matze/Videos/handbrake.txt")
    #m=FFStreamProbe("/home/matze/Videos/CT.m2t")
    #m=FFStreamProbe("/home/matze/Videos/big_buck_bunny_1080p_h264.mov")

    m.printCodecInfo()
    m.formatInfo._print()
    print "getAspect2 ",m.getAspectRatio()
    
    container = m.formatInfo
    print "-------- container: -------------"
    print "formats:",container.formatNames()
    print "bit-rate kb:",container.getBitRate()
    print "duration:",container.getDuration()
    print "size kb:",container.getSizeKB()
    print "is TS:",m.isTransportStream()
    
    print "-------- all streams -------------"    
    for s in m.streams:
        print "Index:",s.getStreamIndex()
        print "getCodec:",s.getCodec()
        print "getCodecTimeBase: ",s.getCodecTimeBase()
        print "getTimeBase: ",s.getTimeBase()
        print "getAspect ",s.getAspectRatio()
        print "getFrameRate: ",s.getFrameRate()
        print "getDuration: ",s.duration()
        print "getWidth: ",s.getWidth()
        print "getHeight: ",s.getHeight()
        print "isAudio: ",s.isAudio()
        print "isVideo: ",s.isVideo()



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
    

'''
Created on Oct 4, 2014
FFMPEG Wrapper - AVCONV will not be supported - ever.
@author: kanehekili
'''

import os,sys
import subprocess
from subprocess import Popen
import re
from shutil import which
import logging
from logging.handlers import RotatingFileHandler
from itertools import tee
import configparser
import gzip

BIN = "ffmpeg"


def setupRotatingLogger(logName,logConsole):
    logSize=5*1024*1024 #5MB
    if logConsole: #aka debug/development
        folder = OSTools().getActiveDirectory()    
    else:
        folder= OSTools().joinPathes(OSTools().getHomeDirectory(),".config",logName)
        OSTools().ensureDirectory(folder)
    logPath = OSTools().joinPathes(folder,logName+".log") 
    fh= RotatingFileHandler(logPath,maxBytes=logSize,backupCount=5)
    fh.rotator=OSTools().compressor
    fh.namer=OSTools().namer
    logHandlers=[]
    logHandlers.append(fh)
    if logConsole:
        logHandlers.append(logging.StreamHandler(sys.stdout))    
    logging.basicConfig(
        handlers=logHandlers,
        #level=logging.INFO
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s : %(message)s'
    )
    #console - only if needed
    '''
    if logConsole:
        cons = logging.StreamHandler(sys.stdout)
        logger.addHandler(cons)    
    '''
def setLogLevel(levelString):
    if levelString == "Debug":
        Log.setLevel(logging.DEBUG)
    elif levelString == "Info":
        Log.setLevel(logging.INFO)
    elif levelString == "Warning":
        Log.setLevel(logging.WARNING)
    elif levelString == "Error":
        Log.setLevel(logging.ERROR)

        
class OSTools():
    __instance=None

    QT_DESKTOPS = ["kde","plasma","lxqtt","trinity desktop","lumina","lomiri","cutefish","ukui","thedesk","razor","deepin","dde"]

    def __new__(cls):
        if OSTools.__instance is None:
            OSTools.__instance=object.__new__(cls)
        return OSTools.__instance
    
    def touch(self,fname, times=None):
        with open(fname, 'a'):
            os.utime(fname, times)
    
    def getPathWithoutExtension(self, aPath):
        if aPath:
            # rawPath = os.path.splitext(str(aPath))[0]
            rawPath = os.path.splitext(aPath)[0]
        else:
            rawPath = ""
        return rawPath

    def getExtension(self,path,withDot=True):
        comp = os.path.splitext(path)
        if len(comp)>1: 
            if withDot:
                return comp[1]
            else:
                return comp[1][1:]
        return comp[0]

    def getDirectory(self,aPath):
        return os.path.dirname(aPath)

    #that is the directory where this file resides - not the main
    #should be used carefully (OK if FFMPEGTools in the same path as main)
    def getWorkingDirectory(self):
        #os.path.dirname(os.path.realpath(__file__)) > if symlinks a necessary
        return os.path.dirname(os.path.abspath(__file__))               

    def setMainWorkDir(self,dirpath):
        os.chdir(dirpath)  #changes the "active directory"  
         
    #location of "cwd", i.e where is bash..
    def getActiveDirectory(self):
        return os.getcwd()
    
    '''
    __file__ is the pathname of the file from which the module was loaded
    This is the only way to ensure the correct working dir, as this module may be 
    located not in the same path as the main module.
    Therefore fileInstance is expected to be __file__ (but not compulsary)
    ! Fix: If called by link, abspath(__file__) is the cwd of the link ... 
    '''
    def getLocalPath(self,fileInstance):
        return os.path.dirname(os.path.realpath(fileInstance))
    
    #check if filename only or the complete path
    def isAbsolute(self,path):
        return os.path.isabs(path)

    #The users home directory - not where the code lies
    def getHomeDirectory(self):
        return os.path.expanduser("~")

    def getFileNameOnly(self, path):
        return os.path.basename(path)
    
    def fileExists(self, path):
        return os.path.isfile(path)
    
    def removeFile(self, path):
        if self.fileExists(path):
            os.remove(path)

    def canWriteToFolder(self,path):
        return os.access(path,os.W_OK)

    def canReadFromFolder(self,path):
        return os.access(path,os.R_OK)

    def ensureDirectory(self, path, tail=None):
        # make sure the target dir is present
        if tail is not None:
            path = os.path.join(path, tail)
        if not os.access(path, os.F_OK):
            try:
                os.makedirs(path)
                os.chmod(path, 0o777) 
            except OSError as osError:
                logging.log(logging.ERROR, "target not created:" + path)
                logging.log(logging.ERROR, "Error: " + str(osError.strerror))
    
    def ensureFile(self, path, tail):
        fn = os.path.join(path, tail)
        self.ensureDirectory(path, None)
        with open(fn, 'a'):
            os.utime(fn, None)
        return fn

    def joinPathes(self,*pathes):
        res=pathes[0]
        for head,tail in self.__pairwise(pathes):
        #for a, b in tee(pathes):
            res = os.path.join(res, tail)
        return res

    def __pairwise(self,iterable):
        a, b = tee(iterable)
        next(b, None)
        return list(zip(a, b))

    def isRoot(self):
        return os.geteuid()==0

    def countFiles(self,aPath,searchString):
        log_dir=os.path.dirname(aPath)
        cnt=0
        for f in os.listdir(log_dir):
            if searchString is None or searchString in f:
                cnt+=1
        return cnt

    #logging rotation & compression
    def compressor(self,source, dest):
        with open(source,'rb') as srcFile:
            data=srcFile.read()
            bindata = bytearray(data)
            with gzip.open(dest,'wb') as gz:
                gz.write(bindata)
        os.remove(source)
    
    def namer(self,name):
        return name+".gz"

    def is_nvidia_gpu_active(self):
        try:
            # Try to detect active GPU via `nvidia-smi` (most reliable if installed)
            subprocess.run(["nvidia-smi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return True
        except Exception:
            pass
    
        try:
            # Fallback: parse `lspci` output (less accurate but doesn't need NVIDIA tools)
            result = subprocess.run(["lspci"], stdout=subprocess.PIPE, text=True)
            return "NVIDIA" in result.stdout
        except Exception:
            return False

    def currentDesktop(self):
        return os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

    def setGTKEnvironment(self):
        os.environ["QT_QPA_PLATFORMTHEME"] = "gtk3"
        os.environ['QT_QPA_PLATFORM'] = 'xcb'

class ConfigAccessor():
    __SECTION = "default" 
    homeDir = OSTools().getHomeDirectory()

    def __init__(self, folder,filePath,section="default"):
        self.__SECTION=section
        self._path = OSTools().joinPathes(self.homeDir,".config",folder,filePath)
        self.parser = configparser.ConfigParser()
        self.parser.add_section(self.__SECTION)
        
    def read(self):
        self.parser.read(self._path)
        
    def set(self, key, value):
        self.parser.set(self.__SECTION, key, value)

    def get(self, key,default=None):
        if self.parser.has_option(self.__SECTION, key):
            return self.parser.get(self.__SECTION, key)
        return default

    def getBoolean(self, key,default=None):
        if self.parser.has_option(self.__SECTION, key):
            return self.parser.getboolean(self.__SECTION, key)
        return default

    def getInt(self, key,default=None):
        if self.parser.has_option(self.__SECTION, key):
            return self.parser.getint(self.__SECTION, key)
        return default

    def getFloat(self, key,default=None):
        if self.parser.has_option(self.__SECTION, key):
            return self.parser.getfloat(self.__SECTION, key)
        return default

        
    def store(self):
        try:
            with open(self._path, 'w') as aFile:
                self.parser.write(aFile)
        except IOError:
            return False
        return True     



Log=logging.getLogger("Main")

def parseCVInfos(cvtext):
    lines = cvtext.splitlines(False)
    cvDict = {}
    for line in lines:
        match = re.search(r"(?<=OpenCV)\s*(\d\S*[a-z]*)+", line)
        if match: 
            cvDict["OpenCV"] = match.group(1)
            continue
            
        match = re.search(r'(?<=Baseline:)\s*([ \w]+)+', line)
        if match:
            cvDict["BaseLine"] = match.group(1) 
            continue
        match = re.search(r"(?<=GTK\+:)\s*(\w+[(\w+ ]*[\d.]+[)]*)+", line)
        if match: 
            cvDict["GTK+"] = match.group(1)
            continue
        match = re.search(r"(?<=FFMPEG:)\s*(\w+)", line)
        if match:
            cvDict["FFMPEG"] = match.group(1) 
            continue
        match = re.search(r"(?<=avcodec:)\s*(\w+[(\w+ ]*[\d.]+[)]*)+", line)
        if match:
            cvDict["AVCODEC"] = match.group(1) 
            continue
    return cvDict


   
    # execs an command, yielding the lines to caller. Throws exception on error
def executeAsync(cmd, commander):
    popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    commander.setProcess(popen)
    for stdout_line in iter(popen.stdout.readline, ""):
        yield stdout_line 
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd)


def executeCmd(cmd):
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()    

   
'''
Probes packets.
if count = -1 no partial seeking takes place
time to seek to
count: number of packets to read 
currently only pts,dts,dts_time&flags are read
Available:
[PACKET]
codec_type=video
stream_index=0
pts=1868670
pts_time=20.763000
dts=1866870
dts_time=20.743000
duration=1800
duration_time=0.020000
convergence_duration=N/A
convergence_duration_time=N/A
size=2397
pos=19111259
flags=__
[/PACKET]
'''


class FFPacketProbe():

    def __init__(self, video_file, seekTo, count=None):
        self.path = video_file
        self.packetList = []
        self._readData(seekTo, count)

    def _readData(self, seekTo, count):
        cmd = ["ffprobe", "-hide_banner"]
        if count is not None:
            cmd = cmd + ["-read_intervals", seekTo + "%+#" + str(count)]
        cmd.extend(("-show_packets", "-select_streams", "v:0", "-show_entries", "packet=pts,pts_time,dts,dts_time,flags", "-of", "csv" , self.path, "-v", "quiet"))
        Log.debug("FFPacket:%s", cmd)    
        result = Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        if len(result[0]) == 0:
            raise IOError('No such media file ' + self.path)
        lines = result[0].decode("utf-8").split('\n')
        for index, text in enumerate(lines):
            if len(text) > 0:
                raw = text.split(',')
                pack = PacketInfo(index)
                pack.pts = raw[1];
                pack.pts_time = raw[2]
                pack.dts = raw[3];
                pack.dts_time = raw[4]
                pack.isKeyFrame = ('K' in raw[5])
                self.packetList.append(pack)
        
        self.printP()
        
    def printP(self):
        for pack in self.packetList:
            print (">>", pack.asString())   


class PacketInfo():

    def __init__(self, index):
        self.pts = 0
        self.dts = 0
        self.pts_time = 0
        self.dts_time = 0
        self.index = index
        self.isKeyFrame = 0
    
    def asString(self):
        return str(self.index) + ") P:" + self.pts + " D:" + self.dts + " pt:" + self.pts_time + " dt:" + self.dts_time + " k:" + str(self.isKeyFrame)

    
class FormatMap():
    def __init__(self, fmt, vcList, acList, extensions,targetExt,fmtlib):
        self.format = fmt
        self.videoCodecs = vcList
        self.audioCodecs = acList;
        self.extensions = extensions
        self.targetExt=targetExt
        self.formatLib = fmtlib

    '''
    @return if vCodec and aCodec are contained in this format
    '''

    def containsCodecs(self, vCodec, aCodec):
        if aCodec is None:
            return vCodec in self.videoCodecs;
        
        return vCodec in self.videoCodecs and aCodec in self.audioCodecs
    
    def hasExtension(self,fileExt):
        return fileExt in self.extensions
    
    def defaultVideoCodec(self):
        return self.videoCodecs[0]
    
    #Those formats are used for c:v xxx or -f options
    def defaultFormats(self):
        return self.formatLib
    
    def videoFormat(self):
        return self.formatLib[0]    

    def audioFormat(self):
        return self.formatLib[1]
    
    def subtitleFormat(self):
        return self.formatLib[2]


class FormatMapGenerator():
    '''
    Image-based sub-title codecs in ffmpeg
        dvbsub ok
        dvdsub ok
        pgssub -not an encode
        xsub   -not an encoder
    
    Text-based subtitle codecs in ffmpeg
        ssa,ass  ok
        webvtt   ok
        jacosub  no
        microdvd no
        mov_text ok
        mpl2     no
        pjs      no
        realtext no
        sami     no 
        stl      no
        subrip   ok
        subviewer no
        subviewer1 no
        text      ok 
        vplayer   ?
        webvtt    ok     
    '''    
    SUB_IMG=["dvbsub","pgssub*","hdmv_pgs_subtitle*","xsub*"]
    SUB_TEXT=["ssa","ass","webvtt","mov_text","subrip","srt","text","webvtt"]
    
    #supported muxers
    muxers = ["mpegts","mpeg", "vob", "dvd", "mp4", "mov", "matroska", "webm", "3gp", "avi", "flv", "ogg"]
    videoCodecs = {}
    audioCodecs = {}
    extensions = {}
    targetExt ={}
    formats={} #the -f switch ..

    videoCodecs["mpegts"] = ["mpeg2video","mpeg1video" ]#critical!
    videoCodecs["mpeg"] = ["mpeg2video","mpeg1video"]
    videoCodecs["vob"] = ["mpeg2video","mpeg1video"]
    videoCodecs["dvd"] = ["mpeg2video","mpeg1video"]
    videoCodecs["mp4"] = ["mp4","mpeg1video", "mpeg2video", "wmv?", "vc1", "theora", "h264", "h265", "vp8", "vp9"]
    videoCodecs["mov"] = ["h264","mpeg1video", "mpeg2video", "wmv?", "vc1", "theora", "mp4", "h265", "vp8", "vp9"]
    videoCodecs["matroska"] = ["h264","mpeg1video", "mpeg2video", "wmv?", "vc1", "theora", "mp4", "h265", "vp8", "vp9", "av1"]
    videoCodecs["webm"] = ["vp8", "vp9"]
    videoCodecs["3gp"] = ["mp4", "h263", "vc1"]
    videoCodecs["avi"] = ["h264","mpeg1video", "mpeg2video", "wmv?", "vc1", "theora", "mp4", "h265", "vp8", "vp9"]
    videoCodecs["flv"] = ["h264","mp4", "vp6"]
    videoCodecs["ogg"] = ["theora"] 
    
    audioCodecs["mpegts"] = ["mp1", "mp2", "mp3"]
    audioCodecs["mpeg"] = ["mp1", "mp2", "mp3"]
    audioCodecs["vob"] = ["mp2"]
    audioCodecs["dvd"] = ["mp1", "mp2", "mp3"]
    # opus in MP4 support is experimental, add '-strict -2' if you want to use it.
    audioCodecs["mp4"] = ["mp1", "mp2", "mp3", "aac", "ac3", "dts", "alac", "vorbis"]
    audioCodecs["mov"] = ["mp1", "mp2", "mp3", "aac", "ac3", "dts", "alac", "vorbis"]
    audioCodecs["matroska"] = ["mp1", "mp2", "mp3", "aac", "ac3", "vorbis", "opus", "flac"]
    audioCodecs["webm"] = ["opus", "vorbis"]
    audioCodecs["3gp"] = ["aac"]
    audioCodecs["avi"] = ["mp1", "mp2", "mp3", "aac", "ac3"]
    audioCodecs["flv"] = ["mp3", "aac"]
    audioCodecs["ogg"] = ["vorbis", "opus", "flac"]

    # the ffmpeg view of extensions
    extensions["mpegts"] = ["m2t", "ts", "m2ts", "mts"]
    extensions["mpeg"] = ["mpg", "mpeg"]
    extensions["vob"] = ["vob"]
    extensions["dvd"] = ["dvd"]
    extensions["mp4"] = ["mp4", "m4p", "m4v"]
    extensions["mov"] = ["mov", "mp4", "m4a", "3gp", "3g2", "mj2"]
    extensions["matroska"] = ["mkv", "mk3d", "mka", "mks"]
    extensions["webm"] = ["webm"]
    extensions["3gp"] = ["3gp"]
    extensions["avi"] = ["avi"]
    extensions["flv"] = ["flv"]
    extensions["ogg"] = ["ogg"]    

    targetExt["mpegts"] = "mpg"
    targetExt["mpeg"] = "mpg"
    targetExt["vob"] = "mpg"
    targetExt["dvd"] = "mpg"
    targetExt["mp4"] = "mp4"
    targetExt["mov"] = "mp4"
    targetExt["matroska"] = "mkv"
    targetExt["webm"] = "webm"
    targetExt["3gp"] = "3gp"
    targetExt["avi"] = "avi"
    targetExt["flv"] = "flv"
    targetExt["ogg"] = "ogg"    

    #formats name for encoding and codec ->ffmpeg -h muxer=matroska and -encoders
    #video, audio,subtitle
    formats["mpegts"] = ["mpegts","mp2",None]
    formats["mpeg"] = ["mpeg2video","mp2",None]
    formats["vob"] = ["mpeg2video","mp2","dvdsub"]
    formats["dvd"] = ["mpeg2video","mp2","dvdsub"]
    formats["mp4"] = ["libx264","aac","mov_text"]
    formats["mov"] = ["libx264","aac","mov_text"]
    formats["matroska"] = ["libx264","libvorbis","srt"] 
    formats["webm"] = ["libvpx-vp9","libvorbis","webvtt"]
    formats["3gp"] = ["h263_v4l2m2m","libopencore_amrnb",None]
    formats["avi"] = ["libx264","libmp3lame",None]
    formats["flv"] = ["flv","libmp3lame",None]
    formats["ogg"] = ["libtheora","libvorbis",None] 
    
    
    def __init__(self):
        self.setup()
    
    def setup(self):
        self.table = {}
        for fi in self.muxers:
            fmt = FormatMap(fi, self.videoCodecs[fi], self.audioCodecs[fi], self.extensions[fi],self.targetExt[fi],self.formats[fi])
            self.table[fi] = fmt

    #need to reflect our internal changes, such as m2t to mpg or mp4
    def getPreferredTargetExtension(self,vCodec,aCodec,currFormats):
        
        #mpegts: depends if h264 or mp2.... 
        fmap = self._findFmtTargetMap(vCodec, aCodec)
              
        for vInfo in currFormats:
            if vInfo=="mpegts":
                continue
            res = self.targetExt.get(vInfo,None)
            if res and self._verifyAudio(vInfo,aCodec):
                    return res;
                
        #IF not found ...
        if fmap:
            return fmap.targetExt
        
        #fallback
        extList = self.extensions.get(currFormats[0],"matroska") #mkv should never be wrong
        return extList[0] 

                

    def getDialogFileExtensionsFor(self, vCodec, aCodec,currFormats):
        extList = set() #Set
        for vInfo in currFormats:
            if vInfo=="mpegts":
                extList.add("*." +self.extensions[vInfo][0])
                continue

            ext = self.targetExt.get(vInfo,None)
            if ext:
                extList.add("*." +ext)
        fmap = self._findFmtTargetMap(vCodec, aCodec)
        if fmap:
            extList.add("*." + fmap.targetExt)
            for ext in fmap.extensions:
                wc = "*." + ext
                #if not wc in extList:
                extList.add(wc)  
        return " ".join(extList)
    
    #This is target map only!  
    def _findFmtTargetMap(self,vCodec, aCodec):
        for fi, fmtMap in self.table.items():
            #if fi=="mpegts":
            #    continue
            if fmtMap.containsCodecs(vCodec, aCodec):
                return fmtMap
        return None

    #redunant audio check
    def _verifyAudio(self,foundVCodec, aCodec):
        codecs = self.audioCodecs.get(foundVCodec,None)
        if not codecs:
            return False
        return aCodec in codecs

    def fromFormatList(self,fmtList):
        formats=[]
        for item in fmtList:
            fmt= self.table.get(item,None)
            if fmt:
                formats.append(fmt)
        return formats
    
    #takes the extension and get the most likely format.
    def fromFilename(self,path):
        ext = OSTools().getExtension(path,withDot=False)
        for fi, fmtMap in self.table.items():
            if ext in fmtMap.extensions:
                return fmtMap
        
        return None

    def sameSubGroup(self,codec1,codec2):
        return codec1 in self.SUB_TEXT and codec2 in self.SUB_TEXT or codec1 in self.SUB_IMG and codec2 in self.SUB_IMG         

FORMATS = FormatMapGenerator()

        
class FFStreamProbe():

    def __init__(self, video_file):
        # self._setupConversionTable()
        self.path = video_file
        self._readData()
         
    def _readData(self):
        result = Popen(["ffprobe", "-show_format", "-show_streams", self.path, "-v", "quiet"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        if len(result[0]) == 0:
            raise IOError('Not a media file ' + self.path)
        self.streams = []
        datalines = []
        self.video = []
        self.audio = []
        self.subtitle=[]
        self.formatInfo = None

        lines = result[0].decode("utf-8").split('\n')
        for a in lines:
            if re.match(r'\[STREAM\]', a):
                datalines = []
            elif re.match(r'\[\/STREAM\]', a):
                self.streams.append(VideoStreamInfo(datalines))
                datalines = []

            elif re.match(r'\[FORMAT\]', a):
                datalines = []
            elif re.match(r'\[\/FORMAT\]', a):
                self.formatInfo = VideoFormatInfo(datalines)
                datalines = []
            else:
                datalines.append(a)
        for a in self.streams:
            if a.isAudio():
                self.audio.append(a)
                a.slot=len(self.audio)
            elif a.isVideo():
                self.video.append(a)
                a.slot=len(self.video)
            elif a.isSubTitle():
                self.subtitle.append(a)
                a.slot=len(self.subtitle)
        self.sanityCheck()

    def sanityCheck(self):
        if logging.root.level!=logging.DEBUG:
            return
        
        Log.debug("-------- Video -------------")
        s = self.getVideoStream()
        if s:
            Log.debug("Index: %d", s.getStreamIndex())
            Log.debug("Slot: %d", s.slot)
            Log.debug("codec %s", s.getCodec())
            Log.debug("getCodecTimeBase: %s", s.getCodecTimeBase())
            Log.debug("getTimeBase: %s", s.getTimeBase())
            Log.debug("getAspect %s", s.getAspectRatio())
            Log.debug("getFrameRate_r: %.3f", s.frameRateMultiple())
            Log.debug("getAVGFrameRate: %3.f", s.frameRateAvg())  # Common denominator
            Log.debug("getDuration: %.3f", s.duration())
            Log.debug("getWidth: %s", s.getWidth())
            Log.debug("getHeight: %s", s.getHeight())
            Log.debug("isAudio: %r", s.isAudio())
            Log.debug("isVideo: %r", s.isVideo())
        
        Log.debug("-------- Audio -------------")
        s = self.getAudioStream()
        if s:  
            Log.debug("Index:%d", s.getStreamIndex())
            Log.debug("Slot: %d", s.slot)
            Log.debug("getCodec:%s", s.getCodec())
            Log.debug("bitrate(kb) %d", s.getBitRate())
            Log.debug("getCodecTimeBase: %s", s.getCodecTimeBase())
            Log.debug("getTimeBase: %s", s.getTimeBase())
            Log.debug("getDuration: %.3f", s.duration())
            Log.debug("isAudio: %r", s.isAudio())
            Log.debug("isVideo: %r", s.isVideo())
            Log.debug("-----------Formats-----------")

        f=self.formatInfo
        Log.debug("Fmt Names:%s",f.formatNames())
        Log.debug("Fmt bitrate;%d",f.getBitRate())
        Log.debug("Fmt dur: %.3f",f.getDuration())
        Log.debug("Fmt size %.3f",f.getSizeKB())
        Log.debug("-----------EOF---------------")
             
    def getVideoStream(self):
        if len(self.video) == 0:
            return None
        return self.video[0]
    
    def getAudioStream(self):
        for stream in self.audio:
            # if stream.getBitRate()>0:
            if stream.isValidAudio():
                return stream     
        return None
    
    def getPrimaryAudioCodec(self):
        for stream in self.audio:
            # if stream.getBitRate()>0:
            if stream.getCodec() != VideoStreamInfo.NA:
                return stream.getCodec()
        
        return None;
    
    def allAudioStreams(self):
        return self.audio
    
    def getDialogFileExtensions(self):
        vcodec = self.getVideoStream().getCodec()
        acodec = self.getPrimaryAudioCodec()
        return FORMATS.getDialogFileExtensionsFor(vcodec, acodec,self.getFormatNames())

    #single extension
    def getSourceExtension(self):
        fmt = self.getFormatNames()[0]
        fmtMap = FORMATS.table[fmt];
        return fmtMap.extensions[0]
    
    #Single extension.
    def getTargetExtension(self):
        if not self.getVideoStream():
            return None
        vcodec = self.getVideoStream().getCodec()
        acodec = self.getPrimaryAudioCodec()
        return FORMATS.getPreferredTargetExtension(vcodec, acodec,self.getFormatNames())
        
    
    def getAspectRatio(self):
        if not self.getVideoStream():
            return 1.0
        ratio = self.getVideoStream().getAspectRatio()
        if ratio == 1.0 and int(self.getVideoStream().getHeight())>0:
            ratio = float(self.getVideoStream().getWidth()) / float(self.getVideoStream().getHeight())
        return ratio

    '''
    This filter is required for copying an AAC stream from 
    a raw ADTS AAC or an MPEG-TS container to MP4A-LATM.
    '''
    def needsAudioADTSFilter(self):
        if self.getAudioStream() is None:
            return False
        return self.getAudioStream().getCodec() == "aac" and (self.isH264Codec() or self.isMP4Container())
    
    '''
    check if needs the h264_mp4toannexb filter-
     Use on: MP4 file(container) containing an H.264 stream to mpegts format
    '''
    def needsH264Filter(self):
        if self.isTransportStream():
            return False;
        return self.isH264Codec() #also works work mkv
    
    # VideoFormat is format info....
    def getFormatNames(self):
        return self.formatInfo.formatNames()
    
    def getRotation(self):
        if self.getVideoStream():
            return self.getVideoStream().getRotation()
        return 0
    
    def getLanguages(self):
        lang = []
        for audio in self.audio:
            res = audio.getLanguage()
            if res != VideoFormatInfo.NA and res not in lang:
                lang.append(res)
        return lang 
    
    # tuple with stream index and the language -for FFmpegCutter
    def getLanguageMapping(self):
        lang={} #key code, value: tuple(audio index, subtitle index)
        for stream in self.streams:
            if stream.isVideo():
                continue
            res = stream.getLanguage()
            if res == VideoFormatInfo.NA:
                continue
            
            if res not in lang:
                lang[res]=[-1,-1]
            
            if stream.isAudio():
                if lang[res][0]==-1:
                    lang[res][0]=stream.slot #MPV specific, might not be the stream number.. 
                    
            elif lang[res][1]==-1:
                lang[res][1]=stream.slot
        return lang 
   
    def hasFormat(self, formatName):
        return formatName in self.getFormatNames() 
    
    def isKnownVideoFormat(self):
        fmt = self.getFormatNames()
        for container in fmt:
            if container in FORMATS.table:
                return True
        return False 
    
    def isTransportStream(self):
        return self.hasFormat("mpegts")
    
    '''
    is MP4? Since its a formatcheck it can't be mp4-TS
    '''

    def isMP4Container(self): 
        return self.hasFormat("mp4")
    
    def isMPEG2Codec(self):
        if self.getVideoStream():
            return "mpeg" in self.getVideoStream().getCodec()
        return False
        
    def isH264Codec(self):
        if self.getVideoStream():
            return "h264" == self.getVideoStream().getCodec()
        return False
    
    def isVC1Codec(self):
        if self.getVideoStream():
            return "vc1" == self.getVideoStream().getCodec()
        return False
    
    
    '''
    subtitles
    tested: subrip and move_text 
    '''
    def hasSubtitles(self):
        return len(self.subtitle) > 0
    
    def subtitleCodec(self):
        if self.hasSubtitles():
            return self.subtitle[0].getCodec()
        
        return None
        
    def firstSubtitleStream(self):
        if self.hasSubtitles():
            return self.subtitle[0]
        return None
    
    
    def printCodecInfo(self):
        print ("-------- Video -------------")
        s = self.getVideoStream()
        print ("Index:", s.getStreamIndex())
        print ("codec", s.getCodec())
        print ("getCodecTimeBase: ", s.getCodecTimeBase())
        print ("getTimeBase: ", s.getTimeBase())
        print ("getAspect ", s.getAspectRatio())
        print ("getFrameRate_r: ", s.frameRateMultiple())
        print ("getAVGFrameRate: ", s.frameRateAvg())  # Common denominator
        print ("getDuration: ", s.duration())
        print ("getWidth: ", s.getWidth())
        print ("getHeight: ", s.getHeight())
        print ("isAudio: ", s.isAudio())
        print ("isVideo: ", s.isVideo())
        
        print ("-------- Audio -------------")
        s = self.getAudioStream()  
        if not s:
            print ("No audio")
            return  
        print ("Index:", s.getStreamIndex())
        print ("getCodec:", s.getCodec())
        print ("bitrate(kb)", s.getBitRate())
        print ("getCodecTimeBase: ", s.getCodecTimeBase())
        print ("getTimeBase: ", s.getTimeBase())
        print ("getDuration: ", s.duration())
        print ("isAudio: ", s.isAudio())
        print ("isVideo: ", s.isVideo())
        print ("-----------Formats-----------")
        f=self.formatInfo
        print("Fmt Names:",f.formatNames())
        print("Fmt bitrate;",f.getBitRate())
        print("Fmt dur;",f.getDuration())
        print("Fmt size;",f.getSizeKB())
        print ("-----------EOF---------------")

    '''
[FORMAT]
filename=../Path/test.mp4
nb_streams=2
nb_programs=0
format_name=mov,mp4,m4a,3gp,3g2,mj2
format_long_name=QuickTime / MOV
start_time=0.000000
duration=62.484000
size=136068832
bit_rate=17421270
probe_score=100
TAG:major_brand=mp42
TAG:minor_version=0
TAG:compatible_brands=isommp42
TAG:creation_time=2016-08-29 09:55:41
TAG:com.android.version=6.0.1
[/FORMAT]

    '''


class VideoFormatInfo():
    NA = "N/A"
    TAG = "TAG:"

    def __init__(self, dataArray):
        self.dataDict = {}
        self.tagDict = {}
        self._parse(dataArray)

    def _parse(self, dataArray):
        for entry in dataArray:
            val=self.NA
            try:
                (key, val) = entry.strip().split('=')
            except:
                Log.error("Error in entry:%s", entry)
            if self.NA != val:
                if self.TAG in key:
                    key = key.split(':')[1]
                    self.tagDict[key] = val
                else:
                    self.dataDict[key] = val

    def _print(self):
        print ("***format data***")
        for key, value in self.dataDict.items():
            print (key, "->", value)
        
        print ("***tag data***")
        for key, value in self.tagDict.items():
            print (key, "->", value)
    
    def getDuration(self):
        if "duration" in self.dataDict:
            return float(self.dataDict['duration'])
        return 0.0
    
    def getBitRate(self):
        if "bit_rate" in self.dataDict:
            kbit = int(self.dataDict["bit_rate"]) / float(1024)
            return round(kbit)
        return 0
    
    def formatNames(self):
        if "format_name" in self.dataDict:
            values = self.dataDict['format_name']
            return values.split(',')
        return [self.NA]
            
    def getSizeKB(self):
        if "size" in self.dataDict:
            kbyte = int(self.dataDict["size"]) / float(1024)
            return round(kbyte)
        return 0.0
         

class VideoStreamInfo():
    # int values
    NA = "N/A"
    TAG = "TAG:"
    PIC ="DISPOSITION:attached_pic"
#     keys = ["index","width", "height","avg_frame_rate","duration","sample_rate"]
#     stringKeys =["codec_type","codec_name"]
#     divKeys =["display_aspect_ratio"]        
    
    def __init__(self, dataArray):
        self.dataDict = {}
        self.tagDict = {}
        self._parse(dataArray)
        self.slot=1 #thats the index in its list (mpv uses this) starting with 1
    
    def _parse(self, dataArray):
        for entry in dataArray:
            if entry.startswith('['):
                continue;
            
            try:
                (key, val) = entry.strip().split('=')
            except:
                Log.error("Error in entry:%s", entry)

            if self.NA != val:
                if self.TAG in key:
                    key = key.split(':')[1]
                    self.tagDict[key] = val
                else:
                    self.dataDict[key] = val
        
    def getStreamIndex(self):
        if 'index' in self.dataDict:
            return int(self.dataDict['index'])
    
    def getAspectRatio(self):
        if 'display_aspect_ratio' in self.dataDict:
            z, n = self.dataDict['display_aspect_ratio'].split(':')
            if z != '0' and n != '0':
                div = round(float(z + ".0") / float(n + ".0") * 100.0)
                return div / 100.0
        return 1.0

    def getRotation(self):
        result = self.dataDict.get('rotation',None)
        if result:
            return int(result)
        result = self.dataDict.get('TAG:rotate',None)
        if result:
            return int(result)
        result = self.tagDict.get('rotate',None)
        if result:
            return int(result)
        return 0;

    '''
    Smallest framerate in float
    r_frame_rate is NOT the average frame rate, it is the smallest frame rate that can accurately represent all timestamps. 
    So no, it is not wrong if it is larger than the average! For example, if you have mixed 25 and 30 fps content, 
    then r_frame_rate will be 150 (it is the least common multiple).
    '''
    def frameRateMultiple(self):
        if 'r_frame_rate' in self.dataDict:
            z, n = self.dataDict['r_frame_rate'].split('/')
            if int(n) != 0:
                return float(z) / int(n)
        return 1.0

    '''
    The average framerate might be wrong on webm muxers (vp8 codec) by a thousand. 
    It usually is ok when using transportstreams (where r_frame_rate shows the non interlaced frequency...)
    '''
    def frameRateAvg(self):
        if "avg_frame_rate" in self.dataDict:
            (n, z) = self.dataDict["avg_frame_rate"].split("/")
            if int(z) != 0:
                return float(n) / float(z) 
        return 1.0

    def saneFPS(self):
        if self.isInterlaced():
            return self.frameRateAvg()
        else:
            return self.frameRateMultiple()

    '''
    ‘tt’ =    Interlaced video, top field coded and displayed first 
    ‘bb’=  Interlaced video, bottom field coded and displayed first 
    ‘tb’= Interlaced video, top coded first, bottom displayed first 
    ‘bt’= Interlaced video, bottom coded first, top displayed first 
    '''
    def isInterlaced(self):
        interlacedID=["tb","tt","bt","bb"]
        if "field_order" in self.dataDict:
            fo=self.dataDict["field_order"]
            if fo in interlacedID:
                return True
        return False

    def getCodec(self):
        return self.dataDict.get('codec_name',self.NA)
    
    def codecTag(self): #sth like avc1 on h264 codec 
        return self.dataDict.get('codec_tag_string',self.NA)
    
    def hasAACCodec(self):
        return self.getCodec() == "aac"
    
    def getWidth(self):
        return self.dataDict.get('width',self.NA)

    def getHeight(self):
        return self.dataDict.get('height',self.NA)
    
    def isAVC(self):  # MOV, h264
        if 'is_avc' in self.dataDict:
            return "true" == self.dataDict['is_avc']
        return False
    
    def getCodecTimeBase(self):
        if 'codec_time_base' in self.dataDict:
            return self.dataDict['codec_time_base']
        return self.NA

    def getTimeBase(self):
        if 'time_base' in self.dataDict:
            return self.dataDict['time_base']
        return self.NA
 
    '''
    bitrate in kb (int)-Audio only
    '''

    def getBitRate(self):
        if "bit_rate" in self.dataDict:
            kbit = int(self.dataDict["bit_rate"]) / float(1024)
            return round(kbit)
        return 0

    '''
    length in seconds (float)
    '''            

    def duration(self):
        if "duration" in self.dataDict:
            return float(self.dataDict["duration"])
        return 0.0 
   
    '''
    some audio stuff
    '''
    def sampleRate(self):
        return int(self.dataDict.get("sample_rate","0"))
    
    def audioChannels(self):
        return int(self.dataDict.get("channels","0"))  

    def isValidAudio(self):
        return self.sampleRate()>0 and self.audioChannels()>0 and self.getCodec()!= VideoStreamInfo.NA
   
    def getLanguage(self):
        if "language" in self.tagDict:
            val = self.tagDict['language']
            if "und" in val:
                return self.NA
            return val
        return self.NA
    
    def _picAttached(self):
        return self.dataDict.get(self.PIC,"0")=="1"
    
    def isAudio(self):
        # Is this stream labeled as an audio stream?
        return str(self.dataDict.get('codec_type',"")) == 'audio'

    def isVideo(self):
        #Is the stream labeled as a video stream.
        return str(self.dataDict.get('codec_type',"")) == 'video' and not self._picAttached()
        
    def isSubTitle(self):
        # Is this stream labeled as subtitle stream?
        return str(self.dataDict.get('codec_type',"")) == 'subtitle'


class FFFrameProbe():

    def __init__(self, video_file):
        self.frames = []
        self.path = video_file
        # self._readDataByLines()
        self._readData()
    
    def _readDataByLines(self):
        p = subprocess.Popen(["ffprobe", "-select_streams", "v:0", "-show_frames", self.path, "-v", "quiet"], stdout=subprocess.PIPE)
        proc = 0;
        while True:
            line = p.stdout.readline()
            if not line:
                break
            if re.match(r'\[\/FRAME\]', line):
                proc += 1
                
#             dataBucket = self.__processLine(line,dataBucket)
#             if len(dataBucket)==0:
#                 proc+=1
#                 print "p ",proc
            
    def __processLine(self, aString, dataBucket):
        if re.match(r'\[FRAME\]', aString):
            dataBucket = []
        elif re.match(r'\[\/FRAME\]', aString):
            self.frames.append(VideoFrameInfo(dataBucket))
            dataBucket = []
        else:
            dataBucket.append(aString)
        return dataBucket
   
    def _readData(self):
        result = Popen(["ffprobe", "-select_streams", "v:0", "-show_frames", self.path, "-v", "quiet"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        if len(result[0]) == 0:
            raise IOError('No such media file ' + self.path)
        self.frames = []
        datalines = []
        
        lines = result[0].decode("utf-8").split('\n')
        for a in lines:
            if re.match(r'\[FRAME\]', a):
                datalines = []
            elif re.match(r'\[\/FRAME\]', a):
                self.frames.append(VideoFrameInfo(datalines))
                datalines = []
            else:
                datalines.append(a)


class VideoFrameInfo():
    '''
    [FRAME]
    media_type=video
    +key_frame=0
    pkt_pts=143730
    +pkt_pts_time=1.597000
    pkt_dts=143730
    pkt_dts_time=1.597000
    best_effort_timestamp=143730
    best_effort_timestamp_time=1.597000
    pkt_duration=1800

    pkt_duration_time=0.020000
    pkt_pos=1787538
    pkt_size=12425
    width=1280
    height=720
    pix_fmt=yuv420p
    sample_aspect_ratio=1:1
    +pict_type=B
    +coded_picture_number=62
    display_picture_number=0
    interlaced_frame=0
    top_field_first=0
    repeat_pict=0
    [/FRAME]
    '''
    
    NA = "N/A"
    validKeys = ["key_frame", "pkt_pts_time", "pict_type", "coded_picture_number"]

    def __init__(self, dataArray):
        self.dataDict = {}
        self._parse(dataArray)
    
    def _parse(self, dataArray):
        for entry in dataArray:
            result = entry.strip().split('=')
            if len(result) == 2:
                key = result[0]
                val = result[1]
                if self.NA != val and key in self.validKeys:
                    self.dataDict[key] = val
    
    '''
    Usually an I-Frame
    '''

    def isKeyFrame(self):
        if self.dataDict["key_frame"]:
            return self.dataDict["key_frame"] == "1"
        return False
    
    '''
    Frame time in millisconds (float)
    '''

    def frameTime(self):
        if self.dataDict["pkt_pts_time"]:
            return float(self.dataDict["pkt_pts_time"]) * 1000.0
        return 0.0
    
    '''
    either P, B or I
    '''

    def frameType(self):
        if self.dataDict["pict_type"]:
            return self.dataDict["pict_type"]
        return self.NA
    
    '''
    Index of frame (int)
    '''

    def frameIndex(self):
        if self.dataDict["coded_picture_number"]:
            return int(self.dataDict["coded_picture_number"])

        
class FFmpegVersion():

    def __init__(self):
        self.error=None
        self.version = 0.0;
    
    def confirmFFmpegInstalled(self):
        return which(BIN)  
    
    def figureItOut(self):
        try:
            result = subprocess.Popen(["/usr/bin/ffmpeg", "-version"], stdout=subprocess.PIPE).communicate()
        except Exception as error:
            self.error = str(error)
            return
            
        if len(result[0]) > 0:
            text = result[0].decode("utf-8")
            m = re.search("[0-9].[0-9]+", text)
            g1 = m.group(0)
            print(g1)
            self.version = float(g1)
            Log.info("FFmepg Version:%.3f", float(g1))


class FFmpegPicture():

    def __init__(self, timestamp, somedata):
        self.ts = timestamp
    
    def getPicture(self):
        # big todo - der test stimmt frame genau
        # ffmpeg -ss 00:26:31.131 -i Guardians.of.the.Galaxy.Vol.2UHD.m4v -vframes 1 -filter:v scale=3840:1604 -y gog.png
        return True 
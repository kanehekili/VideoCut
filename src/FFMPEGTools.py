'''
Created on Oct 4, 2014
FFMPEG Wrapper - AVCONV will not be supported - ever.
@author: kanehekili
'''

import os,sys
import subprocess
from subprocess import Popen
from datetime import timedelta
import time
import re
import logging
import json
from logging.handlers import RotatingFileHandler
from itertools import tee
import configparser
from shutil import which
import gzip


def setupRotatingLogger(logName,logConsole):
    logSize=5*1024*1024 #5MB
    folder = OSTools().getActiveDirectory()
    if not OSTools().canWriteToFolder(folder): 
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

    #that is the directory where the file resides
    def getWorkingDirectory(self):
        abspath = os.path.abspath(__file__)
        dname = os.path.dirname(abspath)
        return dname               

    def moduleDir(self):
        return os.path.dirname(__file__)

    #location of "cwd", i.e where is bash..
    def getActiveDirectory(self):
        return os.getcwd()
    
    #check if filename only or the complete path
    def isAbsolute(self,path):
        return os.path.isabs(path)

    #The users home directory - not where the code lies
    def getHomeDirectory(self):
        return os.path.expanduser("~")

    def setCurrentWorkingDirectory(self):
        os.chdir(self.getWorkingDirectory())
        
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


BIN = "ffmpeg"
Log=logging.getLogger("Main")

def parseCVInfos(cvtext):
    lines = cvtext.splitlines(False)
    cvDict = {}
    for line in lines:
        match = re.search("(?<=OpenCV)\s*(\d\S*[a-z]*)+", line)
        if match: 
            cvDict["OpenCV"] = match.group(1)
            continue
            
        match = re.search('(?<=Baseline:)\s*([ \w]+)+', line)
        if match:
            cvDict["BaseLine"] = match.group(1) 
            continue
        match = re.search("(?<=GTK\+:)\s*(\w+[(\w+ ]*[\d.]+[)]*)+", line)
        if match: 
            cvDict["GTK+"] = match.group(1)
            continue
        match = re.search("(?<=FFMPEG:)\s*(\w+)", line)
        if match:
            cvDict["FFMPEG"] = match.group(1) 
            continue
        match = re.search("(?<=avcodec:)\s*(\w+[(\w+ ]*[\d.]+[)]*)+", line)
        if match:
            cvDict["AVCODEC"] = match.group(1) 
            continue
    return cvDict


def timedeltaToFFMPEGString(deltaTime):
    ms = int(deltaTime.microseconds / 1000)
    s = deltaTime.seconds
    hours, remainder = divmod(s, 3600)
    minutes, seconds = divmod(remainder, 60)
    so = str(seconds).rjust(2, '0')
    mo = str(minutes).rjust(2, '0')
    ho = str(hours).rjust(2, '0')
    mso = str(ms).rjust(3, '0')
    return '%s:%s:%s.%s' % (ho, mo, so, mso)


def timedeltaToString2(deltaTime):
    ms = int(deltaTime.microseconds / 1000)
    s = deltaTime.seconds
    so = str(s).rjust(2, '0')
    mso = str(ms).rjust(3, '0')
    return '%s.%s' % (so, mso)
'''
def log(*messages): #text value only...
    # Hook for logger...
    # cnt = len(messages)
    #print("{0} {1}".format(*messages))
    Log.logInfo("{0} {1}".format(*messages))
    
    cnt = len(messages)
    r= range(cnt)
    tmp=[]
    for n in r:
        tmp.append('{')
        tmp.append(str(n))
        tmp.append('}')
    fmt=''.join(tmp)    
    Log.logInfo(fmt.format(*messages))
    
'''
    
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
Return array with two dicts:
dict 0= code->language
dict 1 = language->code
'''
class _Iso639Model():
    NOCODE="und"
    NOLANG="Undetermined"

    def __init__(self):
        model=self.readIso639Map()
        self.codeToLang=model[0]
        self.langToCode=model[1]
   
    def readIso639Map(self):
        # read the iso file
        HomeDir = os.path.dirname(__file__)
        DataDir = os.path.join(HomeDir, "data")
        path = os.path.join(DataDir, "countryIso639.json")
        with open(path, 'r')as f:
            result = json.load(f) 
            
        return result
    
    #answer the 3 letter code for a country name that is included in "pref" (like deu or ger)
    def codeForCountry(self,countryName, pref=None):
        codes = self.langToCode.get(countryName,[self.NOCODE])
        if pref is not None:
            for isoCode in codes:
                if isoCode in pref:
                    return isoCode
        
        return codes[0] 
    
    def countryForCode(self,code):
        return self.codeToLang.get(code,self.NOLANG)

#factory:
def IsoMap(_singleton=_Iso639Model()):
    return _singleton
   
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
        for vInfo in currFormats:
            if vInfo=="mpegts":
                continue
            res = self.targetExt.get(vInfo,None)
            if res:
                return res;
                
        #IF not found ...
        fmap = self._findFmtTargetMap(vCodec, aCodec)
        if fmap:
            return fmap.targetExt
        return "mp4" #or what?

                

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
            if re.match('\[STREAM\]', a):
                datalines = []
            elif re.match('\[\/STREAM\]', a):
                self.streams.append(VideoStreamInfo(datalines))
                datalines = []

            elif re.match('\[FORMAT\]', a):
                datalines = []
            elif re.match('\[\/FORMAT\]', a):
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
        if self.getVideoStream() is None:
            raise IOError("No video stream available")
        if logging.root.level!=logging.DEBUG:
            return 
        Log.debug("-------- Video -------------")
        s = self.getVideoStream()
        Log.debug("Index: %d", s.getStreamIndex())
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
        if not s:
            Log.debug("No audio")
            return  
        Log.debug("Index:%d", s.getStreamIndex())
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
        return self.getAudioStream().getCodec() == "aac" and (self.isH264() or self.isMP4Container())
    
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
        return self.getVideoStream().getRotation()
    
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
                    lang[res][0]=stream.getStreamIndex()
                    
            elif lang[res][1]==-1:
                lang[res][1]=stream.getStreamIndex()
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
        return "mpeg" in self.getVideoStream().getCodec()
        
    def isH264Codec(self):
        return "h264" == self.getVideoStream().getCodec()
    
    def isVC1Codec(self):
        return "vc1" == self.getVideoStream().getCodec()
    
    
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
    
    def isAudio(self):
        # Is this stream labeled as an audio stream?
        return str(self.dataDict.get('codec_type',"")) == 'audio'

    def isVideo(self):
        #Is the stream labeled as a video stream.
        return str(self.dataDict.get('codec_type',"")) == 'video'
        
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
            if re.match('\[\/FRAME\]', line):
                proc += 1
                
#             dataBucket = self.__processLine(line,dataBucket)
#             if len(dataBucket)==0:
#                 proc+=1
#                 print "p ",proc
            
    def __processLine(self, aString, dataBucket):
        if re.match('\[FRAME\]', aString):
            dataBucket = []
        elif re.match('\[\/FRAME\]', aString):
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
            if re.match('\[FRAME\]', a):
                datalines = []
            elif re.match('\[\/FRAME\]', a):
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

        
class CuttingConfig():

    def __init__(self, srcfilePath, targetPath, audioTracks,subsOn,zTime=None):
        ''' Sets an object that understands say(aText)'''
        self.messenger = None
        self.reencode = False
        self.streamData = None
        self.srcfilePath = srcfilePath
        self.targetPath = targetPath
        self.languages = audioTracks
        self.subtitlesOn=subsOn #to make ffmpeg concat possible
        self.calcZeroTime=zTime

    def supportSubtitles(self):
        return self.streamData.hasSubtitles() and self.subtitlesOn

class FFMPEGCutter():
    MODE_JOIN = 1;
    MODE_CUT = 2;

    def __init__(self, cutConfig, totalTime):
        self._config = cutConfig
        self._tempDir = '/tmp'
        self._tmpCutList = self._getTempPath() + "cut.txt"
        self._fragmentCount = 1;  
        self.videoTime = totalTime
        self.secsCut = 0;
        self.runningProcess = None;
        self.killed = False
        self.errors = []
        self.langMappings = self._buildMapping()
    
    '''
    cut
    '''

    def cutPart(self, startTimedelta, endTimedelta, index=0, nbrOfFragments=1):
        self._fragmentCount = nbrOfFragments
        prefetchTime = startTimedelta  # comp

        prefetchString = timedeltaToFFMPEGString(prefetchTime)
        
        deltaMillis = (endTimedelta - startTimedelta).microseconds
        deltaSeconds = (endTimedelta - startTimedelta).seconds 
        durString = timedeltaToFFMPEGString(timedelta(seconds=deltaSeconds, microseconds=deltaMillis))

        # fast search - which is key search
        Log.info('Prefetch seek/dur:%s >> %s ', prefetchString, durString)
        if nbrOfFragments == 1:
            fragment = self.targetPath()
        else:
            ext = self.retrieveConcatExtension()
            fragment = self._getTempPath() + str(index) + ext
        Log.debug("generate file:%s", fragment)
        self.say("Cutting part:" + str(index))
        
        cmdExt = self._videoMode()
        audioMode = self._audioMode(self.MODE_CUT)
        subTitleMode= self._subtitleMode()
        # the prefetch time finds a keyframe closest. post seek does not improve the result 
        
        cmd = [BIN, "-hide_banner", "-y", "-ss", prefetchString, "-i", self.filePath(), "-t", durString]
        cmdExt.extend(audioMode)
        cmdExt.extend(subTitleMode)
        if len(self.langMappings) > 0:
            cmd.extend(self.langMappings)
        cmdExt.extend(["-avoid_negative_ts", "1", "-shortest", fragment])
        cmd.extend(cmdExt)
        Log.debug("cut:%s", cmd)
        prefix = "Cut part " + str(index) + ":"  
        try:
            for path in executeAsync(cmd, self):
                self.parseAndDispatch(prefix, path)
        except Exception as error:
            self.say("Cutting part %s failed: %s " % (str(index), str(error)))
            self.warn("Error: %s" %(str(error)))
            self.runningProcess = None
            return False
        
        self.secsCut = self.secsCut + deltaSeconds;
        self.runningProcess = None
        return True
    
    '''
    Rules:
    aac_adtstoasc only in an mp4/mov container
    ac3 to aac should optional and only if mp4 container
    reencode must change the container(.extension) to mp4
    test: AC-3 problems
    Test mp2: good
    Base problem: AC-3 should be replaced by either mp2 or aac in mp4 container (AVC Video)
    '''

    #TODO: use containerlist for best audio codec (eg avi to mp4 can only be reencoded)

    def _audioMode(self, mode):
        # streamData is FFStreamProbe
        if self._config.streamData.getAudioStream() is None:
            return []
        targetFmt = FORMATS.fromFilename(self.targetPath())
        Log.debug("audio: %s  targets:%s", self._config.streamData.getAudioStream().getCodec(),targetFmt) #TODO logging
        container=targetFmt.format
        lib = "copy"
        if self._config.reencode:
            targetFmt = FORMATS.fromFilename(self.targetPath())
            lib = targetFmt.audioFormat()
        
        if self._config.streamData.needsAudioADTSFilter():            
            return ["-c:a", lib, "-bsf:a", "aac_adtstoasc"]

        if self._config.streamData.isMPEG2Codec() and container=='mpegts' and (self._fragmentCount == 1 or mode == self.MODE_JOIN):
            return ["-c:a", lib, "-f", "dvd"]

        # This must be configurable - at least for tests. mp2 seems to work for kodi+mp4
#        if self._config.streamData.getVideoStream().getCodec()=="h264" and self._config.streamData.getAudioStream().getCodec()=="ac3":
#            return ["-c:a","mp2"] #test for kodi or aac?       
#             elif (codec == "ac3"): #TDO and avc /mp4 video codec.
#                 return ["-c:a","aac"]

        return ["-c:a", lib]
 
    def _videoMode(self):
        videoStream = self._config.streamData.getVideoStream() 
        # TODO: wrong: The target defines which codec we are using....
        
        srcFmt = FORMATS.fromFilename(self.filePath())
        srcContainer=srcFmt.format
        

        Log.debug("video %s:", videoStream.getCodec())
        lib="copy"
        bsf=None
        codec=None
        if self._config.reencode:
            # TODO: chec if valid
            targetFmt = FORMATS.fromFilename(self.targetPath())
            lib = targetFmt.videoFormat()
            #return ["-c:v", lib, "-preset", "medium"]  # -preset slow -crf 22
        
        if self._config.streamData.needsH264Filter():# and srcContainer == 'mp4': #TODO educated guess,MKV target OK
            bsf=["-bsf:v", "h264_mp4toannexb"] 
            if self._fragmentCount > 1 and not self._config.supportSubtitles():  # CUT ONLY -NOT JOIN!
                codec=["-f", "mpegts"] #TODO; and waht about audio and dvd??

        cmd = ["-c:v", lib]
        if bsf is not None:
            cmd.extend(bsf)
        if codec is not None:
            cmd.extend(codec)    
        return cmd
    
    def _subtitleMode(self):
        '''
        Adding srt file: (tx3g codec)
        ffmpeg -i ocean-fast.mp4 -i CM.de.srt  -c:v copy -c:a copy -c:s mov_text -y DEFA-SRT.mp4
        ffmpeg -i "DEFA - East German trailer subs.mkv" -c:v copy -c:a copy -c:s mov_text -y DEFA-SRT.mp4 
        >>add CM srt., copy stuff and make srt a mov text
        cutting srt in mkv:
        ffmpeg -ss 1004.128 -i title_t00.mkv -t 00:00:30.00 -c:v copy -c:a copy -c:s copy xf.mkv
        remux hd_pgm text(blueray) to mp4:
        ?
        -scodec [subtitle codec]
        Not every subtitle codec can be used for every video container format!
        [subtitle codec] parameter examples:
        for MKV muxers: copy, ass, srt, ssa (srt=pref, copy if same)
        for MP4 muxers: copy, mov_text
        for MOV muxers: copy, mov_text         
        
        mov_text = mp4 subrip... Blueray=hdmv_pgs_subtitle
        
        S..... ssa                  ASS (Advanced SubStation Alpha) subtitle (codec ass)
        S..... ass                  ASS (Advanced SubStation Alpha) subtitle
        S..... dvbsub               DVB subtitles (codec dvb_subtitle)
        S..... dvdsub               DVD subtitles (codec dvd_subtitle)
        S..... mov_text             3GPP Timed Text subtitle
        s..... srt                  SubRip subtitle (codec subrip)
        S..... subrip               SubRip subtitle
        S..... text                 Raw text subtitle
        S..... ttml                 TTML subtitle
        S..... webvtt               WebVTT subtitle
        S..... xsub                 DivX subtitles (XSUB)

        ffmpeg is not able to convert Picture subs into text subs and vice versa. 
        A pgssub can't be converted into mov_text/srt...
        '''
        
        if self._config.supportSubtitles():
            scopy = "copy"
            cmd="-c:s"
            srcFmt = FORMATS.fromFilename(self.filePath())
            targetFmt = FORMATS.fromFilename(self.targetPath())
            if srcFmt.targetExt != targetFmt.targetExt:
                subSrc= self._config.streamData.subtitleCodec()
                subTarget= targetFmt.subtitleFormat()
                if not FORMATS.sameSubGroup(subSrc,subTarget): #TODO ? Only if we can't copy them.  
                    Log.warning("subtitle: src and target are not same text or image")
                    return []
                if subTarget is None:
                    Log.warning("subtitle: container does not support subtitles")
                    return[]
                scopy=subTarget
                
            res=[cmd,scopy]
            return res
        return []
    
    def _getTempPath(self):
        return self._tempDir + '/vc_'
    
    def _buildMapping(self):
        # check if there needs to be a mapping for audio. Makes sense if there are more than one,
        # and the prefered mappings should fit
        # -map 0:0 -map 0:4 -map 0:1
        vs = self._config.streamData.getVideoStream()
        videoMap = "0:" + str(vs.getStreamIndex())
        mapList = ["-map", videoMap]  # this is video
        
        
        #TODO subtitle language mapping only, if codecs/formats fit. 
        scopy = self._subtitleMode()
        langMap = self._config.streamData.getLanguageMapping() #dict lang, (aindex,sIndex)
        avail = self._config.streamData.getLanguages()
        selectedLangs = self._config.languages #intl language
        prefCode=[] 
        for lang in selectedLangs:
            prefCode.append(IsoMap().codeForCountry(lang,avail))

        for code,indexTuple in langMap.items():
            if code in prefCode: 
                entry = "0:" + str(indexTuple[0])
                mapList.append("-map")
                mapList.append(entry)
                if len(scopy)>0:
                    entry = "0:" + str(indexTuple[1])
                    mapList.append("-map")
                    mapList.append(entry)
                
        '''
        for lang in prefLangs:
            if lang in langMap:
                entry = "0:" + str(langMap[lang])
                mapList.append("-map")
                mapList.append(entry)
        '''
        if len(mapList) > 2:
            return mapList
        return []
    
    #Either target ext or m2t if we need mpegts format..
    #?if self._config.streamData.needsH264Filter()->TS
    def retrieveConcatExtension(self):
        default = ".m2t"
        tool=OSTools()
        srcExt = tool.getExtension(self.filePath())
        targetExt = tool.getExtension(self.targetPath())
        if "mp" in srcExt:
            return default
        return targetExt
    
    def filePath(self):
        return self._config.srcfilePath
    
    def targetPath(self):
        return self._config.targetPath
    
    def join(self):
        # TODO hows the timing? aka video time??? 
        # add all files into a catlist: file '/tmp/vc_tmp0.m2t' ..etc
        # ffmpeg -f concat -i catlist.txt  -c copy concat.mp4
        # reencoding takes place in the cut - NOT here.
        # TODO check fifo: https://video.stackexchange.com/questions/30548/how-to-merge-multiple-mp4-videofiles-using-concat-of-ffmpeg-while-transposing-18
        if self._fragmentCount == 1:
            return

        self.say("Joining files...")
        
        with open(self._tmpCutList, 'w') as cutList:
            for index in range(0, self._fragmentCount):
                tmp = self._getTempPath() + str(index) + self.retrieveConcatExtension()
                cutList.write("file '" + tmp + "'\n")

        base = [BIN, "-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", self._tmpCutList, "-c:v","copy","-c:s", "copy"]
        cmd = base + self._audioMode(self.MODE_JOIN)
        if len(self.langMappings) > 0:
            cmd.extend(["-map", "0"])
        cmd.append(self.targetPath())
        Log.info("join:%s", cmd)
        prefix = "Join:"  
        try:
            for path in executeAsync(cmd, self):
                self.parseAndDispatch(prefix, path)
                # print(path,end="")
        except Exception as error:
            self.say("join failed: %s" % (error))
            self.warn("join: %s" % (error));
            self.runningProcess = None
            return False

        self.runningProcess = None      
        self.say("Films joined")
        self._cleanup()
        return True

    def say(self, text):
        if self._config.messenger is not None:
            self._config.messenger.say(text) 
            
    def parseAndDispatch(self, prefix, text): 
        try:  
            m = re.search('frame=[ ]*[0-9]+', text)
            p1 = m.group(0)
            m = re.search('time=[ ]*[0-9:.]+', text)
            p2 = m.group(0)
            self.say(prefix + " " + p1 + " - " + p2)
            curr = self.stringToSeconds(p2)
            perc = ((self.secsCut + curr) / self.videoTime.seconds) * 100
            self._config.messenger.progress(perc)
        except:
            if len(text) > 5:
                print ("<" + text.rstrip())   
        if "failed" in text:
            Log.error("FFmpeg error: %s", text)
            self.say(prefix + " !Conversion failed!")
            self.warn(text);
            return False
        else:
            return True 
    
    def stringToSeconds(self, string):
        items = string.split(":")
        hrs = items[0].split('=')[1]
        mins = items[1]
        sec = items[2].split('.')[0]
        return int(hrs) * 3600 + int(mins) * 60 + int(sec)

    def ensureAvailableSpace(self):
        if not self._hasEnoughAvailableSpace(self._tempDir):
            path = os.path.expanduser("~")
            self.ensureDirectory(path, ".vc_temp")

    def _hasEnoughAvailableSpace(self, tmpDir):
        result = Popen(["df", "--output=avail", tmpDir], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        if len(result[1]) > 0:
            print ("Error using df:" + result[1])
            return False
        
        rows = result[0].decode("utf-8").split('\n')
        if len(rows) > 1:
            # Filesystem      Size  Used Avail Use% Mounted on
            avail = int(rows[1]) * 1024

        needed = os.path.getsize(self.filePath())
        print ("file size:", needed, " avail:", avail, "has enough:", needed <= avail)
        return needed <= avail
    
    def _cleanup(self):
        for index in range(self._fragmentCount):
            fragment = self._getTempPath() + str(index) + self.retrieveConcatExtension()
            os.remove(fragment)   

    def ensureDirectory(self, path, tail):
        # make sure the target dir is present
        if tail is not None:
            path = os.path.join(path, tail)
        if not os.access(path, os.F_OK):
            try:
                os.makedirs(path)
                os.chmod(path, 0o777)
            except OSError:
                self.warn("Error creating directory")
                return
        self._tempDir = path    

    def setProcess(self, proc):
        self.runningProcess = proc;   

    def stopCurrentProcess(self):
        # Stop button has been pressed....
        self.killed = True
        if self.runningProcess is None:
            Log.warning("Can't kill proc! -Error")
            self.warn("Can't kill proc!", "-Error")
        else:
            print("FFMPEGCutter - stop process")
            self.runningProcess.kill()    
    
    def wasAborted(self):
        return self.killed
    
    def warn(self, text):
        self.errors.append(text)
    
    def hasErrors(self):
        return len(self.errors) > 0
    
    def getErrors(self):
        return self.errors

    
class VCCutter():

    def __init__(self, cutConfig):
        self.config = cutConfig
        #self.setupBinary()
        self.regexp = re.compile("([0-9]+) D:([0-9.]+) (.+) ([0-9.]+)%")
        self.runningProcess = None
        self.killed = False
        self.errors = []
        
    def setupBinary(self):
        fv = FFmpegVersion()
        fv.figureItOut()
        if fv.error is not None:
            self.warn("No FFMPEG libraries found - Choose FFMPEG as muxer")
            return False
        if fv.version < 3.0:
            self.warn("Invalid FFMPEG Version! Needs to be 3.0 or higher") 
            return False
        val = str(fv.version)[:1]
        p = OSTools().getWorkingDirectory();
        tail = "ffmpeg/bin/V" + val + "/remux5"
        self.bin = os.path.join(p, tail)
        return True

    # cutlist = [ [t1,t2] [t3,t4]...]
    def cut(self, cutlist):
        # code = remux5 infile outfile -s t1,t2,t3,t4 -e
        # todo -e if flag is set
        # todo -d if debug
        slices = len(cutlist)
        timeString = []
        for index, cutmark in enumerate(cutlist):
#            t1 = cutmark[0].timePos
#            t2 = cutmark[1].timePos
            t1 = cutmark[0].timeDelta()
            t2 = cutmark[1].timeDelta()
            
            timeString.append(timedeltaToString2(t1))
            timeString.append(',')
            timeString.append(timedeltaToString2(t2))
            if index + 1 < slices:
                timeString.append(',')    
                    
        timeString = ''.join(timeString)
        cmd = [self.bin, "-i", self.config.srcfilePath, "-s", timeString]
        if self.config.reencode:
            cmd = cmd + ["-r"]
        if self.config.calcZeroTime:
            cmd = cmd + ["-z"]
        lang = self._buildLanguageMapping()
        if len(lang) > 0:
            codes = ",".join(lang) 
            cmd = cmd + ["-l", codes]
        cmd = cmd + [self.config.targetPath]    
                
        print(cmd)
        Log.debug("cut file:%s", cmd)
        try:
            start = time.monotonic()
            for path in executeAsync(cmd, self):
                now = time.monotonic()
                elapsed = int(now - start)
                showProgress = elapsed >= 1
                ok = self.parseAndDispatch("Cutting ", path, showProgress)
                if ok:
                    start = now

        except Exception as error:
            self.warn("Remux failed: %s" % (error))
            Log.error("Remux failed %s", str(error))
            self.runningProcess = None
            return False
        
        self.say("Cutting done")
        self.runningProcess = None
        return True
    
    def _buildLanguageMapping(self):
        # check if there needs to be a mapping for audio. Makes sense if there are more than one,
        # and the prefered mappings should fit
        
        codes = []
        
        codeList = self.config.streamData.getLanguages() #3letter codes == base
        prefLangs = self.config.languages #Intl Lang ->convert to 3 letter code.
        for lang in prefLangs:
            code = IsoMap().codeForCountry(lang, codeList)
            if code in codeList:
                codes.append(code)
                
        if len(codes) > 0:
            return codes
        return []

    def say(self, text):
        if self.config.messenger is not None:
            self.config.messenger.say(text) 

    def warn(self, text):
        self.errors.append(text)

    def parseAndDispatch(self, prefix, text, showProgress): 
        try:        
            m = self.regexp.search(text) 
            frame = m.group(1)
            dts = m.group(3)
            progress = int(round(float(m.group(4))))
            if showProgress:
                self.say(prefix + " Frame: %s Time: %s" % (frame, dts))
                self.config.messenger.progress(int(progress))
            else:
                return False
        except:
            if len(text) > 5:
                aLine= text.rstrip()
                print ("<" + aLine )  
                if "Err:" in aLine:
                    Log.debug(">%s", aLine)
                    if not "muxing" in aLine: 
                        self.warn(aLine);
            return False
        else:
            return True 

    def setProcess(self, proc):
        self.runningProcess = proc   
        
    def stopCurrentProcess(self):
        # Stop button has been pressed....
        self.killed = True
        if self.runningProcess is None:
            Log.error("Can't kill proc! -Error")
        else:
            print("VCCutter - stop process")
            self.runningProcess.kill()
 
    def wasAborted(self):
        return self.killed   
    
    def hasErrors(self):
        return len(self.errors) > 0
    
    def getErrors(self):
        return self.errors

        
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

'''
joins a list of files. if they are NOT mts files the audio needs to be filtered. All files need to have the same codecs
'''


class FFmpegJoiner():

    def __init__(self):
        self.x = 1
        
    def join(self, listofFiles):
        print("todo")        
 
''' 
    def non_block_read(self,prefix,output):
        fd = output.fileno()
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        text = "."
        try:
            text = output.read()
            #m = re.search('frame=[ ]*[0-9]+',text)
            #p1 = m.group(0)
            #m = re.search('time=[ ]*[0-9:.]+',text)
            #p2 = m.group(0)
            #self.say(prefix+" "+p1+" - "+p2)
            #log(prefix,'frame %s time %s'%(p1,p2))
            print (text)
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
'''        
    

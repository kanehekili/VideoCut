'''
Created on Dec 19, 2022
Cutting tools here
@author: matze
'''

'''
Return array with two dicts:
dict 0= code->language
dict 1 = language->code
'''
import os
from datetime import timedelta
import time
import json
import re
import subprocess
from subprocess import Popen
import FFMPEGTools
from FFMPEGTools import OSTools,FFmpegVersion

Log=FFMPEGTools.Log
FORMATS=FFMPEGTools.FORMATS
binary = FFMPEGTools.BIN

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
        if not OSTools().fileExists(path):
            return (None,None)
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

class CuttingConfig():

    def __init__(self, srcfilePath, targetPath, audioTracks,subsOn,zTime=None):
        ''' Sets an object that understands say(aText)'''
        self.messenger = None
        self.reencode = False
        self.streamData = None
        self.muteAudio = False
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
        
        cmd = [binary, "-hide_banner", "-y", "-ss", prefetchString, "-i", self.filePath(), "-t", durString]
        cmdExt.extend(audioMode)
        cmdExt.extend(subTitleMode)
        if len(self.langMappings) > 0:
            cmd.extend(self.langMappings)
        cmdExt.extend(["-avoid_negative_ts", "1", "-shortest", fragment])
        cmd.extend(cmdExt)
        Log.debug("cut:%s", cmd)
        prefix = "Cut part " + str(index) + ":"  
        try:
            for path in FFMPEGTools.executeAsync(cmd, self):
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
        #TODO audiomute
        if self._config.muteAudio or self._config.streamData.getAudioStream() is None:
            return ["-an"]
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
        
        #srcFmt = FORMATS.fromFilename(self.filePath())
        #srcContainer=srcFmt.format
        

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
        if self._config.muteAudio:
            return []
        
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

        base = [binary, "-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", self._tmpCutList, "-c:v","copy","-c:s", "copy"]
        cmd = base + self._audioMode(self.MODE_JOIN)
        if len(self.langMappings) > 0:
            cmd.extend(["-map", "0"])
        cmd.append(self.targetPath())
        Log.info("join:%s", cmd)
        prefix = "Join:"  
        try:
            for path in FFMPEGTools.executeAsync(cmd, self):
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
        #This makes only sense if installed manually. On Arch and debian check if a file exists in bin
        self.bin=OSTools().joinPathes(p,"ffmpeg","bin","remux5")
        if not OSTools().fileExists(self.bin):
            vFolder ="V" + val
            self.bin = OSTools().joinPathes(p,"ffmpeg","bin",vFolder,"remux5") 
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
        if self.config.muteAudio:
            cmd = cmd + ["-m"]
        
        #TODO mute audio...
        lang = self._buildLanguageMapping()
        if len(lang) > 0:
            codes = ",".join(lang) 
            cmd = cmd + ["-l", codes]
        cmd = cmd + [self.config.targetPath]    
                
        print(cmd)
        Log.debug("cut file:%s", cmd)
        try:
            start = time.monotonic()
            for path in FFMPEGTools.executeAsync(cmd, self):
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



    
    

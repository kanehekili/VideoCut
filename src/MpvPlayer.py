'''
Created on Dec 20, 2021

@author: Kanehekili
The code is based on 
https://github.com/jaseg/python-mpv
under the
GNU Affero General Public License v3.0
'''
     
from PyQt5.QtCore import Qt,QMetaObject,pyqtSlot,pyqtSignal
from PyQt5 import QtCore,QtWidgets
from PyQt5 import QtGui
from PyQt5.QtWidgets import QApplication

from threading import Condition
import FFMPEGTools
import sys,time,re
import locale

try:
    from PyQt5.QtOpenGL import QGLContext    
except ImportError:
    print ("OpenGL lib not found")
    app = QApplication(sys.argv)
    QtWidgets.QMessageBox.critical(None, "OpenGL lib",'"python3-pyqt5.qtopengl" must be installed to run VideoCut.')
    sys.exit(1)    
    
try:
    from PIL.ImageQt import ImageQt #Not there by default...
except ImportError:
    print ("PIL lib not found")
    app = QApplication(sys.argv)
    QtWidgets.QMessageBox.critical(None, "PIL lib",'"python pillow" must be installed to run VideoCut.')
    sys.exit(1)    

try:
    from lib.mpv import (MPV,OpenGlCbGetProcAddrFn,MpvRenderContext,MpvEventEndFile)
except:
    print (("MPV lib not found"))  
    app = QApplication(sys.argv)
    QtWidgets.QMessageBox.critical(None, "MPV lib",'"mpv" must be installed to run VideoCut.')
    sys.exit(1)    

Log=FFMPEGTools.Log

def get_proc_addr(_, name):
    glctx = QGLContext.currentContext()
    if glctx is None:
        return 0
    addr = int(glctx.getProcAddress(name.decode('utf-8')))
    return addr


class VideoWidget(QtWidgets.QFrame):
    """ Sized frame for mpv """
    trigger = pyqtSignal(float,float,float)
    
    def __init__(self, parent):
        QtWidgets.QFrame.__init__(self, parent)
        self._defaultHeight = 518 #ratio 16:9
        self._defaultWidth = 921
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Sunken)
        self.setLineWidth(1)

    def sizeHint(self):
        return QtCore.QSize(self._defaultWidth, self._defaultHeight)

    def updateUI(self,frameNumber,framecount,timeinfo):
        self.trigger.emit(frameNumber,framecount,timeinfo)

class VideoGLWidget(QtWidgets.QOpenGLWidget):
    trigger = pyqtSignal(float,float,float)

    def __init__(self, parent,mpv):
        QtWidgets.QOpenGLWidget.__init__(self, parent)
        self.ratio= 1.0 #?is that true?
        self.mpv=mpv
        self.ctx = None
        self.get_proc_addr_c = OpenGlCbGetProcAddrFn(get_proc_addr)
        self._defaultHeight = 518 #ratio 16:9
        self._defaultWidth = 921

    def initializeGL(self):
        params = {'get_proc_address': self.get_proc_addr_c}
        self.ctx = MpvRenderContext(self.mpv,
                                    'opengl',
                                    opengl_init_params=params)
        self.ctx.update_cb = self.on_update

    def shutdown(self):
        if self.ctx is not None:
            self.ctx.free()
            self.ctx = None

    def paintGL(self):
        "init it on the 1st time"
        if self.ctx is None:
            self.initializeGL()
        # check if we really need a ratio on desktops
        #ratio = self._app.devicePixelRatio()
        w = int(self.width() * self.ratio)
        h = int(self.height() * self.ratio)
        opengl_fbo = {'w': w,
                      'h': h,
                      'fbo': self.defaultFramebufferObject()}
        self.ctx.render(flip_y=True, opengl_fbo=opengl_fbo)


    @pyqtSlot()
    def __update(self):
        if self.window().isMinimized():
            self.makeCurrent()
            self.paintGL()
            self.context().swapBuffers(self.context().surface())
            self.doneCurrent()
        else:
            self.update()

    def on_update(self, ctx=None):
        # __update method should run on the thread that creates the
        # OpenGLContext, which in general is the main thread.
        # QMetaObject.invokeMethod can do this trick.
        QMetaObject.invokeMethod(self, '__update')
    
    def sizeHint(self):
        return QtCore.QSize(self._defaultWidth, self._defaultHeight)

    def updateUI(self,frameNumber,framecount,timeinfo):
        self.trigger.emit(frameNumber,framecount,timeinfo)
    
    
class MpvPlayer():
    ERR_IDS=["No video or audio streams selected."]
    def __init__(self):
        self.mediaPlayer =None
        self.seekLock=Condition()
        self._frameInfoFunc=None
        self._resetState()
    
    def initPlayer(self,container):
        #self.__initPlayer()
        kwArgs=self.__baseMpvArgs()
        kwArgs["wid"]=str(int(container.winId()))
        self.mediaPlayer = MPV(**kwArgs)
        self._hookEvents()
        return self.mediaPlayer 
    
    def initGLPlayer(self):
        kwArgs=self.__baseMpvArgs()
        self.mediaPlayer = MPV(**kwArgs)
        self._hookEvents()
        return self.mediaPlayer 

    '''
    Profile low-latency: 
     audio-buffer=0
     vd-lavc-threads=1
     cache-pause=no
     demuxer-lavf-o-add=fflags=+nobuffer
     demuxer-lavf-probe-info=nostreams
     demuxer-lavf-analyzeduration=0.1
     video-sync=audio
     interpolation=no
     video-latency-hacks=yes
     stream-buffer-size=4k

    Performance:
    The higher the demuxeroffset, the better the "step" seek, but the worse the fast slider seek.
    Offset should be 0.1 for fast seek and 1.5 to 2.5 for slow seek (especially mpgts)
    '''    
    def __baseMpvArgs(self):
        return {   "hwdec":"auto-safe", 
            #video_sync="display-desync", #no effect on mkv/vc1
            "log_handler":self._passLog,
            "loglevel" : 'error',
            "input_vo_keyboard" : False,  #We'll take the qt events
            "pause" : True,
            "mute" : 'yes',
            #"video_latency_hacks" : "yes", #no avail sbtx
            "audio" : "no", #this improves seeking
            #"video_sync" : "desync", #improves seeking instead of audio = off
            #"initial_audio_sync" : "no", check this as an alternative
            "keep_open" : "always",
            #"rebase_start_time" : 'yes',  #default, no will show the real time
            #"hr_seek_framedrop" : 'no',  #yes=default, no=no effect on seek on mts
            #"stream_buffer_size" : '256MiB',#Works for uhd (dimensions>1920xx)
            #"deinterlace" : "yes",        #needed for m2t if interlaced...
            #"index" : "recreate",         #test for m2t
            #"demuxer_lavf_probescore" : 100, #not working with mpg
            "demuxer_lavf_analyzeduration" : 100.0,
            "video-latency-hacks" : "yes", #efficent for fast seek
            #"demuxer_backward_playback_step" : 1024, #no help
            #"video_sync" : "display-desync", #no help
            #"demuxer_lavf_probesize" : 1000, #won't load any mpg2 stream
            #"demuxer_lavf_probe_info" : 'yes',#not working on m2ts either
            "hr_seek" : 'yes',            #yes for slider search
            "hr_seek_demuxer_offset" : self._demuxOffset, #offset too large (2.1) will slow everything down, only if hr_seek is true
            #video_aspect_override" : "16:9, #works,but not necessary
            #demuxer_lavf_hacks" : 'yes', #test for m2t -no won't help 
            #the follwing entries enable mts back seeking: (https://github.com/mpv-player/mpv/issues/4019#issuecomment-747853186)
            "cache" : 'yes',
            "demuxer_seekable_cache" : 'yes',
            #no valid for libmpv < 0.30:
            #"demuxer_max_back_bytes " : '10000MiB',
            #"demuxer_cache_wait" : 'no', #if yes remote files take too long...
            #"demuxer_max_bytes " : '10000MiB',
            #"demuxer_backward_playback_step" : 180,
            "volume" : 100
            }
    
    def _resetState(self):
        self.framecount=0
        self.fps=25.0
        self.duration=0.0
        self._timePos=0.0
        self._demuxOffset=0.1
        self.isReadable=False
        self.play_func=None
        self._lastDispatch=0.0
        self.lastError=""
        self._readyMsgCount=0
        self._frameOffset=0        
    
    def _hookEvents(self):
        ver = self.mpvVersion()
        res= re.findall(r'\d+',ver)
        nbr = 100*int(res[0])+int(res[1])
        if nbr>30:
            self.mediaPlayer.demuxer_max_back_bytes='10000MiB'
            self.mediaPlayer.demuxer_cache_wait='no'
            Log.logInfo("applied demuxer settings for mpv > 3.x")
        
        observe=[]#"seeking","time-pos"...
        #ignore=["mouse-pos",""]
        #observe = [p for p in self.mediaPlayer.property_list if p not in ignore]
        for prop in observe:
            self.mediaPlayer.observe_property(prop, self._onPropertyChange)
            
        self.mediaPlayer.observe_property("time-pos",self._onTimePos) #messes up timing!
        self.mediaPlayer.observe_property("eof-reached",self._onPlayEnd)
        #mostly wrong: self.mediaPlayer.observe_property("estimated-frame-count",self._onFramecount)
        self.mediaPlayer.observe_property("video-frame-info",self._onFrameInfo)
    
    '''
    TEst with jasegs event handler...
    def open_withEvent(self,filePath):
        print("open:",filePath)
        try:
            self._resetState()
            self.mediaPlayer.close()
            self.mediaPlayer.loadfile(filePath)
            #Try to pin down a potential file error 
            @self.mediaPlayer.event_callback('end_file')
            def eofHandler(evt):
                self._superviseEndFileEvent(evt)
            self._getReady()
            eofHandler.unregister_mpv_events()
        except Exception as ex:
            Log.logException("Open mpv file")
            print(ex)
            
    def _superviseEndFileEvent(self,evt):
        if evt['event']['reason'] != MpvEventEndFile.REDIRECT or evt['event']['reason'] != MpvEventEndFile.RESTARTED:
            self.lastError=self.ERR_IDS[0] 
            with self.seekLock:
                print('check notify:',evt)
                self.seekLock.notify()
        
        return True
    '''        
    
    def open(self,filePath):
        try:     
            #Very verbose: self.mediaPlayer.register_event_callback(self._oncallback)
            self._resetState()
            self.mediaPlayer.loadfile(filePath)
            self._getReady()
        except Exception as ex:
            Log.logException("Open mpv file")
            print(ex)

    #Test, not activated    
    def _oncallback(self,callback):
        print("callback:",callback)#.event_id,">",callback.event.level)
        print(callback["event"])
        
    def close(self):
        if self.mediaPlayer:
            self.mediaPlayer.quit()
            
    def changeSettings(self,key,value):
        if self.mediaPlayer:
            if key=="subtitle":
                self.mediaPlayer.sid=int(value)
                
    def getCurrentFrameNumber(self):
        return int(round(self.timePos()*self.fps,0))
        
    def validate(self):
        pass #ffmpeg can read it ..

    #take the current time and add/subtract a number of frames and return the "absolute" new time
    def calcOffset(self,frameOffset):
        nxt=self.timePos()+(frameOffset/self.fps)
        return nxt

    def calcPosition(self,frameNumber):
        return frameNumber/self.fps
  
    #performance tweak: fastseek should have a low demuxer seek offset: tune if fast seek.
    def seek(self,frameNumber,fast=False):
        if self.mediaPlayer.seeking is None:
            Log.logError("No seek! Aborting")
            return
        step = frameNumber - self.getCurrentFrameNumber()
        if abs(step) < 20: #mpv hack: mpegts small distances
            self.seekStep(step)
            return
        secs = self.calcPosition(frameNumber)#hack
        #ts =self._timeAsString(secs)
        #print("1seek secs: %.3f %d >%s"%(secs,frameNumber,ts))
        if fast:
            self.mediaPlayer.hr_seek_demuxer_offset=0.1
        self.mediaPlayer.seek(secs,"absolute+exact")
        self._waitSeekDone()
        self.mediaPlayer.hr_seek_demuxer_offset=self._demuxOffset
        
    '''
    #unused    
    def __seekPrecise(self,dialStep):
        secs=self.calcOffset(dialStep)
        #print("dial:",dialStep)
        self.mediaPlayer.seek(secs,"absolute+exact")
        self._waitSeekDone()
    '''

    #using dialStep with relative leads to different timestamps... 
    def seekStep(self,dialStep):
        if self.mediaPlayer.seeking is not None:
            if dialStep == -1:
                self.mediaPlayer.frame_back_step()
                return
            if dialStep > 0:
                #self.mediaPlayer.frame_step() #crash at end/fills queue with afterruns
                fix=0.8
                if dialStep > 3:
                    fix=1.0
                nxt=(dialStep/self.fps)*fix
                if self.timePos()+nxt>self.duration:
                    return
            else:
                if self.timePos()>self.duration:
                    nxt=-1/self.fps*1.8
                else:
                    nxt=(dialStep/self.fps)*1.2
            self.mediaPlayer.seek(nxt,"relative+exact")
            #print("seek step1 %f time:%f dur:%f"%(nxt,self.timePos(),self.duration)) 
            self._waitSeekDone()
            #print("seekStep2 %f dial: %d currTime:%f"%(nxt,dialStep,self.timePos()))
        else:
            Log.logInfo("MPV: Seek none!")
                               
    def screenshotAtFrame(self,frameNumber):
        secs = self.calcPosition(frameNumber)
        self.mediaPlayer.seek(secs,"absolute+exact") #this works only, if seeking is done, otherwise crash.
        self._waitSeekDone()
        return self.screenshotImage()
    
    def screenshotImage(self):
        im=self.mediaPlayer.screenshot_raw(includes="video")
        return ImageQt(im)#scale? ==QImage        

    def takeScreenShot(self,path):
        self.mediaPlayer.screenshot_to_file(path,includes="video")
        return True
        
    def _onPropertyChange(self,name,pos):
        print("        >",name,":",pos)
    
    def _onDuration(self,name,val):
        if val is not None:
            self.duration=val
            Log.logInfo("durance detected:%.3f"%(val))
        
    def _onFrameInfo(self,name,val):
        if val is not None:
            #video-frame-info : {'picture-type': 'I', 'interlaced': False, 'tff': False, 'repeat': False}
            self.mediaPlayer.show_text(val['picture-type'],'0x7FFFFFFF') #32bit max
    
    def setFPS(self,newFPS):
        self.fps=newFPS
        self.framecount=self.duration*newFPS #framecount prop not reliable
        #often a difference between the mpv fps and the fmmpeg fps
        self.mediaPlayer["fps"]=newFPS
    
    '''            
    def _onFps(self,name,val):
        if val is not None:
            Log.logInfo("fps detected: %.5f"%(val))
            self.mediaPlayer.unobserve_property("estimated-vf-fps",self._onFps)
            self.setFPS(val)
    '''
    
    def _onTimePos(self,name,val):
        if val is not None:
            self._timePos=val
            if not self._frameInfoFunc:
                return

            if not self.mediaPlayer.pause:  #player hack...          
                now=time.monotonic()
                if now-self._lastDispatch < (1/self.fps):
                    return
                self._lastDispatch=now
            frameNumber=self.getCurrentFrameNumber()
            
            #ts =self._timeAsString(val)
            #print("TS:",val," fn:",frameNumber," real time:",ts," calc:",self.timePos())
            '''
            xfps = self.fps
            if xfps is None:
                xfps=-1.0
            xeps= self.mediaPlayer.estimated_vf_fps
            if xeps is None:
                xeps=-1.0
            print("prop time %.3f fps:%f fn:%d fc:%d"%(val,xfps,frameNumber,self.framecount))
            '''
            self._frameInfoFunc(frameNumber,self.framecount,self.timePos()*1000)
    
    #pure debug info
    def _timeAsString(self,val):
        s = int(val*1000/1000)
        ms = int(val*1000 % 1000)
        return '{:02}:{:02}:{:02}.{:03}'.format(s // 3600, s % 3600 // 60, s % 60, ms)   
    
    def _onPlayEnd(self,name,val):
        if val == True and self.play_func:
            self.play_func(False)
            
    def _onSeek(self,name,val):
        if val==False:
            with self.seekLock:
                self.seekLock.notify()
                self.mediaPlayer.unobserve_property("seeking",self._onSeek)
    
    def _waitSeekDone(self):
        self.mediaPlayer.observe_property("seeking",self._onSeek)
        with self.seekLock:  
            self.seekLock.wait(timeout=3)
    
    def _getReady(self):
        self.mediaPlayer.observe_property("estimated-vf-fps", self._onReadyWait)
        self.mediaPlayer.observe_property("duration", self._onReadyWait)
        self.seekLock=Condition()
        with self.seekLock:
            res = self.seekLock.wait(timeout=15.0)#networking=15
            broken = self.lastError in self.ERR_IDS
            self.isReadable=res and not broken 

    def _onReadyWait(self,name,val):
        if val is not None:
            with self.seekLock:
                    self.mediaPlayer.unobserve_property(name,self._onReadyWait)
                    if name == "estimated-vf-fps":
                        self.setFPS(val)
                    else:
                        self._onDuration(name, val)
                    self._readyMsgCount+=1
                    if self._readyMsgCount == 2:
                        self._readyMsgCount=0;
                        self.seekLock.notify()
    
    def _passLog(self,loglevel, component, message):
        msg='{}: {}'.format(component, message)
        Log.logError(">"+msg)
        with self.seekLock:
            self.lastError=message
            if "file" in message or message in self.ERR_IDS:
                self.seekLock.notifyAll()
                    
    def timePos(self):
        return self._timePos-self._frameOffset/self.fps #mpg mpv bug workaround
        #return self._timePos
       
    def isValid(self):
        return self.mediaPlayer.seekable
    
    def connectTo(self,func):
        self._frameInfoFunc=func
    
    #tweak for transport streams
    def tweakTansportStreamSettings(self,isInterlaced):
        Log.logInfo("Transport stream. Setting seek offset to high and interlacing: %d"%(isInterlaced))
        self._demuxOffset=1.5#Solution for mpegts seek
        if isInterlaced:
            self.mediaPlayer.deinterlace="yes"
 
    def tweakUHD(self):
        Log.logInfo("UHD, set stream size")
        self.mediaPlayer.stream_buffer_size='255MiB' 
 
    def tweakVC1(self):
        Log.logInfo("Set VC1 codec in MPV explictly")
        self.mediaPlayer.hwdec_codecs="vc1"       
 
    def tweakMPG(self):
        Log.logInfo("MP2: Setting frame offset in mpg (mpv bug) and seek offset to high")
        self._frameOffset=1
        self._demuxOffset=1.5 #mpeg step seek
        
    def togglePlay(self):
        if self.mediaPlayer is None:
            return False
        if self.mediaPlayer.eof_reached:
            return False
        
        playing = self.mediaPlayer.pause #property
        if playing:
            self.mediaPlayer.audio="auto"
            self.mediaPlayer["mute"]="no" #option
        else:
            self.mediaPlayer["mute"]="yes"
            self.mediaPlayer.audio="no"
        self.mediaPlayer.pause=not playing
        return playing        
 
    def mpvVersion(self):
        return self.mediaPlayer.mpv_version
 
    #relevant if we reach end while playing
    def syncPlay(self,func):
        self.play_func=func
        
    def syncToStart(self):
        self.seek(0)
        self._onTimePos("timepos", self.timePos())

class MpvPlugin():
    def __init__(self,iconSize):
        self.mpvWidget=None
        self.player=None
        self.iconSize=iconSize
        self.controller=None #VCControl
        self.sliderThread=SliderThread(self.onSeek)
        
    def initPlayer(self,filePath, streamData):
        locale.setlocale(locale.LC_NUMERIC, 'C')
        self.__setupPlayer()
        
        #check stream data for exact one video stream
        self.player.open(filePath)    
        if not self.player.isReadable:
            raise Exception("Invalid file")
        self._sanityCheck(streamData)
        self.player.syncPlay(self.markStopPlay)
        return self.player

    def validate(self):
        if self.player:
            return self.player.validate()
        raise Exception('Invalid file')       
    
    def closePlayer(self):
        pass
        
    def shutDown(self):
        self.sliderThread.stop()
    
    def createWidget(self,showGL,parent):
        self.showGL=showGL;
        if showGL:
            Log.logInfo("create GL Widget")
            return self._createGLWidget(parent)
        Log.logInfo("create X11 Widget")
        return self._createPlainwidget(parent)
    
    def _createPlainwidget(self,parent):
        self.mpvWidget=VideoWidget(parent)
        self.mpvWidget.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.mpvWidget.setAttribute(Qt.WA_NativeWindow)
        return self.mpvWidget        
    
    def _createGLWidget(self,parent):
        self.player= MpvPlayer()
        mpv=self.player.initGLPlayer()    
        self.mpvWidget=VideoGLWidget(parent,mpv)
        self.player.connectTo(self.mpvWidget.updateUI)
        return self.mpvWidget
    
    def __setupPlayer(self):
        if self.showGL:
            return #already happened
        if self.player:
            self.player.close()
        self.player= MpvPlayer()
        self.player.initPlayer(self.mpvWidget)
        self.player.connectTo(self.mpvWidget.updateUI)
    
    def videoWidget(self):
        return self.mpvWidget
    
    def setCutEntry(self,cutEntry,restore=False): #this is a cv restore hack
        if restore: #legacy: create a pix from old entry 
            cutEntry.frameNumber=cutEntry.frameNumber-1 #cv compensation
            pilImage = self.player.screenshotAtFrame(cutEntry.frameNumber)
        else: #create a new one
            pilImage = self.player.screenshotImage()

            #set: cutEntry.frameNumber=self.player.getCurrentFrameNumber()    
        cutEntry.timePosMS=self.player.timePos()*1000 #Beware +1!
        cutEntry.pix = self._makeThumbnail(pilImage)
    
    def info(self):
        data={}
        if self.player is not None:
            data["Mpv version"] = self.player.mpvVersion()
            data["Mpv dur"]=str(self.player.duration)
        return data
    
    def _makeThumbnail(self,qImage):
        pix = QtGui.QPixmap.fromImage(qImage)
        pix = pix.scaledToWidth(self.iconSize, mode=Qt.SmoothTransformation)
        return pix       

    def _sanityCheck(self,streamData):
        if streamData is None:
            return
        duration = streamData.formatInfo.getDuration()
        videoInfo = streamData.getVideoStream()               
        ff_fps= videoInfo.frameRateMultiple()
        ff_FrameCount = round(ff_fps*duration)
        isUHD = float(videoInfo.getWidth())>3000.0
        interlaced = videoInfo.isInterlaced()
        frameCount= self.player.framecount
        if not frameCount:
            frameCount=0
        fps=self.player.fps
        if not fps:
            fps=1.0
        #rot = streamData.getRotation()
        #ratio = streamData.getAspectRatio()
        Log.logInfo("Analyze MPV frameCount:%d fps:%.3f /FFMPEG frameCount:%d fps:%.3f, interlaced:%d"%(frameCount,fps,ff_FrameCount,ff_fps,interlaced))   
        
        fps_check= abs(self._secureDiv(self.player.fps,ff_fps)-1)
        #if fps_check >0.1:
        Log.logInfo("Setting FPS into MPV, ratio: %.3f setting fps %.3f"%(fps_check,ff_fps))
        self.player.setFPS(ff_fps)
            
        fcCheck= self._secureDiv(self.player.framecount,ff_FrameCount)
        if fcCheck < 0.9 or fcCheck > 1.1:
            Log.logInfo("Irregular count, ratio: %.3f, setting framecount %d"%(fcCheck,ff_FrameCount))
            self.player.framecount=max(1,ff_FrameCount)    
            
        #Transport stream handling:
        if streamData.isTransportStream():
            self.player.tweakTansportStreamSettings(interlaced)  
        if isUHD:
            self.player.tweakUHD() 
        if streamData.isVC1():
            self.player.tweakVC1()  
        if streamData.isMPEG2():
            self.player.tweakMPG()                        

    def _secureDiv(self,nominator,denominator):
        return nominator / denominator if denominator else 0

    def showBanner(self):
        self.initPlayer("icons/film-clapper.png",None)
        #self._showPos()
        
    def showFirstFrame(self):
        self.player.syncToStart()
        #self._showPos()

    #slider    
    def enqueueFrame(self,frameNumber): #Slider stuff
        self.sliderThread.seekTo(frameNumber)

    #spinbutton +cutEntry   
    def setFrameDirect(self,frameNumber):
        self.player.seek(frameNumber) #direct in Main thread
        delta = int(frameNumber-self.player.getCurrentFrameNumber())
        if delta != 0:
            self.player.seekStep(delta)
        #self.sliderThread.seekTo(int(frameNumber)) #pass it to slider thread
        
    #dial
    def onDial(self,pos):
        self.player.seekStep(pos)
        #self._showPos()

    def onSeek(self,frameNumber):
        if self.player:
            #no demux offset on fast seek
            self.player.seek(frameNumber,fast=True) 
        #return self.player.getCurrentFrameNumber()

    def toggleVideoPlay(self):
        if self.player is None:
            return False
        return self.player.togglePlay()
    
    def changeSettings(self,key,value):
        if self.player is not None:
            self.player.changeSettings(key,value)                
    
    def markStopPlay(self,boolval):
        #MPVEventHandlerThread-pass it over to the main thread.
        #correct: self.mpvWidget.triggerPlayerControls(boolval)
        self.controller.syncVideoPlayerControls(boolval)
        
    def hasVideoOffset(self):
        return False #hook for remux5 zeroTime

#takes the requests and only sends the actual framenumber to the player - makes the slider faster and the queue lighter        
class SliderThread(QtCore.QThread):
    def __init__(self,func):
        QtCore.QThread.__init__(self)
        self.delay=0
        self.condition = QtCore.QWaitCondition()
        self.mutex = QtCore.QMutex()
        self.func=func #function will be executed here, not in main thread
        self.pos=0
        #self.current=0
        self.__running=True
        self.start()
        
    def run(self):
        while self.__running:
            curr=-1
            while self.pos != curr:
                curr=self.pos
                self.func(self.pos)

            self.__wait() #wait until needed
    
    def __wait(self):
        self.mutex.lock()
        self.condition.wait(self.mutex)
        self.mutex.unlock()
    
    def stop(self):
        self.__running=False
        self.condition.wakeOne()
    
    def seekTo(self,fn):
        self.pos = fn
        self.condition.wakeOne()#wake up the long wait
        
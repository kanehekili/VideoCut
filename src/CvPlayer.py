'''
Created on Dec 10, 2021
Opencv related stuff
@author: kanehekili
'''

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import pyqtSignal
from PyQt5 import QtWidgets,QtGui,QtCore
import sys
from datetime import timedelta
import FFMPEGTools

try:
    import cv2  # cv3
    cvmode = 3
    CV_VERSION =  int(cv2.__version__.replace('.',''))
    # print (cv2.getBuildInformation())
except ImportError:
    print (("OpenCV 3 not found,, expecting Version 2 now"))
    try:
        from cv2 import cv  # this is cv2!
        cvmode = 2
        CV_VERSION =  int(cv.__version__.replace('.',''))
    except ImportError:
        print (("OpenCV 2 not found"))  
        app = QApplication(sys.argv)
        QtWidgets.QMessageBox.critical(None, "OpenCV",
            ("Opencv2 or opencv3 must be installed to run VideoCut."))
        sys.exit(1)
        
'''
Compat layer for cv2 and 3
'''

Log=FFMPEGTools.Log

class OpenCV2():

    def __init__(self,):
        self._cap = cv2.VideoCapture()
        
    def getCapture(self):
        return self._cap
        
    def setColor(self, numpyArray):
        cv2.cvtColor(numpyArray, cv.CV_BGR2RGB, numpyArray)  # @UndefinedVariable
        
    def getFrameWidth(self):
        return self._cap.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH)  # @UndefinedVariable
     
    def getFrameHeight(self):
        return self._cap.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT)  # @UndefinedVariable
    
    def getFrameCount(self):
        return self._cap.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT)  # @UndefinedVariable
    
    def getFPS(self):
        return self._cap.get(cv2.cv.CV_CAP_PROP_FPS)  # @UndefinedVariable
    
    def setFramePosition(self, pos):
        self._cap.set(cv2.cv.CV_CAP_PROP_POS_FRAMES, pos)  # @UndefinedVariable
    
    def getFramePosition(self):
        return self._cap.get(cv2.cv.CV_CAP_PROP_POS_FRAMES)  # @UndefinedVariable
        
    def setAVIPosition(self, pos):
        self._cap.set(cv2.cv.CV_CAP_PROP_POS_AVI_RATIO, pos)  # @UndefinedVariable
        
    def setTimePosition(self, ms):
        self._cap.set(cv2.cv.CV_CAP_PROP_POS_MSEC, ms)  # @UndefinedVariable
        
    def getTimePosition(self):
        return self._cap.get(cv2.cv.CV_CAP_PROP_POS_MSEC)  # @UndefinedVariable 
    
    def isOpened(self):
        return self._cap.isOpened()    
        

class OpenCV3():

    def __init__(self):
        self._cap = cv2.VideoCapture()
    
    def getCapture(self):
        return self._cap
    
    def setColor(self, numpyArray):
        cv2.cvtColor(numpyArray, cv2.COLOR_BGR2RGB, numpyArray)  # @UndefinedVariable
        
    def getFrameWidth(self):
        return self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)  # @UndefinedVariable
     
    def getFrameHeight(self):
        return self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)  # @UndefinedVariable
    
    def getFrameCount(self):
        return self._cap.get(cv2.CAP_PROP_FRAME_COUNT)  # @UndefinedVariable
    
    def getFPS(self):
        return self._cap.get(cv2.CAP_PROP_FPS)  # @UndefinedVariable
    
    def setFramePosition(self, pos):
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, pos)  # @UndefinedVariable
    
    def getFramePosition(self):
        return self._cap.get(cv2.CAP_PROP_POS_FRAMES)  # @UndefinedVariable
        
    def setAVIPosition(self, pos):
        self._cap.set(cv2.CAP_PROP_POS_AVI_RATIO, pos)  # @UndefinedVariable
        
    def setTimePosition(self, ms):
        self._cap.set(cv2.CAP_PROP_POS_MSEC, ms)  # @UndefinedVariable
        
    def getTimePosition(self):
        return self._cap.get(cv2.CAP_PROP_POS_MSEC)  # @UndefinedVariable
    
    def isOpened(self):
        return self._cap.isOpened() 

    
if cvmode == 3:
    OPENCV = OpenCV3()
    print ("using CV3")
    cvInfo = FFMPEGTools.parseCVInfos(cv2.getBuildInformation());
    cvInfo["CV_Version"] = 'CV3'
else:
    OPENCV = OpenCV2()
    print ("using CV2")
    cvInfo = FFMPEGTools.parseCVInfos(cv2.getBuildInformation());  
    cvInfo["CV_Version"] = 'CV2'    
    
class CVImage(QtGui.QImage):
    ROTATION = 0

    def __init__(self, numpyArray):
        height, width, bytesPerComponent = numpyArray.shape
        cvrotate = self.getRotation()
        if cvrotate < 1:
            dst = numpyArray
        else:
            dst = cv2.rotate(numpyArray, cvrotate)
            height, width, bytesPerComponent = dst.shape
         
        bytesPerLine = bytesPerComponent * width
            
        OPENCV.setColor(dst)
        super(CVImage, self).__init__(dst.data, width, height, bytesPerLine, QtGui.QImage.Format_RGB888)
    
    def getRotation(self):
        #seems to be fixed in opencv 4.5... 
        return self.ROTATION;


class VideoWidget(QtWidgets.QFrame):
    """ A class for rendering video coming from OpenCV """
    trigger = pyqtSignal(float,float,float)
    
    def __init__(self, parent):
        QtWidgets.QFrame.__init__(self, parent)
        self._defaultHeight = 576
        self._defaultWidth = 720
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self._image = None
        self.imageRatio = 16.0 / 9.0
        self.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Sunken)
        self.setLineWidth(1)

    def paintEvent(self, event):

        QtWidgets.QFrame.paintEvent(self, event)
        if self._image is None:
            return

        qSize = self.size()
        w = qSize.width()
        h = qSize.height()
        imgY = w / self.imageRatio
        if imgY > h:
            imgY = h
            imgX = self.imageRatio * h
            x = (w - imgX) / 2;
            y = 0
        else:
            imgX = w;
            x = 0
            y = (h - imgY) / 2
        
        painter = QtGui.QPainter(self)
        painter.drawImage(QtCore.QRectF(x, y, imgX, imgY), self._image)
        # painter.end()
        
    def sizeHint(self):
        return QtCore.QSize(self._defaultWidth, self._defaultHeight)

    def showFrame(self, aFrame):
        if aFrame is None:  # showing an error icon...
            with open('icons/film-clapper.png', 'rb') as filedata:
                contents = filedata.read();
                self._image = QtGui.QImage()
                self._image.loadFromData(contents, format=None)
                box = self._image.rect()
                self.imageRatio = box.width() / float(box.height())
        else:   
            self._image = CVImage(aFrame)
        self.update()
        
    def setVideoGeometry(self, ratio, rotation):
        if rotation > 0:
            self.imageRatio = 1.0 / float(ratio)
        else:
            self.imageRatio = float(ratio)       
    
    def updateUI(self,frameNumber,framecount,timeinfo):
        self.trigger.emit(frameNumber,framecount,timeinfo)
        
                    
class VideoPlayerCV():

    def __init__(self, path, streamProbe, rotation):
        self.framecount = 0
        self.totalTimeMilliSeconds = 0.0 
        self._streamProbe = streamProbe
        self._capture = None
        self._file = str(path)
        self._isValid = self._captureFromFile(rotation)
        self.currentFrame=None
        
    def _captureFromFile(self, rotation):
        if not self._sanityCheck():
            return False
        self._capture = OPENCV.getCapture();
        if not self._capture.open(self._file):
            Log.logError("STREAM NOT OPENED")
            return False

        self.frameWidth = OPENCV.getFrameWidth()
        self.frameHeight = OPENCV.getFrameHeight()
        self.framecount = round(OPENCV.getFrameCount())
        self.fps = OPENCV.getFPS()
        
        #ffmpeg
        duration = self._streamProbe.formatInfo.getDuration()
        ff_fps= self._streamProbe.getVideoStream().frameRateMultiple()
        ff_FrameCount = round(ff_fps*duration)
        Log.logInfo("Analyze %s frameCount:%d fps:%.3f ffmpeg frameCount:%d fps:%.3f"%(self._file,self.framecount,self.fps,ff_FrameCount,ff_fps))   
        fps_check= (self.fps/ff_fps)
        if abs(fps_check -1.0)>10.0:
            Log.logInfo("Irregular data, ratio: %.3f"%(fps_check))
            self.framecount=ff_FrameCount
            self.fps=ff_fps 
        
        # The problem: cv has a problem if it is BEHIND the last frame...
        # DO NOT USE>> cap.set(cv2.cv.CV_CAP_PROP_POS_AVI_RATIO,1);
        self.__setup(rotation)
        
        if self.framecount == 0:
            self.totalTimeMilliSeconds = duration*1000
        else:
            self.totalTimeMilliSeconds = int(self.framecount / self.fps * 1000)
        
        return True

    def _sanityCheck(self):
        if self._streamProbe is None or not self._streamProbe.isKnownVideoFormat():
            print ("STREAM NOT KNOWN")
            Log.logInfo("STREAM NOT KNOWN")
            return False
        
        if len(self._streamProbe.video)!=1:
            print("Zero or more than 1 video stream")
            Log.logInfo("Zero or more than 1 video stream")
            return False
        
        return True

    #setup, may not take too long. GUI not accessible yet. 
    def __setup(self, rotation):
        OPENCV.setFramePosition(0)
        ret, frame = self._capture.read()
        if ret:
            CVImage.ROTATION = self.__getRotation(rotation)
            self.currentFrame=frame
        OPENCV.setFramePosition(0) 
    
    
    def __getRotation(self, rotation):
        if CV_VERSION > 450: #seems to be fixed with 4.5.0
            return 0
        if rotation > 0 and rotation < 180:
            return cv2.ROTATE_90_CLOCKWISE
        if rotation > 180:
            return cv2.ROTATE_90_COUNTERCLOCKWISE
        if rotation == 180:
            return cv2.ROTATE_180;
        return 0;
    
    def validate(self):
        if not self.isValid():
            raise Exception('Invalid file')

    def isValid(self):
        return self._isValid 

    def getNextFrame(self):
        if not self.isValid():
            return None

        ret, frame = self._capture.read()
        if ret:
            self.currentFrame=frame
            return frame
 
        self.framecount = self.getCurrentFrameNumber()
        Log.logInfo("No more frames @" + str(self.framecount + 1));
        return self.__getLastFrame(self.framecount, 0)

    # A test to paint on a frame. Has artefacts..
    def __markFrame(self, frame, nbr):
        cv2.putText(frame, "FB: {}".format(nbr),
        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)    

    def __getLastFrame(self, frameIndex, retries):
        if frameIndex < 1 or retries > 8:
            return None
        OPENCV.setFramePosition(frameIndex - 1)
        ret, frame = self._capture.read()
        if not ret:
            return self.__getLastFrame(frameIndex - 1, retries + 1)
        self.currentFrame=frame
        return frame    

    def getCurrentFrame(self):
        if self.currentFrame is None:
            return self.getFrameAt(1)
        return self.currentFrame
            

    def getPreviousFrame(self):
        framepos = self.getCurrentFrameNumber()
        if framepos > 0:
            framepos -= 1
        return self.getFrameAt(framepos)

    '''
    0-based index of the frame to be decoded/captured next.
    '''     

    def setFrameAt(self, frameNumber):
        OPENCV.setFramePosition(frameNumber)
   
    def getFrameAt(self, frameNumber):
        try:
            self.setFrameAt(frameNumber)
            return self.getNextFrame()
        except: 
            Log.logException("Error Frame")
            return None
    
    def getCurrentFrameNumber(self):
        return OPENCV.getFramePosition()-1 #cv is always behind!

    '''
    seeks a frame based on AV pos (between 0 and 1) -SLOW!!!!!
    '''

    def getFrameAtAVPos(self, avPos):
        OPENCV.setAVIPosition(avPos)
        return self.getNextFrame()
 
    def getFrameAtMS(self, ms):
        OPENCV.setTimePosition(ms)
        return self.getNextFrame()
 
    def getFrameSize(self):
        return QtCore.QSize(self.frameWidth, self.frameHeight)
    
    def getCurrentFrameTime(self):
        if not self.isValid():
            timeSlot = 0
        else:
            timeSlot = self.getCurrentTimeMS()

        try:    
            td = timedelta(milliseconds=timeSlot)
        except:
            td = timedelta.max
        return td

    # Current position of the video file in milliseconds. 
    def getCurrentTimeMS(self):
        #more precise & reliable than OPENCV.getTimePosition()
        #fpos = self.getCurrentFrameNumber();
        #ct = fpos/self.fps*1000
        #return max(ct,0.0)
        return OPENCV.getTimePosition()


    def takeScreenShot(self,path):
        if self.currentFrame is None:
            return False
        cv2.imwrite(path,cv2.cvtColor(self.currentFrame, cv2.COLOR_RGB2BGR))
        return True

    def close(self):
        if self._capture is not None:
            self._capture.release()


class CvPlugin():
    
    def __init__(self,iconSize):
        self.cvWidget=None
        self.player=None
        self.iconSize=iconSize
        self.sliderThread=None #QT slider thread
        self.controller=None #VCControl
        self._vPlayer=None   #Video player timer thread
    
    def initPlayer(self,filePath, streamData):
        if self.player:
            self.player.close()
            
        rot = streamData.getRotation()
        ratio = streamData.getAspectRatio()
        self.player=VideoPlayerCV(filePath, streamData, rot)
        self.cvWidget.setVideoGeometry(ratio, rot)
        self._initSliderThread()
        self.player.validate()
        return self.player
    
    def closePlayer(self):
        if self.player:
            self.player.close()
        self.player=None        
   
    def changeSettings(self,key,value):
        pass
    
    def shutDown(self):
        self.closePlayer()
        #TODO: terminate slider thread when fixed

    def validate(self):
        if self.player:
            return self.player.validate()
        raise Exception("Invalid medium")
    
    def createWidget(self,useGL,parent):
        self.cvWidget=VideoWidget(parent)
        return self.cvWidget
    
    #unused
    def videoWidget(self):
        return self.cvWidget
        
    
    #TODO based on time, not frame...        
    def setCutEntry(self,cutEntry,restore=False): #this is a cv restore hack
        frameNumber = cutEntry.frameNumber
        if restore:
            frameNumber=frameNumber-1; #legacy bug
            cutEntry.frameNumber=frameNumber
        self.player.setFrameAt(frameNumber)
        frame = self.player.getNextFrame()
        framePos = self.player.getCurrentFrameNumber()
        #timePosMS = self.player.getCurrentFrameTime()
        timePosSecs= self.player.getCurrentTimeMS()
        #cutEntry = VideoCutEntry(framePos, timePosMS, mode,pix)
        cutEntry.timePosMS=timePosSecs
        if cutEntry.pix is None:
            img = CVImage(frame.copy()).scaled(int(self.cvWidget.imageRatio * self.iconSize), self.iconSize)
            pix = QtGui.QPixmap.fromImage(img)
            cutEntry.pix=pix

    def showBanner(self):
        self.cvWidget.showFrame(None)
    
    def info(self):
        return cvInfo
    
    def _initSliderThread(self):
        if self.sliderThread is not None:
            self.sliderThread.stop
            self.sliderThread.quit()
            self.sliderThread.wait()
            self.sliderThread.deleteLater()
            #sleep(0.1)

        #TODO delegate worker to CV... 
        self.sliderThread = SliderThread(self.player.getFrameAt)
        self.sliderThread.signal.connect(self._processFrame)
    
    def _processFrame(self):
        self._showFrame(self.sliderThread.result)
    
    def _showFrame(self, aFrame):
        self.cvWidget.showFrame(aFrame)
        self._triggerCurrentFrameInfo()
    
    def showFirstFrame(self):
        self._grabNextFrame()
    
    def _grabNextFrame(self):
        frame = self.player.getNextFrame()
        if frame is not None:
            self.cvWidget.showFrame(frame)
            
            frameNumber = self._triggerCurrentFrameInfo()
            
            if self.player.framecount == frameNumber:
                self.__stopVideo()
                #callback to controller
                self.controller.syncVideoPlayerControls(False)
        else:
            #callback to controller
            self.controller.syncVideoPlayerControls(False)
            self.player.framecount = self.player.getCurrentFrameNumber()
            self.__stopVideo()      
    
    def _triggerCurrentFrameInfo(self):
        frameNumber = self.player.getCurrentFrameNumber()
        timeinfo = self.player.getCurrentTimeMS()
        self.cvWidget.updateUI(frameNumber,self.player.framecount,timeinfo)
        return frameNumber

    def enqueueFrame(self,fn): #This is a threaded frame via slider thread..should be "showFrame"
        self.sliderThread.showFrame(fn)
        
    #spinbutton    
    def setFrameDirect(self,fn):
        self.sliderThread.showFrame(fn)        

    def onDial(self,dialStep):
        self.sliderThread.wait()  # No concurrency with worker!
        frameNumber = max(0, self.player.getCurrentFrameNumber() + dialStep);
        aFrame = self.player.getFrameAt(frameNumber)
        self._showFrame(aFrame)

    def toggleVideoPlay(self):
        if self._vPlayer is None:
            return self.__playVideo()
        
        return self.__stopVideo()

    def __playVideo(self):
        self._vPlayer = QtCore.QTimer(None)
        self._vPlayer.timeout.connect(self._grabNextFrame)
        # 50 ms if 25 fps and 25 if 50fps
        fRate = (1 / self.player.fps) * 1250
        self._vPlayer.start(round(fRate))
        return True

    def __stopVideo(self):
        if self._vPlayer is not None:
            self._vPlayer.stop()
            self._vPlayer = None
        return False

    def hasVideoOffset(self):
        return True #hook for remux5 zeroTime
    '''
    callbacks
     self.controller.syncVideoPlayerControls(isplaying)

    events:
      videoWidget.trigger (signal(flaot,flaot,float))

    POTENTIAL PLAYER api
    CVPlayer:
    self.player.framecount
    self.player.fps
    
    self.player = VideoPlugin.initPlayer(filePath, self.streamData, rot)
    pos=self.player.getCurrentFrameNumber()
    self.player.isValid()
    boolean= self.player.takeScreenShot(path):
    
    VideoPlugin:
    VideoPlugin.createWidget(self,self.SLIDER_RESOLUTION) ?ICO_SIZE?
    VideoPlugin.showBanner() #clapper zeigen
    self.player = VideoPlugin.initPlayer(filePath, self.streamData, rot)
    
    VideoPlugin.controller=self
    VideoPlugin.setCutEntry(cutEntry,restore=True)
    VideoPlugin.showFirstFrame()
    VideoPlugin.enqueueFrame(frameNumber)
    sliderPos = VideoPlugin.onDial(self._dialStep)
    isPlaying = VideoPlugin.toggleVideoPlay()  
    '''
class SliderThread(QtCore.QThread):
    signal = pyqtSignal()
    result = None
    stop = False

    def __init__(self, func):
        QtCore.QThread.__init__(self)
        self.func = func
        self.fbnr = 0

    def run(self):
        current = -1;
        #QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        while self.fbnr != current:
            current = self.fbnr
            self.result = self.func(current)
            self.signal.emit()
        #QApplication.restoreOverrideCursor()
           

    def showFrame(self, frameNumber):
        self.fbnr = frameNumber
        if not self.stop:
            self.start()        
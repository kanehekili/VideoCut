# -*- coding: utf-8 -*-

# 2014 Matze Wegmann (mat.wegmann@gmail.com)
#



import cv2
from cv2 import cv
import sys
from datetime import timedelta

from PyQt4 import QtGui,QtCore
from PyQt4.QtCore import QTimer, QObject
from PyQt4.QtGui import QApplication, QImage, QPainter, QWidget, QVBoxLayout,\
    QDesktopWidget, QFileDialog, QDial, QColor, QSizePolicy, QLabel,\
    QHBoxLayout, QListWidget, QGridLayout, QListWidgetItem,\
    QIcon, QMenu, QFrame
from PyQt4.Qt import QRectF, QSize, QString, Qt, QStatusBar
from FFMPEGTools import FFMPEGCutter, FFStreamProbe
import os
from time import sleep
#import MProfiler


# sizes ..
SIZE_ICON=80


def changeBackgroundColor(widget, colorString):
    widget.setAttribute(QtCore.Qt.WA_StyledBackground, True)
    style = "background-color: %s;" % colorString
    widget.setStyleSheet(style)

def getAppIcon():
    return QtGui.QIcon('icons/movie-icon.png')
    

def timedeltaToString(deltaTime):
    s = deltaTime.seconds
    hours, remainder = divmod(s, 3600)
    minutes, seconds = divmod(remainder, 60)
    return '%s:%s:%s' % (hours, minutes, seconds)

class OSTools():
    
    def getPathWithoutExtension(self,aPath):
        if aPath:
            rawPath = os.path.splitext(str(aPath))[0]
        else:
            rawPath=""
        return rawPath

    def getWorkingDirectory(self):
        abspath = os.path.abspath(__file__)
        dname = os.path.dirname(abspath)
        return dname               

    def setCurrentWorkingDirectory(self):
        print "DIR:",self.getWorkingDirectory()
        os.chdir(self.getWorkingDirectory())


class CVImage(QImage):
    def __init__(self,numpyArray):
        height, width, bytesPerComponent = numpyArray.shape
        bytesPerLine = bytesPerComponent * width;
        cv2.cvtColor(numpyArray, cv.CV_BGR2RGB, numpyArray)
        super(CVImage,self).__init__(numpyArray.data,width,height,bytesPerLine, QImage.Format_RGB888)


class VideoWidget(QFrame):
    """ A class for rendering video coming from OpenCV """

    def __init__(self, parent=None):
        QFrame.__init__(self,parent)
        self._defaultHeight=576
        self._defaultWidth=720
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        changeBackgroundColor(self, "lightgray")       
        self._image = None
        self.setDefaultRatio()
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.setLineWidth(1)
        #self.setMidLineWidth(2)


    def paintEvent(self, event):
        QFrame.paintEvent(self,event)
        painter = QPainter(self)
        if self._image is None:
            return
        
        qSize = self.size()
        w= qSize.width()
        h= qSize.height()
        imgY= w/self.imageRatio
        if imgY > h:
            imgY=h
            imgX= self.imageRatio*h
            x= (w-imgX)/2;
            y=0
        else:
            imgX = w;
            x=0
            y=(h-imgY)/2
        painter.drawImage(QRectF(x, y,imgX,imgY), self._image)        
        
    def sizeHint(self):
        return QSize(self._defaultWidth,self._defaultHeight)

    def showFrame(self,aFrame):
        if aFrame is None:  #showing an error icon...
            with open('icons/video_clapper.png','rb') as filedata:
                contents = filedata.read();
                self._image = QtGui.QImage()
                self._image.loadFromData(contents, format=None)
                box = self._image.rect()
                self.imageRatio=box.width()/float(box.height())
        else:    
            self.setDefaultRatio()
            self._image = CVImage(aFrame)
        self.update()
        
        
    def setDefaultRatio(self):
        self.imageRatio = 16.0/9.0; #Pixel aspect ratio is not considered yet!
        

class VideoCutEntry():
    MODE_START = "Start"
    MODE_STOP = "Stop"
    def __init__(self,frameNbr,timepos,markerType):
        self.frameNumber=frameNbr;
        self.modeString = markerType
        self.timePos = timepos
        
    def isStartMode(self):
        return self.MODE_START==self.modeString    
    
    def getTimeString(self):
        return ':'.join(str(self.timePos).split(':')[:3])
    

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

        
#widget that contains the widgets
class LayoutWindow(QWidget):
    SLIDER_RESOLUTION = 1000
    DIAL_RESOLUTION = 50 
    def __init__(self,parent=None):
        QWidget.__init__(self,parent)
        self.initWidgets()
        

    def initWidgets(self):
        
        self.ui_VideoFrame = VideoWidget()
        self.ui_Slider =  QtGui.QSlider(QtCore.Qt.Horizontal)
        self.ui_Slider.setMinimum(0)
        self.ui_Slider.setMaximum(self.SLIDER_RESOLUTION)
        #self.ui_Slider.setTickPosition(Qt.TicksAbove)
        
        self.ui_Dial = QDial(self)
        self.ui_Dial.setProperty("value", 0)
        self.ui_Dial.setNotchesVisible(True)
        self.ui_Dial.setWrapping(False)
        self.ui_Dial.setNotchTarget(5.0)
        self.setDialResolution(self.DIAL_RESOLUTION)

        self.ui_InfoLabel = QLabel()
        changeBackgroundColor(self.ui_InfoLabel , "lightblue")
        self.ui_InfoLabel.setText("Info:")
        
        self.ui_List = self.__createListWidget()
        
        #self._listSplitter = QSplitter() ->add as widget...+QVBoxLayout
        #self._listSplitter.addWidget(iconList)
        
        #status bar
        self.statusbar = QStatusBar(self)
        self.statusbar.setSizeGripEnabled(True)
        self.statusbar.showMessage("Idle")
        self.statusbar.addPermanentWidget(self.__createProgressBar())
        self.setLayout(self.makeGridLayout())
        self.adjustSize()
        #changeBackgroundColor(mainVBox, "yellow")

    def makeGridLayout(self):
        layout = QGridLayout()
        self.ui_List.setSizePolicy(QSizePolicy.Minimum,QSizePolicy.Expanding)
        layout.addWidget(self.ui_List,0,0,5,1)
        #layout.addWidget(self._listSplitter,0,0,5,1)
        layout.addWidget(self.ui_VideoFrame,0,2,3,-1);
        layout.addWidget(self.ui_InfoLabel,4,1,1,-1)
        layout.addWidget(self.ui_Slider,5,0,1,120)
        layout.addWidget(self.ui_Dial,5,121)
        layout.addWidget(self.statusbar,6,0,1,122)

        return layout
                                                  
                         

    def makeBoxLayout(self):
        vbox = QVBoxLayout()
        vbox.addWidget(self.ui_VideoFrame)
        vbox.addWidget(self.ui_InfoLabel );
        
        slidehbox = QHBoxLayout()
        slidehbox.addWidget(self.ui_Slider)
        slidehbox.addWidget(self.ui_Dial)

        midHBox = QHBoxLayout()
        midHBox.addWidget(self.ui_List)
        self.ui_List.setSizePolicy(QSizePolicy.Minimum,QSizePolicy.Expanding)
        midHBox.addLayout(vbox)
        
        mainVBox = QVBoxLayout()
        mainVBox.addLayout(midHBox)
        mainVBox.addStretch(1)
        mainVBox.addLayout(slidehbox)
        return mainVBox
    
    def showInfo(self,text):
        self.ui_InfoLabel.setText(text)
    
    def setDialResolution(self,resolution):
        self.ui_Dial.setMinimum(-resolution/2)
        self.ui_Dial.setMaximum(resolution/2)


    def syncSliderPos(self,pos):
        self.ui_Slider.setSliderPosition(pos)
    
    def clearVideoFrame(self):
        self.ui_VideoFrame.showFrame(None)
 
    ### Marks 
    def addCutMark(self,frame,cutEntry,rowIndex):
        item = QListWidgetItem()
        img = CVImage(frame).scaled(self.ui_VideoFrame.imageRatio*SIZE_ICON, SIZE_ICON)
        pix = QtGui.QPixmap.fromImage(img)
        item.setIcon(QIcon(pix))
        if cutEntry.isStartMode():
            item.setBackgroundColor(QColor(224,255,224))
        else:
            item.setBackgroundColor(QColor(255,224,224))

        self.ui_List.insertItem(rowIndex,item)
        text = "%s <br> F: %s<br> T: %s" %(cutEntry.modeString,str(cutEntry.frameNumber),str(cutEntry.getTimeString()))
        marker = QLabel(text)
        marker.setWordWrap(True)
        marker.layout()
        self.ui_List.setItemWidget(item,marker)
        self.ui_List.setIconSize(QSize(SIZE_ICON,SIZE_ICON)) #Forces an update!
        self.ui_List.setCurrentItem(item)
        
 
    def hookEvents(self,aVideoController):
        self.__videoController=aVideoController #for menu callbacks
        self.ui_Slider.valueChanged.connect(aVideoController.sliderMoved)
        
        self.ui_Dial.valueChanged.connect(aVideoController.dialChanged)
        self.ui_Dial.sliderReleased.connect(self.__resetDial)
        self._hookListActions()
    
    def keyReleaseEvent(self,event):
        self.__resetDial()
     
    def _hookListActions(self):
        #TOO bad-the list model -should be here... 
        rmAction = QtGui.QAction(QtGui.QIcon('icons/close-x.png'), 'Delete', self)
        rmAction.triggered.connect(self._removeMarker)
        rmAllAction = QtGui.QAction(QtGui.QIcon('icons/clear-all.png'), 'Remove all', self)
        rmAllAction.triggered.connect(self.clearMarker)
        gotoAction = QtGui.QAction(QtGui.QIcon('icons/go-next.png'), 'Goto', self)
        gotoAction.triggered.connect(self._gotoFromMarker)
  
        #menus      
        self.ui_List.customContextMenuRequested.connect(self._openListMenu)
        self._listMenu = QMenu()
        self._listMenu.addAction(rmAction)
        self._listMenu.addAction(rmAllAction)
        self._listMenu.addAction(gotoAction)
        
 
    def __resetDial(self):
        self.ui_Dial.setProperty("value", 0)

    def __createProgressBar(self):
        self.progressBar = QtGui.QProgressBar(self)
        #self.progressBar.setRange(0,1)
        #self.progressBar.setValue(-1)
        #self.progressBar.reset()
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximumWidth(150)
        self.progressBar.setVisible(False)
        return self.progressBar
    
    def showBusy(self):
        self.progressBar.setRange(0,0)
        self.progressBar.setVisible(True)
    
    def stopProgress(self):
        self.progressBar.setVisible(False)            

    def __createListWidget(self):
        iconList=QListWidget()
        iconList.setAlternatingRowColors(True)
        iconList.setContextMenuPolicy(Qt.CustomContextMenu)
        #iconList.setStyleSheet("QListWidget { background: red; } QListWidget::item { background: yellow; } QListWidget::item:selected { background: blue; }")
        iconList.setStyleSheet("QListWidget::item:selected:active { background: #28D9FF; color:#FFFFFF; } ")#that text color seems not to work!
        return iconList

    #---List widget context menu
    def _removeMarker(self,whatis):
        selectionList = self.ui_List.selectedIndexes()
        if len(selectionList)==0:
            return
        item = selectionList[0]
        self.ui_List.takeItem(item.row())
        self.__videoController.removeVideoCutIndex(item.row())
        
    def clearMarker(self):
        self.ui_List.clear()
        self.__videoController.removeVideoCuts()
        
    def _gotoFromMarker(self,whatis):
        selectionList = self.ui_List.selectedIndexes()
        if len(selectionList)==0:
            return
        item = selectionList[0]
        self.__videoController.gotoCutIndex(item.row())
        
        
    def _openListMenu(self,position):
        selectionList = self.ui_List.selectedIndexes()
        if len(selectionList)==0:
            return
        self._listMenu.exec_(self.ui_List.viewport().mapToGlobal(position)) 

        

class MainFrame(QtGui.QMainWindow):
    def __init__(self,aPath=None):
        super(MainFrame, self).__init__()
        self.setWindowIcon(getAppIcon())
        self._videoController = VideoControl(self)
        self._widgets = self.initUI()
        self._widgets.hookEvents(self._videoController)

        self.show() 
        if aPath is not None:
            self._videoController.setFile(aPath)

    
    def initUI(self):
        
        #self.statusBar().showMessage('Ready')
         
        self.exitAction = QtGui.QAction(QtGui.QIcon('icons/window-close.png'), 'Exit', self)
        self.exitAction.setShortcut('Ctrl+Q')
        self.exitAction.triggered.connect(QtGui.qApp.quit)
        
        self.loadAction = QtGui.QAction(QtGui.QIcon('./icons/loadfile.png'), 'Load Video', self)
        self.loadAction.setShortcut('Ctrl+L')
        self.loadAction.triggered.connect(self.loadFile)


        self.startAction = QtGui.QAction(QtGui.QIcon('./icons/start-icon.png'), 'Set start marker', self)
        self.startAction.setShortcut('Ctrl+G')
        self.startAction.triggered.connect(self._videoController.addStartMarker)

        self.stopAction = QtGui.QAction(QtGui.QIcon('./icons/stop-red-icon.png'), 'Set stop marker', self)
        self.stopAction.setShortcut('Ctrl+H')
        self.stopAction.triggered.connect(self._videoController.addStopMarker)
        
        self.saveAction= QtGui.QAction(QtGui.QIcon('./icons/save-as-icon.png'), 'Save the video', self)
        self.saveAction.setShortcut('Ctrl+S')
        self.saveAction.triggered.connect(self.saveVideo)
        
        self.infoAction = QtGui.QAction(QtGui.QIcon('./icons/info.png'), 'Codec info', self)
        self.infoAction.setShortcut('Ctrl+I')
        self.infoAction.triggered.connect(self.showCodecInfo)
        
        self.playAction = QtGui.QAction(QtGui.QIcon('./icons/play.png'), 'Play video', self)
        self.playAction.setShortcut('Ctrl+P')
        self.playAction.triggered.connect(self.playVideo)
        
        self.toolbar = self.addToolBar('Main')
        self.toolbar.addAction(self.loadAction)
        self.toolbar.addAction(self.startAction)
        self.toolbar.addAction(self.stopAction)
        self.toolbar.addAction(self.saveAction)
        self.toolbar.addAction(self.infoAction)
        self.toolbar.addAction(self.playAction)

        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(self.loadAction)
        fileMenu.addAction(self.startAction)
        fileMenu.addAction(self.stopAction)
        fileMenu.addAction(self.saveAction)
        fileMenu.addAction(self.exitAction)

        widgets = LayoutWindow()
        self.setCentralWidget(widgets);
        w = QDesktopWidget().width()
        h= QDesktopWidget().height()
        #self.setGeometry(w/2,h/2,700,550)
        self.setGeometry(w/4,h/4,700,550)
        
        self.setWindowTitle("VideoCut")   
        return widgets
     
    def showInfo(self,text):
        self._widgets.showInfo(text)


    def getVideoWidget(self):
        return self._widgets.ui_VideoFrame

    def syncSliderPos(self,pos):
        self._widgets.syncSliderPos(pos)

    def addCutMark(self,frame,cutEntry,rowIndex):
        self._widgets.addCutMark(frame,cutEntry,rowIndex)
        
    def showBusy(self):
        self._widgets.showBusy()
        
    def stopProgress(self):
        self._widgets.stopProgress()

    def showWarning(self,aMessage):
        QtGui.QMessageBox.warning(self,"Tsk Tsk",aMessage,QtGui.QMessageBox.Cancel, QtGui.QMessageBox.NoButton, QtGui.QMessageBox.NoButton)
    
    
    def enableControls(self,enable):
        self._widgets.ui_Dial.setEnabled(enable)
        self._widgets.ui_Slider.setEnabled(enable)
            
                            
    #-------- ACTIONS ----------
    def loadFile(self):
        initalPath = self._videoController.getTargetFile()
        result = QFileDialog.getOpenFileName(parent=self, directory=initalPath, caption=QString("Load Video"));
        if result:
            self._widgets.clearMarker()
            self._videoController.setFile(result)

    def saveVideo(self):
        initalPath = self._videoController.getTargetFile()
        result = QFileDialog.getSaveFileName(parent=self, directory=initalPath, caption=QString("Save Video"));
        if result:
            self._widgets.showBusy()
            self._videoController.saveVideo(result)
    
    def showCodecInfo(self):
        #TODO:
        QtGui.QMessageBox.information(self,"Video Info","Under construction",QtGui.QMessageBox.NoButton, QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)
        
    def playVideo(self):
        #TODO:
        
        
        self.playAction.setIcon(QtGui.QIcon('./icons/pause.png'))
        QtGui.QMessageBox.information(self,"Play video","Under construction",QtGui.QMessageBox.NoButton, QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)
        self.playAction.setIcon(QtGui.QIcon('./icons/play.png'))
                
    #-------- ACTIONS  END ----------    

class VideoPlayer():
    def __init__(self,path,streamProbe):
        #streamProbe.getPathName()
        self.framecount = 0
        self._file=str(path)
        self._streamProbe = streamProbe
        self._capture = self._captureFromFile()
        
        
    def _captureFromFile(self):
        if not self._streamProbe.isKnownVideoFormat():
            return None
        cap = cv2.VideoCapture()
        isValid = cap.open(self._file)
        if not isValid:
            return None
        self.frameWidth= cap.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH)
        self.frameHeight= cap.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT)
        self.framecount= cap.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT)
        self.fps= cap.get(cv2.cv.CV_CAP_PROP_FPS)
        
        #The problem: cv has a problem if it is BEHIND the last frame...
        #DO NOT USE;;;;; cap.set(cv2.cv.CV_CAP_PROP_POS_AVI_RATIO,1);
#         test = cap.set(cv2.cv.CV_CAP_PROP_POS_FRAMES,self.framecount-10)
#         self.totalTimeMilliSeconds = cap.get(cv2.cv.CV_CAP_PROP_POS_MSEC);
        if self.frameHeight< 10.0 or self.frameWidth < 10.0 or self.framecount < 10.0 or self.fps < 10.0:
            return None;

        #too slow: self.__checkMax(cap)
        self.totalTimeMilliSeconds = int(self.framecount/self.fps*1000)
        cap.set(cv2.cv.CV_CAP_PROP_POS_FRAMES,0)
        return cap

    def validate(self):
        if not self.isValid():
            raise Exception('Invalid file')

    def isValid(self):
        return self._capture is not None 

    def __checkMax(self,cap):
        testPos=self.framecount-self.framecount//100
        ret = True
        cap.set(cv2.cv.CV_CAP_PROP_POS_FRAMES,testPos)
        while ret:
            ret = cap.grab()
            testPos+=1
        self.framecount = testPos-1

    """Milliseconds per frame."""
    def mspf(self):
        return int(1000 // (self.fps or 25))

            
    def getNextFrame(self):
        if not self.isValid():
            return None
        
        ret, frame = self._capture.read()
        if ret:
            return frame

        self.framecount = self.getCurrentFrameNumber()
        print "No more frames @",self.framecount+1;
        return self.__getLastFrame(self._capture,self.framecount)

    def __getLastFrame(self,cap,frameIndex):
        if frameIndex<1:
            return None
        cap.set(cv2.cv.CV_CAP_PROP_POS_FRAMES,frameIndex-1)
        ret, frame = cap.read()
        if not ret:
            return self.__getLastFrame(cap,frameIndex-1)
        return frame    
           

    def getCurrentFrame(self):
        ret,frame = self._capture.retrieve()
        if ret:
            return frame;
        else: 
            return self.getFrameAt(1)

    def getPreviousFrame(self):
        framepos = self.getCurrentFrameNumber()
        if framepos > 0:
            framepos -=1
        return self.getFrameAt(framepos)
    
    def setFrameAt(self,frameNumber):
        self._capture.set(cv2.cv.CV_CAP_PROP_POS_FRAMES,frameNumber)    
    
    def getFrameAt(self,frameNumber):
        self._capture.set(cv2.cv.CV_CAP_PROP_POS_FRAMES,frameNumber-1)
        return self.getNextFrame()
    '''
    seeks a frame based on AV pos (between 0 and 1) -SLOW!!!!!
    '''
    def getFrameAtAVPos(self,avPos):
        self._capture.set(cv2.cv.CV_CAP_PROP_POS_AVI_RATIO,avPos)
        return self.getNextFrame()
 
    def getFrameAtMS(self,ms):
        self._capture.set(cv2.cv.CV_CAP_PROP_POS_MSEC,ms)
        return self.getNextFrame()
 
    def getFrameSize(self):
        return QSize(self.frameWidth,self.frameHeight)
    
    def getCurrentFrameTime(self):
        if not self.isValid():
            timeSlot=0
        else:    
            timeSlot = self._capture.get(cv2.cv.CV_CAP_PROP_POS_MSEC)
        td = timedelta(milliseconds=int(timeSlot))
        return td
    
    def getCurrentTimeMS(self):
        return self._capture.get(cv2.cv.CV_CAP_PROP_POS_MSEC)
    
    def getCurrentFrameNumber(self):
        return self._capture.get(cv2.cv.CV_CAP_PROP_POS_FRAMES)

    def close(self):
        if self._capture is not None:
            self._capture.release()
             
'''
  handles the events from the GUI, connecting to the VideoPlayer and the VideoWidget... 
'''        
class VideoControl(QObject):
    def __init__(self,mainFrame):
        super(VideoControl, self).__init__()
        self.player = None
        self.gui = mainFrame
        self._frameSet=False
        self._initTimer()
        self.videoCuts=[]
        self.currentPath = OSTools().getWorkingDirectory()#//TODO get a Video dir
        self.streamData = None

    def _initTimer(self):
        self._timer = QTimer(self.gui)
        self._timer.timeout.connect(self._displayAutoFrame)

    
    def getTargetFile(self):
        if self.streamData is not None:
            return self.currentPath+"."+self.streamData.getTargetExtension()

        return self.currentPath
        
    #-- Menu handling ---    
    def setFile(self,filePath):
        if self.player is not None:
            self.player.close()
            self.videoCuts=[]
        
        self.streamData = FFStreamProbe(filePath)
        
        self.currentPath = OSTools().getPathWithoutExtension(filePath);
        try:            
            self.player = VideoPlayer(filePath,self.streamData) 
            self.player.validate()
            self._initSliderThread()
            self._updateSliderPosition(0)
            self.gui.enableControls(True)
        except Exception,ex:
            msg= "Error opening file: "+str(ex.args[0])
            print msg
            #self.currentPath = ""
            #TODO: self.gui.clearAll();
            self._updateSliderPosition(0)
            self._showCurrentFrameInfo(0)
            self.gui.showWarning("Invalid file format!")
            self.gui.enableControls(False)


    def addStartMarker(self):
        frame = self.player.getCurrentFrame() 
        framePos = self.player.getCurrentFrameNumber()
        timePos = self.player.getCurrentFrameTime()
        cutEntry = VideoCutEntry(framePos,timePos,VideoCutEntry.MODE_START)
        self._addVideoCut(frame, cutEntry)

    def addStopMarker(self):
        frame = self.player.getCurrentFrame()
        framePos = self.player.getCurrentFrameNumber()
        timePos = self.player.getCurrentFrameTime()
        cutEntry = VideoCutEntry(framePos,timePos,VideoCutEntry.MODE_STOP)
        self._addVideoCut(frame, cutEntry)

    def _addVideoCut(self,frame,cutEntry):
        rowIndex=len(self.videoCuts)
        for idx, videoEntry in enumerate(self.videoCuts):
            frameNbr = videoEntry.frameNumber
            testNbr = cutEntry.frameNumber
            if testNbr < frameNbr:
                rowIndex=idx
                break
        
        self.videoCuts.insert(rowIndex,cutEntry)
        self.gui.addCutMark(frame,cutEntry,rowIndex)
    
    def removeVideoCuts(self):
        self.videoCuts=[]
    
    def removeVideoCutIndex(self,index):
        cut = self.videoCuts[index]
        self.videoCuts.remove(cut)
    
    def gotoCutIndex(self,index):
        cut = self.videoCuts[index]
        self._updateSliderPosition(cut.frameNumber)
    

    def saveVideo(self,path):
        print "generate"
        spanns=[]
        block = None
        for cutEntry in self.videoCuts:
            
            if cutEntry.isStartMode():
                if block:
                    print "Start invalid:", cutEntry.getTimeString()
                else:
                    block=[]
                    block.append(cutEntry)
                    print "Start ok:", cutEntry.getTimeString()
            else:
                if block:
                    print "Stop:", cutEntry.getTimeString()
                    block.append(cutEntry)
                    spanns.append(block)
                    block=None
                else:
                    print "Stop ignored:", cutEntry.getTimeString()
    
        for cutmarks in spanns:
            print cutmarks[0].getTimeString(),"-",cutmarks[1].getTimeString()
        
        src = self.player._file
        #need that without extension!
        self.cutAsync(src,path,spanns)
    
    #-- Menu handling end ---

    def cutAsync(self,srcPath,targetPath,spanns):
        worker = LongRunningOperation(self.__makeCuts,srcPath, targetPath, spanns)
        self.connect(worker,worker.signalDone,self.gui.stopProgress)
        #start the worker thread. 
        worker.startOperation()  
 

    def __makeCuts(self,srcPath,targetPath,spanns):
        cutter = FFMPEGCutter(srcPath,targetPath)
        slices = len(spanns)
        for index, cutmark in enumerate(spanns):
            t1=cutmark[0].timePos
            t2 = cutmark[1].timePos
            cutter.cutPart(t1, t2, index,slices)
        cutter.join()    
        
    '''

    '''
    def _initSliderThread(self):
        self.sliderThread = Worker(self.player.getFrameAt)
        self.connect(self.sliderThread,self.sliderThread.signal,self._showFrame)
    
    #connected to slider-called whenever position is changed.
    def sliderMoved(self,pos):
        if self.player is None or not self.player.isValid():
            self.gui.syncSliderPos(0)
        if not self._frameSet:    
            frameNumber = round(self.player.framecount/LayoutWindow.SLIDER_RESOLUTION*pos,0)
            self.sliderThread.showFrame(frameNumber)
        self._frameSet=False
    

    def dialChanged(self,pos):
        if self.player is None or pos == 0:
            self._timer.stop()
            return
        self._dialStep = pos
        self._timer.start(1)
        
    def _displayAutoFrame(self):
        if self.player is None or not self.player.isValid():
            return
        self._frameSet = True
        frameNumber = self.player.getCurrentFrameNumber()+self._dialStep;
        sliderPos= int(frameNumber*LayoutWindow.SLIDER_RESOLUTION/self.player.framecount)
        self.gui.syncSliderPos(sliderPos)
        aFrame = self.player.getFrameAt(frameNumber)
        self._showFrame(aFrame, frameNumber)
        self._frameSet = False
        
    
    def _displayFrameAtMS(self,milliseconds):
        self._videoUI().showFrame(self.player.getFrameAtMS(milliseconds))
    
    def _showFrame(self,aFrame,aFrameNumber):
        self._videoUI().showFrame(aFrame)
        self._showCurrentFrameInfo(aFrameNumber)
        
    def _displayFrame(self,frameNumber):
        self._videoUI().showFrame(self.player.getFrameAt(frameNumber))

#     def _advanceFrames(self,delta):
#         dx = self.player.getCurrentFrameNumber()+delta
#         self._displayFrame(dx)

    def _videoUI(self):
        return self.gui.getVideoWidget()

    
    def _showCurrentFrameInfo(self,frameNumber):
        out = "Frame: %s Time: %s max: %s" %(str(frameNumber), str(self.player.getCurrentFrameTime()),str(self.player.framecount))
        self.gui.showInfo(out)

    def _updateSliderPosition(self,frameNumber):
        self._frameSet=True
        if frameNumber == 0:
            sliderPos=0
        else:
            sliderPos= int(frameNumber*LayoutWindow.SLIDER_RESOLUTION/self.player.framecount)
        self.gui.syncSliderPos(sliderPos)
        self.sliderThread.showFrame(frameNumber)
    


#-- threads
class Worker(QtCore.QThread):
    def __init__(self, func):
        super(Worker, self).__init__()
        self.func = func
        self.signal=QtCore.SIGNAL('WORKX')
        self.fbnr=0

    def run(self):
        current = -1;
        while self.fbnr != current:
            print "Worker:",self.fbnr
            current = self.fbnr
            result = self.func(current)
            self.emit( self.signal,result,current )

    def __del__(self):
        self.wait()

    def showFrame(self,frameNumber):
        self.fbnr=frameNumber
        self.start()
        
        
class LongRunningOperation(QtCore.QThread): 
    def __init__(self, func, *args):
        QtCore.QThread.__init__(self)
        self.signalDone=QtCore.SIGNAL('LRO_DONE')
        self.function = func
        self.arguments = args

    def run(self):
        self.function(*self.arguments)
        self.emit(self.signalDone)

        
    def startOperation(self):
        self.start() #invokes run - process pending QT events
        sleep(0.5)
        print "proc events"
        QtCore.QCoreApplication.processEvents()

def main():
    OSTools().setCurrentWorkingDirectory()
    app = QApplication(sys.argv)
    app.setWindowIcon(getAppIcon())
    argv = sys.argv
    if len(argv)==1:
        MainFrame()
    else:
        path = argv[1]
        MainFrame(path)        
    return app
    
        
if __name__ == '__main__':
    app = main()
    sys.exit(app.exec_())

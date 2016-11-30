# -*- coding: utf-8 -*-
from PyQt4.Qt import QMessageBox

# 2014 Matze Wegmann (mat.wegmann@gmail.com)
#


try:
    import cv2
except ImportError:
    print "OpenCV not found! Please install."
        
try:
    from cv2 import cv #this is cv2!
except ImportError:
    print "OpenCV 2 not found, expecting Version 3 now"    


import sys, traceback
from datetime import timedelta

from PyQt4 import QtGui,QtCore
from PyQt4.QtCore import QTimer, QObject
from PyQt4.QtGui import QApplication, QImage, QPainter, QWidget, QVBoxLayout,\
    QDesktopWidget, QFileDialog, QDial, QColor, QSizePolicy, QLabel,\
    QHBoxLayout, QListWidget, QGridLayout, QListWidgetItem,\
    QIcon, QMenu, QFrame, QSpinBox, QCheckBox
<<<<<<< HEAD
from PyQt4.Qt import QRectF, QSize, QString, Qt, QStatusBar #, QFrame
from FFMPEGTools import FFMPEGCutter, FFStreamProbe, CuttingConfig
=======
from PyQt4.Qt import QRectF, QSize, QString, Qt, QStatusBar
from FFMPEGTools import FFMPEGCutter, FFStreamProbe
>>>>>>> branch 'master' of https://github.com/kanehekili/VideoCut
import os
from time import sleep
<<<<<<< HEAD
import xml.etree.cElementTree as CT
=======
import xml.etree.cElementTree as CETree
>>>>>>> branch 'master' of https://github.com/kanehekili/VideoCut
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

#TODO join them with the OSTools class and create an import in ant
class OSTools():
    
    def getPathWithoutExtension(self,aPath):
        if aPath:
            #rawPath = os.path.splitext(str(aPath))[0]
            rawPath = os.path.splitext(aPath)[0]
        else:
            rawPath=""
        return rawPath

    def getWorkingDirectory(self):
        abspath = os.path.abspath(__file__)
        dname = os.path.dirname(abspath)
        return dname               

    def getHomeDirectory(self):
        return os.path.expanduser("~")

    def setCurrentWorkingDirectory(self):
        os.chdir(self.getWorkingDirectory())
        
    def getFileNameOnly(self,path):
        return os.path.basename(path)
    
    def fileExists(self,path):
        return os.path.isfile(path)
    
    def removeFile(self,path):
        if self.fileExists(path):
            os.remove(path)

'''
Compat layer for cv2 and 3
'''
class OpenCV2():
    def __init__(self,):
        self._cap = cv2.VideoCapture()
        
    def getCapture(self):
        return self._cap

        
    def setColor(self,numpyArray):
        cv2.cvtColor(numpyArray, cv.CV_BGR2RGB, numpyArray)#@UndefinedVariable
        
    def getFrameWidth(self):
        return self._cap.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH)#@UndefinedVariable
     
    def getFrameHeight(self):
        return self._cap.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT)#@UndefinedVariable
    
    def getFrameCount(self):
        return self._cap.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT)#@UndefinedVariable
    
    def getFPS(self):
        return self._cap.get(cv2.cv.CV_CAP_PROP_FPS)#@UndefinedVariable
    
    def setFramePosition(self,pos):
        self._cap.set(cv2.cv.CV_CAP_PROP_POS_FRAMES,pos)#@UndefinedVariable
    
    def getFramePosition(self):
        return self._cap.get(cv2.cv.CV_CAP_PROP_POS_FRAMES)#@UndefinedVariable
        
    def setAVIPosition(self,pos):
        self._cap.set(cv2.cv.CV_CAP_PROP_POS_AVI_RATIO,pos)#@UndefinedVariable
        
    def setTimePosition(self,ms):
        self._cap.set(cv2.cv.CV_CAP_PROP_POS_MSEC,ms)#@UndefinedVariable
        
    def getTimePosition(self):
        return self._cap.get(cv2.cv.CV_CAP_PROP_POS_MSEC)#@UndefinedVariable     
        

class OpenCV3():
    def __init__(self):
        self._cap = cv2.VideoCapture()
    
    def getCapture(self):
        return self._cap
    
    def setColor(self,numpyArray):
        cv2.cvtColor(numpyArray, cv2.COLOR_BGR2RGB, numpyArray)#@UndefinedVariable
        
    def getFrameWidth(self):
        return self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)#@UndefinedVariable
     
    def getFrameHeight(self):
        return self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)#@UndefinedVariable
    
    def getFrameCount(self):
        return self._cap.get(cv2.CAP_PROP_FRAME_COUNT)#@UndefinedVariable
    
    def getFPS(self):
        return self._cap.get(cv2.CAP_PROP_FPS)#@UndefinedVariable
    
    def setFramePosition(self,pos):
        self._cap.set(cv2.CAP_PROP_POS_FRAMES,pos)#@UndefinedVariable
    
    def getFramePosition(self):
        return self._cap.get(cv2.CAP_PROP_POS_FRAMES)#@UndefinedVariable
        
    def setAVIPosition(self,pos):
        self._cap.set(cv2.CAP_PROP_POS_AVI_RATIO,pos)#@UndefinedVariable
        
    def setTimePosition(self,ms):
        self._cap.set(cv2.CAP_PROP_POS_MSEC,ms)#@UndefinedVariable
        
    def getTimePosition(self):
        return self._cap.get(cv2.CAP_PROP_POS_MSEC)#@UndefinedVariable
    
if "3." in cv2.__version__:
    OPENCV=OpenCV3()
else:
    OPENCV=OpenCV2()    

class XMLAccessor():
    def __init__(self,path):
        self._path=path+".xml"
        
    def writeXML(self,videoCutEntries):
        rootElement = CETree.Element('VC_Data')
        for cut in videoCutEntries:
            entry = CETree.SubElement(rootElement,"Entry")
            entry.attrib["frame"]=str(cut.frameNumber) 
            entry.attrib["mode"]=str(cut.modeString)
        
        with open(self._path, 'w') as aFile:
            CETree.ElementTree(rootElement).write(aFile)

    def readXML(self):
        cutEntries = []
        if not OSTools().fileExists(self._path):
            return cutEntries
        with open(self._path, 'r') as xmlFile:
            xmlData = xmlFile.read()
            
        root = CETree.fromstring(xmlData)
        for info in root:
            frameNbr= float(info.get('frame'))
            markerType= info.get('mode')
            entry = VideoCutEntry(frameNbr,0,markerType)
            cutEntries.append(entry)
        
        return cutEntries

    def clear(self):
        OSTools().removeFile(self._path)
            

class CVImage(QImage):
    def __init__(self,numpyArray):
        height, width, bytesPerComponent = numpyArray.shape
        bytesPerLine = bytesPerComponent * width;
        #cv2.cvtColor(numpyArray, cv2.COLOR_BGR2RGB, numpyArray)
        #cv2: cv2.cvtColor(numpyArray, cv.CV_BGR2RGB, numpyArray)
        OPENCV.setColor(numpyArray)
        super(CVImage,self).__init__(numpyArray.data,width,height,bytesPerLine, QImage.Format_RGB888)


class VideoWidget(QFrame):
    """ A class for rendering video coming from OpenCV """

    def __init__(self, parent):
        QFrame.__init__(self,parent)
        #super(VideoWidget,self).__init__(parent)
        self._defaultHeight=576
        self._defaultWidth=720
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        changeBackgroundColor(self, "lightgray")       
        self._image = None
        self.setDefaultRatio()
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.setLineWidth(1)
   

    def paintEvent(self, event):

        QFrame.paintEvent(self,event)
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
        
        painter = QPainter(self)
        painter.drawImage(QRectF(x, y,imgX,imgY), self._image)
        #painter.end()
  
        
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
        
        self.ui_VideoFrame = VideoWidget(self)
        self.ui_Slider =  QtGui.QSlider(QtCore.Qt.Horizontal)
        self.ui_Slider.setMinimum(0)
        self.ui_Slider.setMaximum(self.SLIDER_RESOLUTION)
        self.ui_Slider.setToolTip("Video track")
        #self.ui_Slider.setTickPosition(Qt.TicksAbove)
        
        self.ui_Dial = QDial(self)
        self.ui_Dial.setProperty("value", 0)
        self.ui_Dial.setNotchesVisible(True)
        self.ui_Dial.setWrapping(False)
        self.ui_Dial.setNotchTarget(5.0)
        self.ui_Dial.setToolTip("Fine tuning")
        self.setDialResolution(self.DIAL_RESOLUTION)

        self.ui_GotoField = QSpinBox(self)
        self.ui_GotoField.setValue(1)
        self.ui_GotoField.setToolTip("Goto Frame")
        
        self.ui_InfoLabel = QLabel(self)
        changeBackgroundColor(self.ui_InfoLabel , "lightblue")
        self.ui_InfoLabel.setText("")
        self.ui_InfoLabel.setToolTip("Infos about the video position")
        
        self.ui_CB_Reencode = QCheckBox(self)
        self.ui_CB_Reencode.setText("Exact cut")
        self.ui_CB_Reencode.setChecked(False)
        self.ui_CB_Reencode.setToolTip("Exact cut is slow, but precise")
        
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
        gridLayout = QGridLayout()
        self.ui_List.setSizePolicy(QSizePolicy.Minimum,QSizePolicy.Expanding)
        gridLayout.addWidget(self.ui_List,0,0,5,1)
        #row column, rowSpan, columnSpan
        gridLayout.addWidget(self.ui_VideoFrame,0,2,3,-1);
        gridLayout.addWidget(self.ui_GotoField,4,1,1,20)
        gridLayout.addWidget(self.ui_InfoLabel,4,26,1,90)
        gridLayout.addWidget(self.ui_CB_Reencode,4,121)
        gridLayout.addWidget(self.ui_Slider,5,0,1,120)
        gridLayout.addWidget(self.ui_Dial,5,121)
        gridLayout.addWidget(self.statusbar,6,0,1,122)

        return gridLayout
                                                  
                         

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
    
    def showStatusMessage(self,text):
        self.statusbar.showMessage(text)
    
    def setDialResolution(self,resolution):
        self.ui_Dial.setMinimum(-resolution/2)
        self.ui_Dial.setMaximum(resolution/2)


    def syncSliderPos(self,pos):
        self.ui_Slider.setSliderPosition(pos)
    
    def setSliderTicks(self,ticks):
        self.ui_Slider.setSingleStep(ticks)
        self.ui_Slider.setPageStep(ticks*2)
    
    def setGotoFieldMaximum(self,count):
        self.ui_GotoField.setMaximum(count)
    
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
        
        self.ui_GotoField.editingFinished.connect(self.__gotoFrame)
        
        self.ui_CB_Reencode.stateChanged.connect(aVideoController.setExactCut)
        
        self.ui_CB_Reencode.stateChanged.connect(aVideoController.setExactCut)
        
        self.statusMessenger = StatusDispatcher()
        self.connect(self.statusMessenger,self.statusMessenger.signal,self.showStatusMessage)
        
        self._hookListActions()
    
    def keyReleaseEvent(self,event):
        self.__resetDial()
     
    def _hookListActions(self):
        #TOO bad-the list model -should be here... 
        rmAction = QtGui.QAction(QtGui.QIcon('icons/close-x.png'), 'Delete', self)
        rmAction.triggered.connect(self._removeMarker)
        rmAllAction = QtGui.QAction(QtGui.QIcon('icons/clear-all.png'), 'Remove all', self)
        rmAllAction.triggered.connect(self.purgeMarker)
        self.gotoAction = QtGui.QAction(QtGui.QIcon('icons/go-next.png'), 'Goto', self)
        self.gotoAction.triggered.connect(self._gotoFromMarker)
  
        #menus      
        self.ui_List.customContextMenuRequested.connect(self._openListMenu)
        self._listMenu = QMenu()
        self._listMenu.addAction(self.gotoAction)
        self._listMenu.addSeparator()
        self._listMenu.addAction(rmAction)
        self._listMenu.addAction(rmAllAction)

        
 
    def __resetDial(self):
        self.ui_Dial.setProperty("value", 0)

    def __gotoFrame(self):
        self.__videoController._gotoFrame(self.ui_GotoField.value())

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

  
    def clearMarkerList(self):
        self.ui_List.clear()

    #remove contents, remove file 
    def purgeMarker(self):
        self.ui_List.clear()
        self.__videoController.purgeVideoCuts()
        
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
        self.setWindowTitle("VideoCut") 
        return widgets
    
    def updateWindowTitle(self,text):
        qText = QString(text.decode('utf-8'))
        self.setWindowTitle("VideoCut - "+qText)
     
    def showInfo(self,text):
        self._widgets.showInfo(text)


    def getVideoWidget(self):
        return self._widgets.ui_VideoFrame

    def syncSliderPos(self,pos):
        self._widgets.syncSliderPos(pos)
        
    def setDialResolution(self,fps):
        self._widgets.setDialResolution(fps)

    def setGotoMaximum(self,count):
        self._widgets.setGotoFieldMaximum(count)

    def setSliderTicks(self,ticks):
        self._widgets.setSliderTicks(ticks)        

    def addCutMark(self,frame,cutEntry,rowIndex):
        self._widgets.addCutMark(frame,cutEntry,rowIndex)
        
    def showBusy(self):
        self._widgets.showBusy()
        
    def stopProgress(self):
        self._widgets.stopProgress()

    def showWarning(self,aMessage):
        QtGui.QMessageBox.warning(self,"Not supported",aMessage,QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton, QtGui.QMessageBox.NoButton)
    
    
    def enableControls(self,enable):
        self._widgets.ui_Dial.setEnabled(enable)
        self._widgets.ui_Slider.setEnabled(enable)
            
                            
    #-------- ACTIONS ----------
    def loadFile(self):
        initalPath = self._videoController.getTargetFile()
        result = QFileDialog.getOpenFileName(parent=self, directory=initalPath, caption=QString("Load Video"));
        if result:
            fn = self.__encodeQString(result)
            self._widgets.clearMarkerList()
            self._videoController.clearVideoCutEntries()
            self._videoController.setFile(fn)#encode error: str(result)
            
    def saveVideo(self):
        initalPath = self._videoController.getTargetFile()
        qText = QString(initalPath.decode('utf-8'))
        result = QFileDialog.getSaveFileName(parent=self, directory=qText, caption=QString("Save Video"));
        if result:
            fn = self.__encodeQString(result)
            self._widgets.showBusy()
            self._videoController.saveVideo(fn)
    
    def __encodeQString(self,qString):
        return unicode(qString).encode('utf-8')
    
    def showCodecInfo(self):
        #TODO: More infos, better layout
        try:
            videoData = self._videoController.streamData.getVideoStream()
            audioData = self._videoController.streamData.getAudioStream()
            '''
            (FPS Avg,videoData.getFrameRate()),
            (Aspect,videoData.getAspectRatio()),
            (Video Codec,videoData.getCodec()),
            
            (Width,videoData.getWidth()),
            (Height,videoData.getHeight()),
            getCodecTimeBase
            getTimeBase
            (Bitrate,videoData.bitRate()),
            (Duration,videoData.duration())
            (FPS?,vidoeaData.frameRate())
            
            (Audio Codec,audioData.getCodec())
            '''
            text = '<table border=0 cellspacing="3",cellpadding="2"><tr border=1><td><b>Video Codec:</b></td><td> %s </td></tr><tr><td><b>Aspect:</b></td><td> %s </td></tr><tr><td><b>FPS:</b></td><td> %s </td></tr><tr><td><b>Audio codec:</b></td><td> %s </td></tr></table>' %(videoData.getCodec(),videoData.getAspectRatio(),videoData.getFrameRate(),audioData.getCodec())
        except:
            text = "<br><b>No Information</b><br>"    
        self.__getInfoDialog(text).show()
        
    def playVideo(self):
        isPlaying = self._videoController.toggleVideoPlay()
        self.setVideoPlayerControls(isPlaying)
    
    def setVideoPlayerControls(self,isPlaying):
        if isPlaying:
            self.__enableActionsOnVideoPlay(False)
            self.playAction.setIcon(QtGui.QIcon('./icons/pause.png'))
        else:
            self.__enableActionsOnVideoPlay(True)
            self.playAction.setIcon(QtGui.QIcon('./icons/play.png'))            
               
    #-------- ACTIONS  END ----------    

    def __enableActionsOnVideoPlay(self,enable):
        #TODO:Disabling leads to crash ?
        #self.enableControls(enable)
        self._widgets.ui_Slider.setEnabled(enable)
        self.loadAction.setEnabled(enable)
        self.saveAction.setEnabled(enable) 
        self._widgets.gotoAction.setEnabled(enable)        

    def __getInfoDialog(self,text):
        dlg = QtGui.QDialog(self)
        dlg.setWindowModality(QtCore.Qt.WindowModal)
        dlg.setWindowTitle("Video Infos")
        layout = QtGui.QVBoxLayout(dlg)
        label = QtGui.QLabel(text)
        layout.addWidget(label)
        return dlg

    def getErrorDialog(self,text,infoText,detailedText):
        dlg = QMessageBox(self)
        dlg.setIcon(QMessageBox.Warning)
        dlg.setWindowModality(QtCore.Qt.WindowModal)
        dlg.setWindowTitle("Error")
        dlg.setText(text)
        dlg.setInformativeText(infoText)
        dlg.setDetailedText(detailedText)
        dlg.setStandardButtons(QMessageBox.Ok)
        
        return dlg
        


class VideoPlayer():
    def __init__(self,path,streamProbe):
        self.framecount = 0
        self.totalTimeMilliSeconds = 0.0 
        self._streamProbe=streamProbe
        self._capture = None
        self._file=str(path)
        self._isValid = self._captureFromFile()
        
        
    def _captureFromFile(self):
        if self._streamProbe is None or not self._streamProbe.isKnownVideoFormat():
            print "STREAM NOT KNOWN"
            return False
        self._capture = OPENCV.getCapture();
        if not self._capture.open(self._file):
            print "STREAM NOT OPENED"
            return False

        self 
        self.frameWidth= OPENCV.getFrameWidth()
        self.frameHeight= OPENCV.getFrameHeight()
        self.framecount= OPENCV.getFrameCount()
        self.fps= OPENCV.getFPS()
        
        '''
        self.frameWidth= self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.frameHeight= self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        self.framecount= self._capture.get(cv2.CAP_PROP_FRAME_COUNT)
        self.fps= self._capture.get(cv2.CAP_PROP_FPS)
        
        this is cv2: code:
        self.frameWidth= self._capture.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH)
        self.frameHeight= self._capture.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT)
        self.framecount= self._capture.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT)
        self.fps= self._capture.get(cv2.cv.CV_CAP_PROP_FPS)

        '''
        #The problem: cv has a problem if it is BEHIND the last frame...
        #DO NOT USE;;;;; cap.set(cv2.cv.CV_CAP_PROP_POS_AVI_RATIO,1);
#         test = cap.set(cv2.cv.CV_CAP_PROP_POS_FRAMES,self.framecount-10)
#         self.totalTimeMilliSeconds = cap.get(cv2.cv.CV_CAP_PROP_POS_MSEC);
#         if self.frameHeight< 10.0 or self.frameWidth < 10.0 or self.framecount < 10.0 or self.fps < 10.0:
#             return cap;
        self.totalTimeMilliSeconds = int(self.framecount/self.fps*1000)
        OPENCV.setFramePosition(0)
        print "STREAM OK"
        return True

    def validate(self):
        if not self.isValid():
            raise Exception('Invalid file')

    def isValid(self):
        return self._isValid 

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

    def grabNextFrame(self):
        if not self.isValid():
            return None

        ret, frame = self._capture.read()
        if ret:
            return frame
        return None
    

    def __getLastFrame(self,cap,frameIndex):
        if frameIndex<1:
            return None
        OPENCV.setFramePosition(frameIndex-1)
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
        OPENCV.setFramePosition(frameNumber)
    
    def getFrameAt(self,frameNumber):
        self.setFrameAt(frameNumber-1)
        return self.getNextFrame()

    '''
    seeks a frame based on AV pos (between 0 and 1) -SLOW!!!!!
    '''
    def getFrameAtAVPos(self,avPos):
        OPENCV.setAVIPosition(avPos)
        return self.getNextFrame()
 
    def getFrameAtMS(self,ms):
        OPENCV.setTimePosition(ms)
        return self.getNextFrame()
 
    def getFrameSize(self):
        return QSize(self.frameWidth,self.frameHeight)
    
    def getCurrentFrameTime(self):
        if not self.isValid():
            timeSlot=0
        else:
            timeSlot = OPENCV.getTimePosition()    

        try:    
            td = timedelta(milliseconds=long(timeSlot))
        except:
            td = timedelta.max
        return td
    
    def getCurrentTimeMS(self):
        return OPENCV.getTimePosition()
     
    def getCurrentFrameNumber(self):
        return OPENCV.getFramePosition()

    def close(self):
        if self._capture is not None:
            self._capture.release()
             
'''
  handles the events from the GUI, connecting to the VideoPlayer and the VideoWidget... 
'''        
class VideoControl(QObject):
    def __init__(self,mainFrame):
        #super(VideoControl, self).__init__()
        QObject.__init__(self)
        self.player = None
        self.gui = mainFrame
        self._frameSet=False
        self._initTimer()
        self.videoCuts=[]
        self.currentPath = OSTools().getHomeDirectory()#//TODO get a Video dir
        self.streamData = None
        self._vPlayer = None
        self.exactcut = False

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
        try:
            self.streamData = FFStreamProbe(filePath)
            self.currentPath = OSTools().getPathWithoutExtension(filePath); 
        except: 
            self.streamData = None  
            self.currentPath = OSTools().getHomeDirectory()    
        try:            
            self.player = VideoPlayer(filePath,self.streamData) 
            self._initSliderThread()
            self.player.validate()
            
            self.__initSliderTicks()
            self.gui.enableControls(True)
            self.gui.updateWindowTitle(OSTools().getFileNameOnly(filePath))
            self._asyncInitVideoViews()
           
        except:
            self.gui.updateWindowTitle(OSTools().getFileNameOnly(filePath))
            self._gotoFrame(0)
            self._showCurrentFrameInfo(0)
            if not OSTools().fileExists(filePath):
                msg = "File not found"
            else:
                msg = "Invalid file format!"
            
            self.gui.showWarning(msg)
            self.gui.enableControls(False)
<<<<<<< HEAD
=======
            traceback.print_exc(file=sys.stdout)
>>>>>>> branch 'master' of https://github.com/kanehekili/VideoCut
    
    def setExactCut(self,reencode): 
        self.exactcut = Qt.Checked==reencode   

    def addStartMarker(self):
        self._createVideoCutEntry(VideoCutEntry.MODE_START)
        self.gui._widgets.statusMessenger.say("Marker created")

    def addStopMarker(self):
        self._createVideoCutEntry(VideoCutEntry.MODE_STOP)

    def _createVideoCutEntry(self,mode,updateXML=True):
        self.sliderThread.wait()
        frame = self.player.getCurrentFrame()
        framePos = self.player.getCurrentFrameNumber()
        timePos = self.player.getCurrentFrameTime()
        cutEntry = VideoCutEntry(framePos,timePos,mode)
        self._addVideoCut(frame, cutEntry,updateXML)
        

    def _addVideoCut(self,frame,cutEntry,updateXML):
        rowIndex=len(self.videoCuts)
        for idx, videoEntry in enumerate(self.videoCuts):
            frameNbr = videoEntry.frameNumber
            testNbr = cutEntry.frameNumber
            if testNbr < frameNbr:
                rowIndex=idx
                break
        
        self.videoCuts.insert(rowIndex,cutEntry)
        self.gui.addCutMark(frame,cutEntry,rowIndex)
        if updateXML:
            XMLAccessor(self.currentPath).writeXML(self.videoCuts)

    def _asyncInitVideoViews(self):
        #QTimer.singleShot(10,self._gotoFrame)
        QTimer.singleShot(10,self._grabNextFrame)
        QTimer.singleShot(150, self.restoreVideoCuts)

    def restoreVideoCuts(self):
        self.sliderThread.wait() #sync with the worker
        
        cutList=XMLAccessor(self.currentPath).readXML()  
        for cut in cutList:
            fbnr = cut.frameNumber
            self.player.setFrameAt(fbnr)
            mode = VideoCutEntry.MODE_STOP
            if cut.isStartMode():
                mode = VideoCutEntry.MODE_START
            self._createVideoCutEntry(mode,False)


        self.player.setFrameAt(0)          
    
    #remove/clear all cuts but leave the file untouched
    def clearVideoCutEntries(self):
        self.videoCuts=[]

    #clear all cuts and its persistence
    def purgeVideoCuts(self):
        self.clearVideoCutEntries()
        XMLAccessor(self.currentPath).clear()        
    
    def removeVideoCutIndex(self,index):
        cut = self.videoCuts[index]
        self.videoCuts.remove(cut)
        XMLAccessor(self.currentPath).writeXML(self.videoCuts)
    
    def gotoCutIndex(self,index):
        cut = self.videoCuts[index]
        self._gotoFrame(cut.frameNumber)
    

    def saveVideo(self,path):
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
        config = CuttingConfig(srcPath,targetPath)
        config.streamData = self.streamData
        config.reencode = self.exactcut
        config.messenger = self.gui._widgets.statusMessenger
        cutter = FFMPEGCutter(config)
        
        cutter.ensureAvailableSpace()
        slices = len(spanns)
        for index, cutmark in enumerate(spanns):
            t1=cutmark[0].timePos
            t2 = cutmark[1].timePos
<<<<<<< HEAD
            hasSucess = cutter.cutPart(t1, t2, index,slices)
            # addon! hasSucess = cutter.cutPart(t1, t2, index,slices,self.exactcut)
=======
            hasSucess = cutter.cutPart(t1, t2, index,slices,self.exactcut)
>>>>>>> branch 'master' of https://github.com/kanehekili/VideoCut
            if not hasSucess:
                print"VC-Cut error" #TODO need a signal for error
                return
        cutter.join()    
        
    '''

    '''
    def _initSliderThread(self):
        self.sliderThread = Worker(self.player.getFrameAt)
        self.connect(self.sliderThread,self.sliderThread.signal,self._showFrame)
    
    #we want 1 minute per single step
    def __initSliderTicks(self):
        videoInfo= self.streamData.getVideoStream()
        fps = videoInfo.getFrameRate()
        if self.player.framecount > 0:
            ratio = round(LayoutWindow.SLIDER_RESOLUTION*60*fps/self.player.framecount,1)
            self.gui.setSliderTicks(ratio)
            self.gui.setDialResolution(fps)
            self.gui.setGotoMaximum(self.player.framecount)
        self._frameSet=False 
         
        
    #connected to slider-called whenever position is changed.
    def sliderMoved(self,pos):
        if self.player is None or not self.player.isValid():
            self.gui.syncSliderPos(0)
        if not self._frameSet: 
            frameNumber = round(self.player.framecount/LayoutWindow.SLIDER_RESOLUTION*pos,0)
            self.__dispatchShowFrame(frameNumber)
        self._frameSet=False

    #display Frame with syncing the slider pos. 
    def _gotoFrame(self,frameNumber=0):
        self._frameSet=True
        if self.player.framecount < 1:
            return;
        if frameNumber == 0:
            sliderPos=0
        else:
            sliderPos= int(frameNumber*LayoutWindow.SLIDER_RESOLUTION/self.player.framecount)
        self.gui.syncSliderPos(sliderPos)
        self.__dispatchShowFrame(frameNumber)
    
    def __dispatchShowFrame(self,frameNumber):
        if self._vPlayer is None:
            self.sliderThread.showFrame(frameNumber)
    
    #connected to the dial
    def dialChanged(self,pos):
        if self.player is None or pos == 0:
            self._timer.stop()
            return
        self._dialStep = pos
        #self._dialStep = 1
        ts=(1/self.player.fps)*2500
        #print "dial:",pos, " time:",ts
        self._timer.start(ts)
 
    #called by timer on dial change...    
    def _displayAutoFrame(self):
        if self.player is None or not self.player.isValid():
            return
        self.sliderThread.wait()#No concurrency with worker!
        self._frameSet = True
        frameNumber = max(0,self.player.getCurrentFrameNumber()+self._dialStep);
        sliderPos= int(frameNumber*LayoutWindow.SLIDER_RESOLUTION/self.player.framecount)
        self.gui.syncSliderPos(sliderPos)
        aFrame = self.player.getFrameAt(frameNumber)
        self._showFrame(aFrame)
#        self._gotoFrame(frameNumber)
        self._frameSet = False
        
    #called by worker ...
    def _showFrame(self,aFrame):
        self._videoUI().showFrame(aFrame)
        x = self.player.getCurrentFrameNumber()
        self._showCurrentFrameInfo(x)
        
    def _displayFrame(self,frameNumber):
        self._videoUI().showFrame(self.player.getFrameAt(frameNumber))

    def _videoUI(self):
        return self.gui.getVideoWidget()

    
    def _showCurrentFrameInfo(self,frameNumber):
        timeinfo = self.player.getCurrentFrameTime()
        #basket = "%02d.%03i" %(timeinfo.seconds,timeinfo.microseconds/1000)
        out = "Frame: %s Time: %s max: %s" %(str(frameNumber), str(timeinfo),str(self.player.framecount))
        #TODO: Pass 3 values for 3 widgets....
        self.gui.showInfo(out)

    
    def toggleVideoPlay(self):
        if self.streamData is None:
            return False
        if self._vPlayer is None:
            return self.__playVideo()
        
        return self.__stopVideo()

    #TODO Warning, if it runs, Worker may NOT be used!
    def __playVideo(self):
        self._vPlayer = QTimer(self.gui)
        self._vPlayer.timeout.connect(self._grabNextFrame)
        #50 ms if 25 fps and 25 if 50fps
        fRate=(1/self.player.fps)*1250
        self._vPlayer.start(fRate)
        return True

    def __stopVideo(self):
            self._vPlayer.stop()
            self._vPlayer = None
            self._frameSet = False
            return False

    def _grabNextFrame(self):
        self._frameSet = True
        frame= self.player.grabNextFrame()
        if frame is not None:
            self._videoUI().showFrame(frame)
            frameNumber = self.player.getCurrentFrameNumber()
            sliderPos= int(frameNumber*LayoutWindow.SLIDER_RESOLUTION/self.player.framecount)
            self._showCurrentFrameInfo(frameNumber)
            self.gui.syncSliderPos(sliderPos)
        else:
            self.gui.setVideoPlayerControls(False)
            self.player.framecount = self.player.getCurrentFrameNumber()
            self.__stopVideo()        


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
            #print "Worker:",self.fbnr
            current = self.fbnr
            result = self.func(current)
            self.emit( self.signal,result )

    def __del__(self):
        self.wait()

    def showFrame(self,frameNumber):
        self.fbnr=frameNumber
        self.start()
        
''' Long running operations for actions that do not draw or paint '''        
class LongRunningOperation(QtCore.QThread): 
    def __init__(self, func, *args):
        QtCore.QThread.__init__(self)
        self.signalDone=QtCore.SIGNAL('LRO_DONE')
        self.function = func
        self.arguments = args

    def run(self):
        try:
            self.function(*self.arguments)
        except:
            traceback.print_exc(file=sys.stdout)
        finally:
            self.emit(self.signalDone)

        
    def startOperation(self):
        self.start() #invokes run - process pending QT events
        sleep(0.5)
        QtCore.QCoreApplication.processEvents()

class StatusDispatcher(QObject):
    def __init__(self):
        QObject.__init__(self)
        self.text=""
        self.signal=QtCore.SIGNAL('BroadcastText')
    def say(self,aString):
        self.text=aString
        self.emit(self.signal,aString)

WIN=None

def handle_exception(exc_type, exc_value, exc_traceback):
    """ handle all exceptions """
    if WIN is not None:
        
        infoText = exc_value.message
        detailText ="*".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        WIN.getErrorDialog("Unexpected error",infoText,detailText).show()
     

def main():
    try:
        global WIN
        OSTools().setCurrentWorkingDirectory()
        argv = sys.argv
        app = QApplication(argv)
        app.setWindowIcon(getAppIcon())
        if len(argv)==1:
            WIN = MainFrame() #keep python reference!
        else:
            WIN = MainFrame(argv[1])  
        app.exec_()
    except:
        traceback.print_exc(file=sys.stdout)
        
if __name__ == '__main__':
    sys.excepthook=handle_exception
    sys.exit(main())

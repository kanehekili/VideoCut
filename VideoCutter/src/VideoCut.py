# -*- coding: utf-8 -*-
# 2014 kanehekili (mat.wegmann@gmail.com)
#

import sys, traceback, math

try:
    import cv2 #cv3
    print cv2.getBuildInformation()
except ImportError:
    print "OpenCV 3 not found,, expecting Version 2 now"
    try:
        from cv2 import cv #this is cv2!
    except ImportError:
        print "OpenCV 2 not found"  
        app = QtGui.QApplication(sys.argv)
        QtGui.QMessageBox.critical(None, "OpenCV",
            "Opencv2 or opencv3 must be installed to run VideoCut.")
        sys.exit(1)


from datetime import timedelta
#QT4
from PyQt4.Qt import QMessageBox, QFontMetrics
from PyQt4 import QtGui,QtCore
from PyQt4.QtCore import QTimer, QObject
from PyQt4.QtGui import QApplication, QImage, QPainter, QWidget, QVBoxLayout,\
    QDesktopWidget, QFileDialog, QDial, QColor, QSizePolicy, QLabel,\
    QHBoxLayout, QListWidget, QGridLayout, QListWidgetItem,\
    QIcon, QMenu, QFrame, QSpinBox, QCheckBox
from PyQt4.Qt import QRectF, QSize, QString, Qt, QStatusBar #, QFrame
from FFMPEGTools import FFMPEGCutter, FFStreamProbe, CuttingConfig,OSTools,Logger,VCCutter
import os
from time import sleep
import xml.etree.cElementTree as CT

# sizes ..
SIZE_ICON=80
ITEM_ROW_COUNT=3

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
    
    def isOpened(self):
        return self._cap.isOpened()    
        

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
    
    def isOpened(self):
        return self._cap.isOpened() 
    
if "3." in cv2.__version__:
    OPENCV=OpenCV3()
    print "using CV3"
else:
    OPENCV=OpenCV2()
    print "using CV2"    

class XMLAccessor():
    def __init__(self,path):
        self._path=path+".xml"
        
    def writeXML(self,videoCutEntries):
        rootElement = CT.Element('VC_Data')
        for cut in videoCutEntries:
            entry = CT.SubElement(rootElement,"Entry")
            entry.attrib["frame"]=str(cut.frameNumber) 
            entry.attrib["mode"]=str(cut.modeString)
        
        with open(self._path, 'w') as aFile:
            CT.ElementTree(rootElement).write(aFile)

    def readXML(self):
        cutEntries = []
        if not OSTools().fileExists(self._path):
            return cutEntries
        with open(self._path, 'r') as xmlFile:
            xmlData = xmlFile.read()
            
        root = CT.fromstring(xmlData)
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
        OPENCV.setColor(numpyArray)
        super(CVImage,self).__init__(numpyArray.data,width,height,bytesPerLine, QImage.Format_RGB888)


class VideoWidget(QFrame):
    """ A class for rendering video coming from OpenCV """
    
    def __init__(self, parent):
        QFrame.__init__(self,parent)
        self._defaultHeight=576
        self._defaultWidth=720
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        changeBackgroundColor(self, "lightgray")       
        self._image = None
        self.imageRatio = 16.0/9.0
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
            self._image = CVImage(aFrame)
        self.update()
        
    def setVideoRatio(self,ratio):
        self.imageRatio = float(ratio)


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
        t1 = str(self.timePos).split('.')
        if len(t1)< 2:
            return t1[0]
        t1[1]=t1[1][:3]
        return '.'.join(t1)
    
class VCSpinbox(QSpinBox):
    def __init__(self,parent=None):
        QSpinBox.__init__(self,parent)
        
    def keyPressEvent(self, keyEvent):
        if (keyEvent.key() == QtCore.Qt.Key_Enter) or (keyEvent.key() == QtCore.Qt.Key_Return):
            super(VCSpinbox, self).keyPressEvent(keyEvent)
        else:
            self.blockSignals(True)
            super(VCSpinbox, self).keyPressEvent(keyEvent)
            self.blockSignals(False)
        
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
        #contribution:
        self.ui_Slider.setStyleSheet(stylesheet(self))
        
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

        #TODO: subclass spinbox. do not trigger if editing until enter or one of the buttons is pressed.  
        #self.ui_GotoField = QSpinBox(self)
        self.ui_GotoField = VCSpinbox(self)
        self.ui_GotoField.setValue(1)
        self.ui_GotoField.setToolTip("Goto Frame")
        
        
        self.ui_InfoLabel = QLabel(self)
        #self.ui_InfoLabel.setMargin(4)
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

    def makeGridLayout(self):
        gridLayout = QGridLayout()
        self.ui_List.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Expanding)
        self.ui_List.setMaximumWidth(SIZE_ICON*2.6)
        gridLayout.addWidget(self.ui_List,0,0,5,1)
        #from row,from col, rowSpan, columnSpan
       
        gridLayout.addWidget(self.ui_VideoFrame,0,1,4,-1);
        gridLayout.addWidget(self.ui_GotoField,4,1,1,2)
        gridLayout.addWidget(self.ui_InfoLabel,4,3,1,8)
        gridLayout.addWidget(self.ui_CB_Reencode,4,11,1,-1)
        gridLayout.addWidget(self.ui_Slider,5,0,1,11)
        gridLayout.addWidget(self.ui_Dial,5,11,1,-1)
        gridLayout.addWidget(self.statusbar,6,0,1,12)

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
        item.setSizeHint(QSize(SIZE_ICON,self.ITEM_HEIGHT))
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
        marker.setWordWrap(False)
        #marker.setStyleSheet("QLabel::focus { background: transparent;color : yellow; }")
        marker.layout()
        
        self.ui_List.setItemWidget(item,marker)
        self.ui_List.setIconSize(QSize(SIZE_ICON,SIZE_ICON)) #Forces an update!
        self.ui_List.setCurrentItem(item)
        
 
    def hookEvents(self,aVideoController):
        self.__videoController=aVideoController #for menu callbacks
        self.ui_Slider.valueChanged.connect(aVideoController.sliderMoved)
        
        self.ui_Dial.valueChanged.connect(aVideoController.dialChanged)
        self.ui_Dial.sliderReleased.connect(self.__resetDial)
        
        #self.ui_GotoField.editingFinished.connect(self.__gotoFrame)
        self.ui_GotoField.valueChanged.connect(self.__gotoFrame)
        
        self.ui_CB_Reencode.stateChanged.connect(aVideoController.setExactCut)
        
        self.statusMessenger = StatusDispatcher()
        self.connect(self.statusMessenger,self.statusMessenger.signal,self.showStatusMessage)
        
        self._hookListActions()
    
    def spinButtonTest(self,value):
        print "test",value
    
    def syncSpinButton(self,frameNbr):
        self.ui_GotoField.blockSignals(True)
        self.ui_GotoField.setValue(frameNbr)
        self.ui_GotoField.blockSignals(False)
    
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

    def __gotoFrame(self,value):
        self.__videoController._gotoFrame(value)

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
        iconList.setStyleSheet("QListView{outline:none;} QListWidget::item:selected { background: #28D9FF; } ")#that text color seems not to work!
        fontM = QFontMetrics(iconList.font())
        self.ITEM_HEIGHT=fontM.height()*ITEM_ROW_COUNT
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

        self.centerWindow()
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
        
        '''
        the conversion menues
        '''
        #self.convertToMP4 = QtGui.QAction(QtGui.QIcon('./icons/stop-red-icon.png'),"Convert to mp4",self)
        self.convertToMP4 = QtGui.QAction("Convert to mp4",self)
        self.convertToMP4.setCheckable(True)
#         self.selectContainer = QtGui.QAction(QtGui.QIcon('./icons/stop-red-icon.png'),"change to a different container",self)
#         self.extractMP3 = QtGui.QAction(QtGui.QIcon('./icons/stop-red-icon.png'),"Extract MP3",self)
#         self.switchAudio = QtGui.QAction(QtGui.QIcon('./icons/stop-red-icon.png'),"Swtich audio",self)
        self.mediaSettings= QtGui.QAction(QtGui.QIcon('./icons/settings.png'),"Output settings",self)
        self.mediaSettings.setShortcut('Ctrl+T')
        self.mediaSettings.triggered.connect(self.openMediaSettings)

        
        '''
        toolbar defs
        '''
        self.toolbar = self.addToolBar('Main')
        self.toolbar.addAction(self.loadAction)
        self.toolbar.addAction(self.saveAction)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.startAction)
        self.toolbar.addAction(self.stopAction)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.infoAction)
        self.toolbar.addAction(self.playAction)
        self.toolbar.addAction(self.mediaSettings)
                               
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(self.loadAction)
        fileMenu.addAction(self.saveAction)
        fileMenu.addSeparator();
        fileMenu.addAction(self.startAction)
        fileMenu.addAction(self.stopAction)
        fileMenu.addSeparator();
        fileMenu.addAction(self.exitAction)

        '''
        #TODO - add functions:
        fileMenu = menubar.addMenu('&Conversion')
        fileMenu.addAction(self.convertToMP4)
        fileMenu.addAction(self.selectContainer)
        fileMenu.addAction(self.extractMP3)
        fileMenu.addAction(self.switchAudio)
        '''
        widgets = LayoutWindow()
        self.setCentralWidget(widgets);
        self.setWindowTitle("VideoCut") 
        return widgets
    
    def centerWindow(self):
        frameGm = self.frameGeometry()
        screen = QtGui.QApplication.desktop().screenNumber(QtGui.QApplication.desktop().cursor().pos())
        centerPoint = QtGui.QApplication.desktop().screenGeometry(screen).center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())        

    
    def updateWindowTitle(self,text):
        qText = QString(text.decode('utf-8'))
        self.setWindowTitle("VideoCut - "+qText)
     
    def showInfo(self,text):
        self._widgets.showInfo(text)

    def syncSpinButton(self,frameNbr):
        self._widgets.syncSpinButton(frameNbr)

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
    
    def openMediaSettings(self):
        dlg= SettingsDialog(self)
        dlg.show()
    
    def showCodecInfo(self):
        #TODO: More infos, better layout
        try:
            streamData= self._videoController.streamData 
            container = streamData.formatInfo;
            videoData = streamData.getVideoStream()
            audioData = streamData.getAudioStream()
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
            #text = '<table border=0 cellspacing="3",cellpadding="2"><tr border=1><td><b>Video Codec:</b></td><td> %s </td></tr><td><b>Dimension:</b></td><td> %s x %s </td></tr><tr><td><b>Aspect:</b></td><td> %s </td></tr><tr><td><b>FPS:</b></td><td> %s </td></tr><tr><td><b>Duration:</b></td><td> %s </td></tr><tr><td><b>Audio codec:</b></td><td> %s </td></tr></table>' %(videoData.getCodec(),videoData.getWidth(),videoData.getHeight(),videoData.getAspectRatio(),videoData.getFrameRate(),videoData.duration(),audioData.getCodec())
            text = """<table border=0 cellspacing="3",cellpadding="2">
                    <tr border=1><td><b>Container:</b></td><td> %s </td></tr>
                    <tr><td><b>Bitrate:</b></td><td> %s [kb/s]</td></tr>
                    <tr><td><b>Size:</b></td><td> %s [kb] </td></tr>
                    <tr><td><b>is TS:</b></td><td> %s </td></tr>
                    <tr><td><b>Video Codec:</b></td><td> %s </td></tr>
                    <tr><td><b>Dimension:</b></td><td> %sx%s </td></tr>
                    <tr><td><b>Aspect:</b></td><td> %s </td></tr>
                    <tr><td><b>FPS:</b></td><td> %s </td></tr>
                    <tr><td><b>Duration:</b></td><td> %s [sec]</td></tr>
                    <tr><td><b>Audio codec:</b></td><td> %s </td></tr>
                    </table>"""%(container.formatNames()[0],container.getBitRate(),container.getSizeKB(),streamData.isTransportStream(),videoData.getCodec(),videoData.getWidth(),videoData.getHeight(),videoData.getAspectRatio(),videoData.getFrameRate(),videoData.duration(),audioData.getCodec())                    
        except:
            Log.logException("Invalid codec format")
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
        self.enableControls(enable)
        self.loadAction.setEnabled(enable)
        self.saveAction.setEnabled(enable) 
        self._widgets.gotoAction.setEnabled(enable)        

    def __getInfoDialog(self,text):
        dlg = QtGui.QDialog(self)
        dlg.setWindowModality(QtCore.Qt.WindowModal)
        dlg.setWindowTitle("Video Infos")
        layout = QtGui.QVBoxLayout(dlg)
        label = QtGui.QLabel(text)
        label.sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        label.setSizePolicy(label.sizePolicy)
        label.setMinimumSize(QtCore.QSize(450, 40))
        layout.setSizeConstraint(QtGui.QLayout.SetFixedSize)
        layout.addWidget(label)
        return dlg

    def _getSettingsDialog(self):
        dlg = QtGui.QDialog(self)
        dlg.setWindowModality(QtCore.Qt.WindowModal)
        dlg.setWindowTitle("Settings")
        layout = QtGui.QVBoxLayout(dlg)
        

    def getErrorDialog(self,text,infoText,detailedText):
        dlg = DialogBox(self)
        dlg.setIcon(QMessageBox.Warning)
        dlg.setWindowModality(QtCore.Qt.WindowModal)
        dlg.setWindowTitle("Error")
        dlg.setText(text)
        dlg.setInformativeText(infoText)
        dlg.setDetailedText(detailedText)
        dlg.setStandardButtons(QMessageBox.Ok)
        return dlg

class SettingsDialog(QtGui.QDialog):

    def __init__(self,parent):
        """Init UI."""
        super(SettingsDialog, self).__init__(parent)
        self.init_ui()

    def init_ui(self):
        self.setWindowModality(QtCore.Qt.WindowModal)
        self.setWindowTitle("Settings")


        outBox = QtGui.QVBoxLayout()
        #outBox.addStretch(1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        frame1 =  QtGui.QFrame()
        frame1.setFrameStyle(QFrame.Box | QFrame.Sunken)
        frame1.setLineWidth(1)
       
        frame2 =  QtGui.QFrame()
        frame2.setFrameStyle(QFrame.Box | QFrame.Sunken)
        frame2.setLineWidth(1)
       
        encodeBox = QtGui.QVBoxLayout(frame1)
        self.check_reencode =  QtGui.QCheckBox("Reencode")
        #self.check_reencode.toolTip("Force exact cut. Makes it real slow!")
        #connect
        self.combo = QtGui.QComboBox()
        self.combo.addItem("mp4", None)
        self.combo.addItem("mp2", None)
        self.combo.addItem("flv", None)
        #connect
        encodeBox.addWidget(self.check_reencode)
        encodeBox.addWidget(self.combo)
        
        
        
        expoBox = QtGui.QVBoxLayout(frame2)
        radioHBox = QtGui.QHBoxLayout()
        self.exBasic = QtGui.QRadioButton("Basic")
        self.exBasic.setChecked(True)
        #self.exBasic.toggled.connect(lambda:self.btnstate(self.exBasic))
        radioHBox.addWidget(self.exBasic)
        
        self.exRemux = QtGui.QRadioButton("Experimental")
        #self.exRemux.toggled.connect(lambda:self.btnstate(self.b2))
        radioHBox.addWidget(self.exRemux)

        radioVBox = QtGui.QVBoxLayout()
        rGroup1 = QtGui.QButtonGroup(frame2)
        #radioVBox.addStretch(1)
        self.exIFrame = QtGui.QRadioButton("I-Frame")
        self.exExact = QtGui.QRadioButton("Exact")
        rGroup1.addButton(self.exIFrame)
        rGroup1.addButton(self.exExact)
        radioVBox.addWidget(self.exIFrame)
        radioVBox.addWidget(self.exExact)
        
        expoBox.addLayout(radioHBox)
        expoBox.addLayout(radioVBox)
        
        #outBox.addWidget(??)
        outBox.addWidget(frame1)
        outBox.addWidget(frame2)
        self.setLayout(outBox)
        
        
class DialogBox(QMessageBox): #subclassed for reasonable sizing 

    def __init__(self, *args, **kwargs):            
        super(DialogBox, self).__init__(*args, **kwargs)

    # We only need to extend resizeEvent, not every event.
    def resizeEvent(self, event):

        result = super(DialogBox, self).resizeEvent(event)

        details_box = self.findChild(QtGui.QTextEdit)
        if details_box is not None:
            geo = details_box.sizeHint()
            w= geo.width()*2
            h = geo.height()
            details_box.setFixedSize(QtCore.QSize(w,h))
        else:
            print("No details")
        return result
    
    def closeEvent(self, event):
        event.accept() 
        
'''
Class may be replaced if the underlying interface is not opencv (e.g qt or ffmpeg or sth)
'''        
class VideoPlayerCV():
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
            Log.logInfo("STREAM NOT KNOWN")
            return False
        self._capture = OPENCV.getCapture();
        if not self._capture.open(self._file):
            Log.logError( "STREAM NOT OPENED")
            return False

        self.frameWidth= OPENCV.getFrameWidth()
        self.frameHeight= OPENCV.getFrameHeight()
        self.framecount= OPENCV.getFrameCount()
        self.fps= OPENCV.getFPS()


        #The problem: cv has a problem if it is BEHIND the last frame...
        #DO NOT USE;;;;; cap.set(cv2.cv.CV_CAP_PROP_POS_AVI_RATIO,1);
#         test = cap.set(cv2.cv.CV_CAP_PROP_POS_FRAMES,self.framecount-10)
#         if self.frameHeight< 10.0 or self.frameWidth < 10.0 or self.framecount < 10.0 or self.fps < 10.0:
#             return cap;
        self.totalTimeMilliSeconds = int(self.framecount/self.fps*1000)
        OPENCV.setFramePosition(0)
        Log.logInfo("STREAM OK")
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
        Log.logInfo("No more frames @"+str(self.framecount+1));
        return self.__getLastFrame(self._capture,self.framecount)

    #A test to paint on a frame. Has artefacts..
    def __markFrame(self,frame,nbr):
        cv2.putText(frame, "FB: {}".format(nbr),
        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)    


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
            print "Error -see log"
            Log.logException("Error 1")
            self.streamData = None  
            self.currentPath = OSTools().getHomeDirectory()    
        try:            
            self.player = VideoPlayerCV(filePath,self.streamData)
            self._initSliderThread()
            self.player.validate()
            
            self.__initSliderTicks()
            self.gui.enableControls(True)
            self.gui.getVideoWidget().setVideoRatio(self.streamData.getAspectRatio())
            self.gui.updateWindowTitle(OSTools().getFileNameOnly(filePath))
            self._asyncInitVideoViews()
           
        except:
            print "Error -see log:"
            Log.logException("Error 2")
            self.gui.updateWindowTitle(OSTools().getFileNameOnly(filePath))
            self._gotoFrame(0)
            self._showCurrentFrameInfo(0)
            if not OSTools().fileExists(filePath):
                msg = "File not found"
            else:
                msg = "Invalid file format!"
            
            self.gui.showWarning(msg)
            self.gui.enableControls(False)
    
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
                    Log.logInfo( "Start invalid: %s"%(cutEntry.getTimeString()))
                else:
                    block=[]
                    block.append(cutEntry)
                    print "Start ok:", cutEntry.getTimeString()
            else:
                if block:
                    Log.logInfo( "Stop:"+ cutEntry.getTimeString())
                    block.append(cutEntry)
                    spanns.append(block)
                    block=None
                else:
                   Log.logInfo( "Stop ignored:"+ cutEntry.getTimeString())
    
        for cutmarks in spanns:
            Log.logInfo('cut: %s -%s'%(cutmarks[0].getTimeString(),cutmarks[1].getTimeString()))
        
        src = self.player._file
        #need that without extension!
        self.cutAsync(src,path,spanns)
    
    #-- Menu handling end ---

    def cutAsync(self,srcPath,targetPath,spanns):
        worker = LongRunningOperation(self.__makeCuts,srcPath, targetPath, spanns)
        #worker = LongRunningOperation(self.__directCut,srcPath, targetPath, spanns)
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
            hasSucess = cutter.cutPart(t1, t2, index,slices)
            if not hasSucess:
                print"VC-Cut error" #TODO need a signal for error
                Log.logError("***Cutting failed***")
                return
        cutter.join()    
        
    '''
    new VCCutter API
    '''
    def __directCut(self,srcPath,targetPath,spanns):
   
        config = CuttingConfig(srcPath,targetPath)
        config.streamData = self.streamData
        config.reencode = self.exactcut
        config.messenger = self.gui._widgets.statusMessenger
        cutter = VCCutter(config)
        success = cutter.cut(spanns)
        print "CUT DONE:",success
    
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
        #self._dialStep = pos
        self._dialStep =math.copysign(1, pos)*round(math.exp(abs(pos/3.0) -1))
        #self._dialStep = 1
        ts=(1/self.player.fps)*2500
        #print "dial:",pos, " log:",self._dialStep
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
        self._frameSet = False
        
    #called by worker ...
    def _showFrame(self,aFrame):
        self._videoUI().showFrame(aFrame)
        x = self.player.getCurrentFrameNumber()
        self._showCurrentFrameInfo(x)
        
#     def _displayFrame(self,frameNumber):
#         self._videoUI().showFrame(self.player.getFrameAt(frameNumber))

    def _videoUI(self):
        return self.gui.getVideoWidget()

    
    def _showCurrentFrameInfo(self,frameNumber):
        timeinfo = long(self.player.getCurrentTimeMS())
        s= long(timeinfo/1000)
        ms= long(timeinfo%1000)
        ts= '{:02}:{:02}:{:02}.{:03}'.format(s // 3600, s % 3600 // 60, s % 60, ms)
        out = "<b>Frame:</b> %08d of %s Time: %s " %(frameNumber,self.player.framecount ,ts,)
        #TODO: Pass 3 values for 3 widgets....
        self.gui.showInfo(out)
        self.gui.syncSpinButton(frameNumber)

    
    def toggleVideoPlay(self):
        if self.streamData is None:
            return False
        if self._vPlayer is None:
            return self.__playVideo()
        
        return self.__stopVideo()

    def __playVideo(self):
        self._vPlayer = QTimer(self.gui)
        self._vPlayer.timeout.connect(self._grabNextFrame)
        #50 ms if 25 fps and 25 if 50fps
        fRate=(1/self.player.fps)*1250
        self._vPlayer.start(fRate)
        return True

    def __stopVideo(self):
        if self._vPlayer is not None:
            self._vPlayer.stop()
            self._vPlayer = None
        self._frameSet = False
        return False

    def _grabNextFrame(self):
        self._frameSet = True
        frame= self.player.getNextFrame()
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
            Log.logException("***Error in LongRunningOperation***")
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
        global Log
        Log = Logger()
        Log.logInfo('*** START ***')
        OSTools().setCurrentWorkingDirectory()
        argv = sys.argv
        app = QApplication(argv)
        app.setWindowIcon(getAppIcon())
        if len(argv)==1:
            WIN = MainFrame() #keep python reference!
        else:
            WIN = MainFrame(argv[1])  
        app.exec_()
        Log.logInfo('*** STOP ***')
        Log.logClose()
    except:
        Log.logException("Error in main:")      
        #traceback.print_exc(file=sys.stdout)

def stylesheet(self):
    return "QSlider{margin:1px;padding:1px;}" #to view the focus border
 
        
if __name__ == '__main__':
    sys.excepthook=handle_exception
    sys.exit(main())

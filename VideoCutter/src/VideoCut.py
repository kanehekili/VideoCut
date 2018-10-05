# -*- coding: utf-8 -*-
# 2014 kanehekili (mat.wegmann@gmail.com)
#

import sys, traceback, math
from PyQt5.QtCore import pyqtSignal
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication,QWidget

try:
    import cv2 #cv3
    cvmode=3
    print (cv2.getBuildInformation())
except ImportError:
    print ("OpenCV 3 not found,, expecting Version 2 now")
    try:
        from cv2 import cv #this is cv2!
        cvmode=2
    except ImportError:
        print ("OpenCV 2 not found")  
        app = QApplication(sys.argv)
        QtWidgets.QMessageBox.critical(None, "OpenCV",
            "Opencv2 or opencv3 must be installed to run VideoCut.")
        sys.exit(1)


from datetime import timedelta

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
    
if cvmode == 3:
    OPENCV=OpenCV3()
    print ("using CV3")
else:
    OPENCV=OpenCV2()
    print ("using CV2")    

class XMLAccessor():
    def __init__(self,path):
        self._path=path+".xml"
        
    def writeXML(self,videoCutEntries):
        rootElement = CT.Element("VC_Data")
        for cut in videoCutEntries:
            entry = CT.SubElement(rootElement,"Entry")
            entry.attrib["frame"]=str(cut.frameNumber) 
            entry.attrib["mode"]=str(cut.modeString)
        
        with open(self._path, 'wb') as aFile:
            #rootElement.write(aFile)
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
            

class CVImage(QtGui.QImage):
    def __init__(self,numpyArray):
        height, width, bytesPerComponent = numpyArray.shape
        bytesPerLine = bytesPerComponent * width;
        OPENCV.setColor(numpyArray)
        super(CVImage,self).__init__(numpyArray.data,width,height,bytesPerLine, QtGui.QImage.Format_RGB888)


class VideoWidget(QtWidgets.QFrame):
    """ A class for rendering video coming from OpenCV """
    
    def __init__(self, parent):
        QtWidgets.QFrame.__init__(self,parent)
        self._defaultHeight=576
        self._defaultWidth=720
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Expanding)
        changeBackgroundColor(self, "lightgray")       
        self._image = None
        self.imageRatio = 16.0/9.0
        self.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Sunken)
        self.setLineWidth(1)
   

    def paintEvent(self, event):

        QtWidgets.QFrame.paintEvent(self,event)
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
        
        painter = QtGui.QPainter(self)
        painter.drawImage(QtCore.QRectF(x, y,imgX,imgY), self._image)
        #painter.end()
  
        
    def sizeHint(self):
        return QtCore.QSize(self._defaultWidth,self._defaultHeight)

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
    
class VCSpinbox(QtWidgets.QSpinBox):
    def __init__(self,parent=None):
        QtWidgets.QSpinBox.__init__(self,parent)
        
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
        self.ui_Slider =  QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.ui_Slider.setFocusPolicy(QtCore.Qt.StrongFocus)
        #contribution:
        self.ui_Slider.setStyleSheet(stylesheet(self))
        
        self.ui_Slider.setMinimum(0)
        self.ui_Slider.setMaximum(self.SLIDER_RESOLUTION)
        self.ui_Slider.setToolTip("Video track")
        self.ui_Slider.setTickPosition(QtWidgets.QSlider.TicksAbove)
        self.ui_Slider.setTickInterval(0)
        
        self.ui_Dial = QtWidgets.QDial(self)
        
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
        
        
        self.ui_InfoLabel = QtWidgets.QLabel(self)
        #self.ui_InfoLabel.setMargin(4)
        #changeBackgroundColor(self.ui_InfoLabel , "lightblue")
        self.ui_InfoLabel.setStyleSheet("QLabel { border: 1px solid darkgray; border-radius: 3px; background: lightblue} ");
        self.ui_InfoLabel.setText("")
        self.ui_InfoLabel.setToolTip("Infos about the video position")
        
        self.ui_StatusLabel= QtWidgets.QLabel(self)
        self.ui_StatusLabel.setStyleSheet("QLabel { border: 1px solid darkgray; border-radius: 3px; background: lightgreen} ");
        
        self.ui_List = self.__createListWidget()
        
        #self._listSplitter = QSplitter() ->add as widget...+QVBoxLayout
        #self._listSplitter.addWidget(iconList)
        
        #status bar
        self.statusbar = QtWidgets.QStatusBar(self)
        self.statusbar.setStyleSheet("QStatusBar { border: 1px solid darkgray; border-radius: 3px; } ");
        self.statusbar.setSizeGripEnabled(True)
        self.statusbar.showMessage("Idle")
        self.statusbar.addPermanentWidget(self.__createProgressBar())
        self.setLayout(self.makeGridLayout())
        self.adjustSize()

    def makeGridLayout(self):
        gridLayout = QtWidgets.QGridLayout()
        self.ui_List.setSizePolicy(QtWidgets.QSizePolicy.Preferred,QtWidgets.QSizePolicy.Expanding)
        self.ui_List.setMaximumWidth(SIZE_ICON*2.6)
        gridLayout.addWidget(self.ui_List,0,0,5,1)
        #from row,from col, rowSpan, columnSpan
       
        gridLayout.addWidget(self.ui_VideoFrame,0,1,4,-1);
        gridLayout.addWidget(self.ui_GotoField,4,1,1,2)
        gridLayout.addWidget(self.ui_InfoLabel,4,3,1,7)
        #gridLayout.addWidget(self.ui_CB_Reencode,4,11,1,-1)??exact cut,target,experimaenta
        gridLayout.addWidget(self.ui_StatusLabel,4,10,1,-1)
        gridLayout.addWidget(self.ui_Slider,5,0,1,11)
        gridLayout.addWidget(self.ui_Dial,5,11,1,-1)
        gridLayout.addWidget(self.statusbar,6,0,1,12)
        
        gridLayout.setRowStretch(1, 1)

        return gridLayout
                             

    def makeBoxLayout(self):
        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.ui_VideoFrame)
        vbox.addWidget(self.ui_InfoLabel );
        
        slidehbox = QtWidgets.QHBoxLayout()
        slidehbox.addWidget(self.ui_Slider)
        slidehbox.addWidget(self.ui_Dial)

        midHBox = QtWidgets.QHBoxLayout()
        midHBox.addWidget(self.ui_List)
        self.ui_List.setSizePolicy(QtWidgets.QSizePolicy.Minimum,QtWidgets.QSizePolicy.Expanding)
        midHBox.addLayout(vbox)
        
        mainVBox = QtWidgets.QVBoxLayout()
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
        
        item = QtWidgets.QListWidgetItem()
        item.setSizeHint(QtCore.QSize(SIZE_ICON,self.ITEM_HEIGHT))
        img = CVImage(frame).scaled(self.ui_VideoFrame.imageRatio*SIZE_ICON, SIZE_ICON)
        pix = QtGui.QPixmap.fromImage(img)
        item.setIcon(QtGui.QIcon(pix))
        if cutEntry.isStartMode():
            item.setBackground(QtGui.QColor(224,255,224))
        else:
            item.setBackground(QtGui.QColor(255,224,224))
        self.ui_List.insertItem(rowIndex,item)

        text = "%s <br> F: %s<br> T: %s" %(cutEntry.modeString,str(cutEntry.frameNumber),str(cutEntry.getTimeString()))
        marker = QtWidgets.QLabel(text)
        marker.setWordWrap(False)
        marker.layout()
        
        self.ui_List.setItemWidget(item,marker)
        self.ui_List.setIconSize(QtCore.QSize(SIZE_ICON,SIZE_ICON)) #Forces an update!
        self.ui_List.setCurrentItem(item)
        
 
    def hookEvents(self,aVideoController):
        self.__videoController=aVideoController #for menu callbacks
        self.ui_Slider.valueChanged.connect(aVideoController.sliderMoved)
        
        self.ui_Dial.valueChanged.connect(aVideoController.dialChanged)
        self.ui_Dial.sliderReleased.connect(self.__resetDial)
        
        #self.ui_GotoField.editingFinished.connect(self.__gotoFrame)
        self.ui_GotoField.valueChanged.connect(self.__gotoFrame)
        
        #self.ui_CB_Reencode.stateChanged.connect(aVideoController.setExactCut)
        
        self.statusMessenger = StatusDispatcher()
        self.statusMessenger.signal.connect(self.showStatusMessage)
       
        self._hookListActions()
    
    def syncSpinButton(self,frameNbr):
        self.ui_GotoField.blockSignals(True)
        self.ui_GotoField.setValue(frameNbr)
        self.ui_GotoField.blockSignals(False)
    
    def keyReleaseEvent(self,event):
        self.__resetDial()
     
    def _hookListActions(self):
        #TOO bad-the list model -should be here... 
        rmAction = QtWidgets.QAction(QtGui.QIcon('icons/close-x.png'), 'Delete', self)
        rmAction.triggered.connect(self._removeMarker)
        rmAllAction = QtWidgets.QAction(QtGui.QIcon('icons/clear-all.png'), 'Remove all', self)
        rmAllAction.triggered.connect(self.purgeMarker)
        self.gotoAction = QtWidgets.QAction(QtGui.QIcon('icons/go-next.png'), 'Goto', self)
        self.gotoAction.triggered.connect(self._gotoFromMarker)
  
        #menus      
        self.ui_List.customContextMenuRequested.connect(self._openListMenu)
        self._listMenu = QtWidgets.QMenu()
        self._listMenu.addAction(self.gotoAction)
        self._listMenu.addSeparator()
        self._listMenu.addAction(rmAction)
        self._listMenu.addAction(rmAllAction)

        
 
    def __resetDial(self):
        self.ui_Dial.setProperty("value", 0)

    def __gotoFrame(self,value):
        self.__videoController._gotoFrame(value)

    def __createProgressBar(self):
        self.progressBar = QtWidgets.QProgressBar(self)
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
        iconList=QtWidgets.QListWidget()
        iconList.setAlternatingRowColors(True)
        iconList.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        iconList.setStyleSheet("QListView{outline:none;} QListWidget::item:selected { background: #28D9FF; } ")#that text color seems not to work!
        fontM = QtGui.QFontMetrics(iconList.font())
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

        

class MainFrame(QtWidgets.QMainWindow):
    MODE_ACTIVE=2
    signalActive=pyqtSignal()
    
    def __init__(self,aPath=None):
        self.__initalMode=0
        
        super(MainFrame, self).__init__()
        self.setWindowIcon(getAppIcon())
        self.settings = SettingsModel(self)
        self._videoController = VideoControl(self)
        self._widgets = self.initUI()
        self._widgets.hookEvents(self._videoController)
        self.settings.update()
        
        self.centerWindow()
        self.show() 
        if aPath is not None:
            self._videoController.setFile(aPath)
        else:
            self.getVideoWidget().showFrame(None)

    
    def initUI(self):
        
        #self.statusBar().showMessage('Ready')
         
        self.exitAction = QtWidgets.QAction(QtGui.QIcon('icons/window-close.png'), 'Exit', self)
        self.exitAction.setShortcut('Ctrl+Q')
        self.exitAction.triggered.connect(QApplication.quit)
        
        self.loadAction = QtWidgets.QAction(QtGui.QIcon('./icons/loadfile.png'), 'Load Video', self)
        self.loadAction.setShortcut('Ctrl+L')
        self.loadAction.triggered.connect(self.loadFile)


        self.startAction = QtWidgets.QAction(QtGui.QIcon('./icons/start-icon.png'), 'Set start marker', self)
        self.startAction.setShortcut('Ctrl+G')
        self.startAction.triggered.connect(self._videoController.addStartMarker)

        self.stopAction = QtWidgets.QAction(QtGui.QIcon('./icons/stop-red-icon.png'), 'Set stop marker', self)
        self.stopAction.setShortcut('Ctrl+H')
        self.stopAction.triggered.connect(self._videoController.addStopMarker)
        
        self.saveAction= QtWidgets.QAction(QtGui.QIcon('./icons/save-as-icon.png'), 'Save the video', self)
        self.saveAction.setShortcut('Ctrl+S')
        self.saveAction.triggered.connect(self.saveVideo)
        
        self.infoAction = QtWidgets.QAction(QtGui.QIcon('./icons/info.png'), 'Codec info', self)
        self.infoAction.setShortcut('Ctrl+I')
        self.infoAction.triggered.connect(self.showCodecInfo)
        
        self.playAction = QtWidgets.QAction(QtGui.QIcon('./icons/play.png'), 'Play video', self)
        self.playAction.setShortcut('Ctrl+P')
        self.playAction.triggered.connect(self.playVideo)
        
        '''
        the conversion menues
        '''
        #self.convertToMP4 = QtWidgets.QAction(QtGui.QIcon('./icons/stop-red-icon.png'),"Convert to mp4",self)
        self.convertToMP4 = QtWidgets.QAction("Convert to mp4",self)
        self.convertToMP4.setCheckable(True)
#         self.selectContainer = QtWidgets.QAction(QtGui.QIcon('./icons/stop-red-icon.png'),"change to a different container",self)
#         self.extractMP3 = QtWidgets.QAction(QtGui.QIcon('./icons/stop-red-icon.png'),"Extract MP3",self)
#         self.switchAudio = QtWidgets.QAction(QtGui.QIcon('./icons/stop-red-icon.png'),"Swtich audio",self)
        self.mediaSettings= QtWidgets.QAction(QtGui.QIcon('./icons/settings.png'),"Output settings",self)
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
    '''
    overwriting event seems to be the only way to find out WHEN there is the first
    time where we could display a dialog. So if Show && Activated have arrived
    the MainFrame sends a signal to whom it may concern...
    '''
    def event(self,event):
        if self.__initalMode < self.MODE_ACTIVE:
            if event.type() == QtCore.QEvent.Show or event.type() == QtCore.QEvent.WindowActivate:
                self.__initalMode+=1
                if self.isActivated():
                    self.signalActive.emit()
        return super(MainFrame,self).event(event)
    
    def isActivated(self):
        return self.__initalMode == self.MODE_ACTIVE
    
    def centerWindow(self):
        frameGm = self.frameGeometry()
        screen = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
        centerPoint = QApplication.desktop().screenGeometry(screen).center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())        

    
    def updateWindowTitle(self,text):
        #qText = QtCore.QString(text.decode('utf-8'))
        #qText = text.decode('utf-8')
        self.setWindowTitle("VideoCut - "+text)
     
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
        pad ='\t'
        QtWidgets.QMessageBox.warning(self,"Warning!",aMessage+pad)
    
    def enableControls(self,enable):
        self._widgets.ui_Dial.setEnabled(enable)
        self._widgets.ui_Slider.setEnabled(enable)
            
                            
    #-------- ACTIONS ----------
    def loadFile(self):
        initalPath = self._videoController.getTargetFile()
        result = QtWidgets.QFileDialog.getOpenFileName(parent=self, directory=initalPath, caption="Load Video");
        if result:
            fn = self.__encodeQString(result)
            self._widgets.clearMarkerList()
            self._videoController.clearVideoCutEntries()
            self._videoController.setFile(fn)#encode error: str(result)
            
    def saveVideo(self):
        initalPath = self._videoController.getTargetFile()
        #qText = initalPath.decode('utf-8')
        qText = initalPath
        result = QtWidgets.QFileDialog.getSaveFileName(parent=self, directory=qText, caption="Save Video");
        if result:
            fn = self.__encodeQString(result)
            self._widgets.showBusy()
            self._videoController.saveVideo(fn)
    
    def __encodeQString(self,stringTuple):
        text = stringTuple[0]
        #return unicode(qString).encode('utf-8')
        #return text.encode('utf-8')
        return text
    
    def openMediaSettings(self):
        dlg= SettingsDialog(self,self.settings)
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
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowModality(QtCore.Qt.WindowModal)
        dlg.setWindowTitle("Video Infos")
        layout = QtWidgets.QVBoxLayout(dlg)
        label = QtWidgets.QLabel(text)
        label.sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        label.setSizePolicy(label.sizePolicy)
        label.setMinimumSize(QtCore.QSize(450, 40))
        layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        layout.addWidget(label)
        return dlg

    def getErrorDialog(self,text,infoText,detailedText):
        dlg = DialogBox(self)
        dlg.setIcon(QtWidgets.QMessageBox.Warning)
        dlg.setWindowModality(QtCore.Qt.WindowModal)
        dlg.setWindowTitle("Error")
        dlg.setText(text)
        dlg.setInformativeText(infoText)
        dlg.setDetailedText(detailedText)
        dlg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        return dlg

class SettingsModel():
    def __init__(self,mainframe):
        #keep flags- save them later
        self.experimental=False
        self.selectedContainer="mp4" 
        self.containerList=["mp4","mpg","mkv","flv","m2t"] 
        self.reencoding=False
        self.mainFrame=mainframe
    
    def update(self):
        cutmode="Fast"
        mode="FFMPEG"
        if self.experimental:
            mode="REMUX"
        if self.reencoding:
            cutmode="Exact"
        self.mainFrame._widgets.ui_StatusLabel.setText(cutmode+" / "+mode)

class SettingsDialog(QtWidgets.QDialog):

    def __init__(self,parent,model):
        """Init UI."""
        super(SettingsDialog, self).__init__(parent)
        self.model=model
        self.init_ui()

    def init_ui(self):
        self.setWindowModality(QtCore.Qt.WindowModal)
        self.setWindowTitle("Settings")


        outBox = QtWidgets.QVBoxLayout()
        #outBox.addStretch(1)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        frame1 =  QtWidgets.QFrame()
        frame1.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Sunken)
        frame1.setLineWidth(1)
       
        frame2 =  QtWidgets.QFrame()
        frame2.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Sunken)
        frame2.setLineWidth(1)
       
        encodeBox = QtWidgets.QVBoxLayout(frame1)
        self.check_reencode =  QtWidgets.QCheckBox("Reencode (Slow!)")
        self.check_reencode.setToolTip("Force exact cut. Makes it real slow!")
        self.check_reencode.setChecked(self.model.reencoding)
        #connect
        self.check_reencode.stateChanged.connect(self.on_reencodeChanged)
        
        self.combo = QtWidgets.QComboBox()
        for item in self.model.containerList:
            self.combo.addItem(item, None)
        
        self.combo.setEnabled(self.model.reencoding)
        
        self.combo.setCurrentText(self.model.selectedContainer)
        self.combo.currentTextChanged.connect(self.on_combobox_selected)
        #we want audio as well?
        self.exRemux = QtWidgets.QCheckBox("Experimental")
        self.exRemux.setToolTip("Uses the remux code instead of default ffmpeg commandline")
        self.exRemux.setChecked(self.model.experimental)
        self.exRemux.stateChanged.connect(self.on_experimentalChanged)
        
        encodeBox.addWidget(self.check_reencode)
        encodeBox.addWidget(self.combo)
        
        expoBox = QtWidgets.QVBoxLayout(frame2)
        expoBox.addWidget(self.exRemux)
        
        outBox.addWidget(frame1)
        outBox.addWidget(frame2)
        self.setLayout(outBox)
        #make it wider...
        self.setMinimumSize(400, 0)
        
    def on_combobox_selected(self,value):
        self.model.selectedContainer=value
        self.model.update()
    
    def on_reencodeChanged(self,reencode):
        self.model.reencoding= QtCore.Qt.Checked==reencode
        self.combo.setEnabled(self.model.reencoding)
        self.model.update()
        
    def on_experimentalChanged(self,isExperimental):
        self.model.experimental= QtCore.Qt.Checked==isExperimental
        self.model.update()    
        
class DialogBox(QtWidgets.QMessageBox): #subclassed for reasonable sizing 

    def __init__(self, *args, **kwargs):            
        super(DialogBox, self).__init__(*args, **kwargs)

    # We only need to extend resizeEvent, not every event.
    def resizeEvent(self, event):

        result = super(DialogBox, self).resizeEvent(event)

        details_box = self.findChild(QtWidgets.QTextEdit)
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
            print ("STREAM NOT KNOWN")
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
        return QtCore.QSize(self.frameWidth,self.frameHeight)
    
    def getCurrentFrameTime(self):
        if not self.isValid():
            timeSlot=0
        else:
            timeSlot = OPENCV.getTimePosition()    

        try:    
            td = timedelta(milliseconds=timeSlot)
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
class VideoControl(QtCore.QObject):
    def __init__(self,mainFrame):
        #super(VideoControl, self).__init__()
        QtCore.QObject.__init__(self)
        self.player = None
        self.gui = mainFrame
        self._frameSet=False
        self._initTimer()
        self.videoCuts=[]
        self.currentPath = OSTools().getHomeDirectory()#//TODO get a Video dir
        self.streamData = None
        self._vPlayer = None
        
        mainFrame.signalActive.connect(self.displayWarningMessage)
        self.lastError=None
        mainFrame.signalActive.connect(self.displayWarningMessage)
        self.lastError=None

    def _initTimer(self):
        self._timer = QtCore.QTimer(self.gui)
        self._timer.timeout.connect(self._displayAutoFrame)

    
    def getTargetFile(self):
        if self.streamData is not None:
            return self.currentPath+"."+self.streamData.getTargetExtension()

        return self.currentPath
     
    def displayWarningMessage(self):
        if self.lastError is None:
            return
        self.gui.showWarning(self.lastError)
        self.lastError=None
        
    #-- Menu handling ---    
    def setFile(self,filePath):
        if self.player is not None:
            self.player.close()
            self.videoCuts=[]
        try:
            self.streamData = FFStreamProbe(filePath)
            self.currentPath = OSTools().getPathWithoutExtension(filePath); 
        except: 
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
            print ("Error -see log")
            Log.logException("Error 2")
            self.gui.updateWindowTitle(OSTools().getFileNameOnly(filePath))
            self._gotoFrame(0)
            self._showCurrentFrameInfo(0)
            if not OSTools().fileExists(filePath):
                self.lastError = "File not found"
            else:
                self.lastError = "Invalid file format"
            
            self._videoUI().showFrame(None)
            self.gui.enableControls(False)
            if self.gui.isActivated():
                self.displayWarningMessage()
    
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
        QtCore.QTimer.singleShot(10,self._grabNextFrame)
        QtCore.QTimer.singleShot(150, self.restoreVideoCuts)

    def restoreVideoCuts(self):
        self.sliderThread.wait() #sync with the worker
        
        try:
            cutList=XMLAccessor(self.currentPath).readXML()
        except Exception as error:
            print(error)
            return  
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
                    print ("Start ok:", cutEntry.getTimeString())
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
        settings = self.gui.settings
        targetContainer = settings.selectedContainer
        isExperimental =settings.experimental
        isReeincoding = settings.reencoding
        if isExperimental:
            worker = LongRunningOperation(self.__directCut,srcPath, targetPath, spanns,settings)
        else:
            worker = LongRunningOperation(self.__makeCuts,srcPath, targetPath, spanns,settings)
        worker.signal.connect(self.gui.stopProgress)
        #start the worker thread. 
        worker.startOperation()  


    def __makeCuts(self,srcPath,targetPath,spanns,settings):
        config = CuttingConfig(srcPath,targetPath)
        config.streamData = self.streamData
        #TODO: 
        #config.targetContainer = settings.selectedContainer
        config.reencode = settings.reencoding
        
        config.messenger = self.gui._widgets.statusMessenger
        cutter = FFMPEGCutter(config)
        
        cutter.ensureAvailableSpace()
        slices = len(spanns)
        for index, cutmark in enumerate(spanns):
            t1=cutmark[0].timePos
            t2 = cutmark[1].timePos
            hasSucess = cutter.cutPart(t1, t2, index,slices)
            if not hasSucess:
                print("VC-Cut error") #TODO need a signal for error
                Log.logError("***Cutting failed***")
                return
        cutter.join()    
        
    '''
    new VCCutter API
    '''
    def __directCut(self,srcPath,targetPath,spanns,settings):
   
        config = CuttingConfig(srcPath,targetPath)
        config.streamData = self.streamData
        config.messenger = self.gui._widgets.statusMessenger
        
        #TODO
        #config.targetContainer = settings.selectedContainer
        config.reencode = settings.reencoding
        
        cutter = VCCutter(config)
        success = cutter.cut(spanns)
        print ("CUT DONE:",success)
    
    def _initSliderThread(self):
        
        self.sliderThread = Worker(self.player.getFrameAt)
        self.sliderThread.signal.connect(self._processFrame)
    
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
            return
        if not self._frameSet: 
            frameNumber = round(self.player.framecount/LayoutWindow.SLIDER_RESOLUTION*pos,0)
            self.__dispatchShowFrame(frameNumber)
        self._frameSet=False

    #display Frame with syncing the slider pos. 
    def _gotoFrame(self,frameNumber=0):
        if self.player is None:
            return;
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
        self._dialStep =math.copysign(1, pos)*round(math.exp(abs(pos/3.0) -1))
        ts=(1/self.player.fps)*2500
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
    def _processFrame(self):
        frm = self.sliderThread.result
        self._showFrame(frm)
        
    def _showFrame(self,aFrame):
        self._videoUI().showFrame(aFrame)
        x = self.player.getCurrentFrameNumber()
        self._showCurrentFrameInfo(x)
        
    def _videoUI(self):
        return self.gui.getVideoWidget()

    
    def _showCurrentFrameInfo(self,frameNumber):
        timeinfo = self.player.getCurrentTimeMS()
        s= int(timeinfo/1000)
        ms= int(timeinfo%1000)
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
        self._vPlayer = QtCore.QTimer(self.gui)
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
    signal = pyqtSignal()
    result=None
    def __init__(self, func):
        super(Worker, self).__init__()
        self.func = func
        self.fbnr=0
        #self._dialStep = 1
    def run(self):
        current = -1;
        while self.fbnr != current:
            current = self.fbnr
            self.result = self.func(current)
            self.signal.emit()

    def __del__(self):
        self.wait()

    def showFrame(self,frameNumber):
        self.fbnr=frameNumber
        self.start()
        
''' Long running operations for actions that do not draw or paint '''        
class LongRunningOperation(QtCore.QThread):
    signal = pyqtSignal() 
    def __init__(self, func, *args):
        QtCore.QThread.__init__(self)
        self.function = func
        self.arguments = args

    def run(self):
        try:
            self.function(*self.arguments)
        except:
            Log.logException("***Error in LongRunningOperation***")
        finally:
            self.signal.emit()

        
    def startOperation(self):
        self.start() #invokes run - process pending QT events
        sleep(0.5)
        QtCore.QCoreApplication.processEvents()

class StatusDispatcher(QtCore.QObject):
    signal=pyqtSignal(str)
    def __init__(self):
        QtCore.QObject.__init__(self)
    def say(self,aString):
        self.signal.emit(aString)

WIN=None

def handle_exception(exc_type, exc_value, exc_traceback):
    """ handle all exceptions """
    if WIN is not None:
        infoText = str(exc_value)
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
        traceback.print_exc(file=sys.stdout)

def stylesheet(self):
    #return "QSlider{margin:1px;padding:1px;background:yellow}" #to view the focus border QSlider:focus{border: 1px solid  #000}
    #No focus and no ticks are available using stylesheets.
    return """
        QSlider:horizontal{
            margin:1px;padding:1px;
        }
        
        QSlider:focus{border: 1px dotted #bbf}
        
        QSlider::groove:horizontal {
        border: 1px solid #bbb;
        background: white;
        height: 8px;
        border-radius: 4px;
        }
        
        QSlider::sub-page:horizontal {
        background: qlineargradient(x1: 0, y1: 0,    x2: 0, y2: 1,
            stop: 0 #66e, stop: 1 #bbf);
        background: qlineargradient(x1: 0, y1: 0.2, x2: 1, y2: 1,
            stop: 0 #bbf, stop: 1 #55f);
        border: 1px solid #777;
        height: 10px;
        border-radius: 4px;
        }
        
        QSlider::add-page:horizontal {
        background: #fff;
        border: 1px solid #777;
        height: 10px;
        border-radius: 4px;
        }
        
        QSlider::handle:horizontal {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #eee, stop:1 #ccc);
        border: 1px solid #777;
        width: 13px;
        margin: -4px 0;
        border-radius: 4px;
        }
        
        QSlider::handle:horizontal:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #fff, stop:1 #ddd);
        border: 1px solid #444;
        border-radius: 4px;
        }
        
        QSlider::sub-page:horizontal:disabled {
        background: #bbb;
        border-color: #999;
        }
        
        QSlider::add-page:horizontal:disabled {
        background: #eee;
        border-color: #999;
        }
        
        QSlider::handle:horizontal:disabled {
        background: #eee;
        border: 1px solid #aaa;
        border-radius: 4px;
        }"""
 
        
if __name__ == '__main__':
    sys.excepthook=handle_exception
    sys.exit(main())

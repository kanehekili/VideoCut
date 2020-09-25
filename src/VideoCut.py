#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 2014-2020 kanehekili (mat.wegmann@gmail.com)
#

import sys, traceback, math
import configparser
from PyQt5.QtCore import pyqtSignal
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QWidget
import json
from PyQt5.Qt import Qt

try:
    import cv2  # cv3
    cvmode = 3
    # print (cv2.getBuildInformation())
except ImportError:
    print ("OpenCV 3 not found,, expecting Version 2 now")
    try:
        from cv2 import cv  # this is cv2!
        cvmode = 2
    except ImportError:
        print ("OpenCV 2 not found")  
        app = QApplication(sys.argv)
        QtWidgets.QMessageBox.critical(None, "OpenCV",
            "Opencv2 or opencv3 must be installed to run VideoCut.")
        sys.exit(1)

from datetime import timedelta

from FFMPEGTools import FFMPEGCutter, FFStreamProbe, CuttingConfig, OSTools, Logger, VCCutter, FORMATS
import FFMPEGTools 
from time import sleep, time
import xml.etree.cElementTree as CT

# sizes ..
SIZE_ICON = 80
ITEM_ROW_COUNT = 3


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


class XMLAccessor():

    def __init__(self, path):
        self._path = path + ".xml"
        
    def writeXML(self, videoCutEntries):
        rootElement = CT.Element("VC_Data")
        for cut in videoCutEntries:
            entry = CT.SubElement(rootElement, "Entry")
            entry.attrib["frame"] = str(cut.frameNumber) 
            entry.attrib["mode"] = str(cut.modeString)
        
        with open(self._path, 'wb') as aFile:
            CT.ElementTree(rootElement).write(aFile)

    def readXML(self):
        cutEntries = []
        if not OSTools().fileExists(self._path):
            return cutEntries
        with open(self._path, 'r') as xmlFile:
            xmlData = xmlFile.read()
            
        root = CT.fromstring(xmlData)
        for info in root:
            frameNbr = float(info.get('frame'))
            markerType = info.get('mode')
            entry = VideoCutEntry(frameNbr, 0, markerType)
            cutEntries.append(entry)
        
        return cutEntries

    def clear(self):
        OSTools().removeFile(self._path)

# class ImageGeometry():
#     def __init__(self,rotation,numpyArray):
#        self.height, self.width, bytesPerComponent = numpyArray.shape 
#        self.cvrotate = self.getRotation(rotation)
#        if self.cvrotate > 0:
#             center = (width / 2, height / 2) 
#             dst= cv2.rotate(numpyArray,self.cvrotate)
#             self.height, self.width, bytesPerComponent = dst.shape
#        
#        self.bytesPerLine = bytesPerComponent * self.width 
#        
#     def getRotation(self,rotation):
#         if rotation > 0 and rotation < 180:
#             return cv2.ROTATE_90_CLOCKWISE
#         if rotation > 180:
#             return cv2.ROTATE_90_COUNTERCLOCKWISE
#         if rotation == 180:
#             return cv2.ROTATE_180;
#         return 0;


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
        return self.ROTATION;
#         if self.ROTATION > 0 and self.ROTATION < 180:
#             return cv2.ROTATE_90_CLOCKWISE
#         
#         if self.ROTATION > 180:
#             return cv2.ROTATE_90_COUNTERCLOCKWISE
#         return -1


class VideoWidget(QtWidgets.QFrame):
    """ A class for rendering video coming from OpenCV """
    
    def __init__(self, parent):
        QtWidgets.QFrame.__init__(self, parent)
        self._defaultHeight = 576
        self._defaultWidth = 720
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        #TODO changeBackgroundColor(self, "lightgray")       
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
            with open('icons/video_clapper.png', 'rb') as filedata:
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


class VideoCutEntry():
    MODE_START = "Start"
    MODE_STOP = "Stop"

    def __init__(self, frameNbr, timepos, markerType):
        self.frameNumber = frameNbr;
        self.modeString = markerType
        self.timePos = timepos
        
    def isStartMode(self):
        return self.MODE_START == self.modeString    
    
    def getTimeString(self):
        t1 = str(self.timePos).split('.')
        if len(t1) < 2:
            return t1[0]
        t1[1] = t1[1][:3]
        return '.'.join(t1)

    
class VCSpinbox(QtWidgets.QSpinBox):

    def __init__(self, parent=None):
        QtWidgets.QSpinBox.__init__(self, parent)
        
    def keyPressEvent(self, keyEvent):
        if (keyEvent.key() == QtCore.Qt.Key_Enter) or (keyEvent.key() == QtCore.Qt.Key_Return):
            super(VCSpinbox, self).keyPressEvent(keyEvent)
        else:
            self.blockSignals(True)
            super(VCSpinbox, self).keyPressEvent(keyEvent)
            self.blockSignals(False)

        
# widget that contains the widgets
class LayoutWindow(QWidget):
    SLIDER_RESOLUTION = 1000
    DIAL_RESOLUTION = 50 

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.initWidgets()

    def initWidgets(self):
        
        self.ui_VideoFrame = VideoWidget(self)
        self.ui_Slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.ui_Slider.setFocusPolicy(QtCore.Qt.StrongFocus)
        # contribution:
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

        self.ui_GotoField = VCSpinbox(self)
        self.ui_GotoField.setValue(1)
        self.ui_GotoField.setToolTip("Goto Frame")
        
        self.ui_InfoLabel = QtWidgets.QLabel(self)
        self.ui_InfoLabel.setStyleSheet("QLabel { border: 1px solid darkgray; border-radius: 3px; color: black; background: lightblue} ");
        self.ui_InfoLabel.setText("")
        self.ui_InfoLabel.setToolTip("Infos about the video position")
        
        self.ui_CutModeLabel = QtWidgets.QLabel(self)
        self.ui_CutModeLabel.setStyleSheet("QLabel { border: 1px solid darkgray; border-radius: 3px; color: black; background: lightgreen} ");
        self.ui_CutModeLabel.setAlignment(QtCore.Qt.AlignCenter)
        
        self.ui_BackendLabel = QtWidgets.QLabel(self)
        self.ui_BackendLabel.setStyleSheet("QLabel { border: 1px solid darkgray; border-radius: 3px; color: black; background: lightgreen} ");
        self.ui_BackendLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.statusBox = QtWidgets.QHBoxLayout()
        self.statusBox.addWidget(self.ui_CutModeLabel)
        self.statusBox.addWidget(self.ui_BackendLabel)
        
        self.ui_List = self.__createListWidget()
        
        # self._listSplitter = QSplitter() ->add as widget...+QVBoxLayout
        # self._listSplitter.addWidget(iconList)
        
        # status bar
        self.statusbar = QtWidgets.QStatusBar(self)
        self.statusbar.setStyleSheet("QStatusBar { border: 1px inset darkgray; border-radius: 3px;}QStatusBar::item {border-radius: 3px;} ");
        self.statusbar.setSizeGripEnabled(False)
        self.statusbar.showMessage("Idle")
        self.statusbar.addPermanentWidget(self.__createProgressBar())
        self.buttonStop = QtWidgets.QToolButton(self)
        self.buttonStop.setIcon(QtGui.QIcon('./icons/window-close.png'))
        self.buttonStop.setIconSize(QtCore.QSize(20, 20))
        self.buttonStop.setVisible(False)
        self.buttonStop.setToolTip("Stop processing")
        self.statusbar.addPermanentWidget(self.buttonStop, 0)
        self.setLayout(self.makeGridLayout())
        self.adjustSize()

    def makeGridLayout(self):
        gridLayout = QtWidgets.QGridLayout()
        self.ui_List.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        self.ui_List.setMaximumWidth(round(SIZE_ICON * 2.6))
        gridLayout.addWidget(self.ui_List, 0, 0, 5, 1)
        # from row,from col, rowSpan, columnSpan
        gridLayout.addWidget(self.ui_VideoFrame, 0, 1, 4, -1);
        gridLayout.addWidget(self.ui_GotoField, 4, 1, 1, 2)
        gridLayout.addWidget(self.ui_InfoLabel, 4, 3, 1, 7)
        gridLayout.addLayout(self.statusBox, 4, 10, 1, -1)
        gridLayout.addWidget(self.ui_Slider, 5, 0, 1, 11)
        gridLayout.addWidget(self.ui_Dial, 5, 11, 1, -1)
        gridLayout.addWidget(self.statusbar, 6, 0, 1, 12)
        
        gridLayout.setRowStretch(1, 1)

        return gridLayout

    def makeBoxLayout(self):
        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.ui_VideoFrame)
        vbox.addWidget(self.ui_InfoLabel);
        
        slidehbox = QtWidgets.QHBoxLayout()
        slidehbox.addWidget(self.ui_Slider)
        slidehbox.addWidget(self.ui_Dial)

        midHBox = QtWidgets.QHBoxLayout()
        midHBox.addWidget(self.ui_List)
        self.ui_List.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        midHBox.addLayout(vbox)
        
        mainVBox = QtWidgets.QVBoxLayout()
        mainVBox.addLayout(midHBox)
        mainVBox.addStretch(1)
        mainVBox.addLayout(slidehbox)
        return mainVBox
    
    def showInfo(self, text):
        self.ui_InfoLabel.setText(text)
    
    def showStatusMessage(self, text):
        self.statusbar.showMessage(text)
    
    def setDialResolution(self, resolution):
        self.ui_Dial.setMinimum(round(-resolution / 2))
        self.ui_Dial.setMaximum(round(resolution / 2))

    def syncSliderPos(self, pos):
        self.ui_Slider.setSliderPosition(pos)
    
    def setSliderTicks(self, ticks):
        self.ui_Slider.setSingleStep(ticks)
        self.ui_Slider.setPageStep(ticks * 2)
    
    def setGotoFieldMaximum(self, count):
        self.ui_GotoField.setMaximum(count)
    
    def clearVideoFrame(self):
        self.ui_VideoFrame.showFrame(None)
 
    # ## Marks 
    def addCutMark(self, frame, cutEntry, rowIndex):
        
        item = QtWidgets.QListWidgetItem()
        item.setSizeHint(QtCore.QSize(SIZE_ICON, self.ITEM_HEIGHT))
        img = CVImage(frame).scaled(int(self.ui_VideoFrame.imageRatio * SIZE_ICON), SIZE_ICON)
        pix = QtGui.QPixmap.fromImage(img)
        item.setIcon(QtGui.QIcon(pix))
        #TODO: Respect theme
        if cutEntry.isStartMode():
            item.setBackground(QtGui.QColor(224, 255, 224))
        else:
            item.setBackground(QtGui.QColor(255, 224, 224))
        self.ui_List.insertItem(rowIndex, item)

        text = "%s <br> F: %s<br> T: %s" % (cutEntry.modeString, str(cutEntry.frameNumber), str(cutEntry.getTimeString()))
        marker = QtWidgets.QLabel(text)
        marker.setStyleSheet("QLabel {color:black;}")
        marker.setWordWrap(False)
        marker.layout()
        
        self.ui_List.setItemWidget(item, marker)
        self.ui_List.setIconSize(QtCore.QSize(SIZE_ICON, SIZE_ICON))  # Forces an update!
        self.ui_List.setCurrentItem(item)
 
    def hookEvents(self, aVideoController):
        self.__videoController = aVideoController  # for menu callbacks
        self.ui_Slider.valueChanged.connect(aVideoController.sliderMoved)
        
        self.ui_Dial.valueChanged.connect(aVideoController.dialChanged)
        self.ui_Dial.sliderReleased.connect(self.__resetDial)

        self.ui_GotoField.valueChanged.connect(self.__gotoFrame)
        
        self.statusMessenger = StatusDispatcher()
        self.statusMessenger.signal.connect(self.showStatusMessage)
        self.statusMessenger.progressSignal.connect(self.updateProgressBar)
        self.buttonStop.clicked.connect(aVideoController.killSaveProcessing)
        self._hookListActions()
    
    def syncSpinButton(self, frameNbr):
        self.ui_GotoField.blockSignals(True)
        self.ui_GotoField.setValue(int(frameNbr))
        self.ui_GotoField.blockSignals(False)
    
    def keyReleaseEvent(self, event):
        self.__resetDial()
     
    def _hookListActions(self):
        # TOO bad-the list model -should be here... 
        rmAction = QtWidgets.QAction(QtGui.QIcon('icons/close-x.png'), 'Delete', self)
        rmAction.triggered.connect(self._removeMarker)
        rmAllAction = QtWidgets.QAction(QtGui.QIcon('icons/clear-all.png'), 'Remove all', self)
        rmAllAction.triggered.connect(self.purgeMarker)
        self.gotoAction = QtWidgets.QAction(QtGui.QIcon('icons/go-next.png'), 'Goto', self)
        self.gotoAction.triggered.connect(self._gotoFromMarker)
  
        # menus      
        self.ui_List.customContextMenuRequested.connect(self._openListMenu)
        self._listMenu = QtWidgets.QMenu()
        self._listMenu.addAction(self.gotoAction)
        self._listMenu.addSeparator()
        self._listMenu.addAction(rmAction)
        self._listMenu.addAction(rmAllAction)
 
    def __resetDial(self):
        self.ui_Dial.setProperty("value", 0)

    def __gotoFrame(self, value):
        self.__videoController._gotoFrame(value)

    def __createProgressBar(self):
        self.progressBar = QtWidgets.QProgressBar(self)
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximumWidth(200)
        self.progressBar.setVisible(False) 
        self.progressBar.setValue(0)
        return self.progressBar
    
    def startProgress(self):
        self.progressBar.setRange(0, 100)
        self.progressBar.setVisible(True)
        self.buttonStop.setVisible(True)

    def stopProgress(self):
        self.progressBar.setVisible(False)   
        self.buttonStop.setVisible(False)
        self.progressBar.setValue(0);           

    def enableUserActions(self, enable):
        self.ui_Dial.setEnabled(enable)
        self.ui_Slider.setEnabled(enable)
        self.gotoAction.setEnabled(enable)
        self.ui_GotoField.setEnabled(enable)

    def updateProgressBar(self, percent):
        self.progressBar.setValue(percent)

    def __createListWidget(self):
        iconList = QtWidgets.QListWidget()
        iconList.setAlternatingRowColors(True)
        iconList.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        #TODO: Respect colors
        iconList.setStyleSheet("QListView{outline:none;} QListWidget::item:selected { background: #28D9FF; } ")  # that text color seems not to work!
        fontM = QtGui.QFontMetrics(iconList.font())
        self.ITEM_HEIGHT = fontM.height() * ITEM_ROW_COUNT
        return iconList

    #---List widget context menu
    def _removeMarker(self, whatis):
        selectionList = self.ui_List.selectedIndexes()
        if len(selectionList) == 0:
            return
        item = selectionList[0]
        self.ui_List.takeItem(item.row())
        self.__videoController.removeVideoCutIndex(item.row())
  
    def clearMarkerList(self):
        self.ui_List.clear()

    # remove contents, remove file 
    def purgeMarker(self):
        self.ui_List.clear()
        self.__videoController.purgeVideoCuts()
        
    def _gotoFromMarker(self, whatis):
        selectionList = self.ui_List.selectedIndexes()
        if len(selectionList) == 0:
            return
        item = selectionList[0]
        self.__videoController.gotoCutIndex(item.row())
        
    def _openListMenu(self, position):
        selectionList = self.ui_List.selectedIndexes()
        if len(selectionList) == 0:
            return
        self._listMenu.exec_(self.ui_List.viewport().mapToGlobal(position)) 
        

class MainFrame(QtWidgets.QMainWindow):
    MODE_ACTIVE = 2
    signalActive = pyqtSignal()
    
    def __init__(self, aPath=None):
        self.__initalMode = 0
        
        super(MainFrame, self).__init__()
        self.setWindowIcon(getAppIcon())
        self.settings = SettingsModel(self)
        self._videoController = VideoControl(self)
        self._widgets = self.initUI()
        self._widgets.hookEvents(self._videoController)
        self.settings.update()
        
        self.centerWindow()
        self._widgets.enableUserActions(False)
        self.show() 
        if aPath is not None:
            self._videoController.setFile(aPath)
        else:
            self.getVideoWidget().showFrame(None)
    
    def initUI(self):
        
        # self.statusBar().showMessage('Ready')
         
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
        
        self.saveAction = QtWidgets.QAction(QtGui.QIcon('./icons/save-as-icon.png'), 'Save the video', self)
        self.saveAction.setShortcut('Ctrl+S')
        self.saveAction.triggered.connect(self.saveVideo)
        
        self.infoAction = QtWidgets.QAction(QtGui.QIcon('./icons/info.png'), 'Codec info', self)
        self.infoAction.setShortcut('Ctrl+I')
        self.infoAction.triggered.connect(self.showCodecInfo)
        
        self.playAction = QtWidgets.QAction(QtGui.QIcon('./icons/play.png'), 'Play video', self)
        self.playAction.setShortcut('Ctrl+P')
        self.playAction.triggered.connect(self.playVideo)
        
        self.photoAction = QtWidgets.QAction(QtGui.QIcon('./icons/screenshot.png'), 'Take screenshot', self)
        self.photoAction.setShortcut('Ctrl+P')
        self.photoAction.triggered.connect(self.takeScreenShot)
        
        '''
        the settings menues
        '''
#         self.convertToMP4 = QtWidgets.QAction(QtGui.QIcon('./icons/stop-red-icon.png'),"Convert to mp4",self)
#         self.convertToMP4 = QtWidgets.QAction("Convert to mp4",self)
#         self.convertToMP4.setCheckable(True)
#         self.selectContainer = QtWidgets.QAction(QtGui.QIcon('./icons/stop-red-icon.png'),"change to a different container",self)
#         self.extractMP3 = QtWidgets.QAction(QtGui.QIcon('./icons/stop-red-icon.png'),"Extract MP3",self)
#         self.switchAudio = QtWidgets.QAction(QtGui.QIcon('./icons/stop-red-icon.png'),"Swtich audio",self)
        self.mediaSettings = QtWidgets.QAction(QtGui.QIcon('./icons/settings.png'), "Output settings", self)
        self.mediaSettings.setShortcut('Ctrl+T')
        self.mediaSettings.triggered.connect(self.openMediaSettings)

        '''
        audio language selection
        '''
        self.langSettings = QtWidgets.QAction(QtGui.QIcon('./icons/langflags.png'), "Language settings", self)
        self.langSettings.setShortcut('Ctrl+L')
        self.langSettings.triggered.connect(self.openLanguageSettings)

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
        self.toolbar.addAction(self.photoAction)
        self.toolbar.addAction(self.infoAction)
        self.toolbar.addAction(self.playAction)
        self.toolbar.addAction(self.mediaSettings)
        self.toolbar.addAction(self.langSettings)
                               
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
        
        # connect the labels to their dialogs

        # if not "self" - stops if out of scope!
        self.cutfilter = SignalOnEvent(widgets.ui_CutModeLabel)
        self.cutfilter.clicked.connect(self.openMediaSettings)
        
        self.backendfilter = SignalOnEvent(widgets.ui_BackendLabel)
        self.backendfilter.clicked.connect(self.openMediaSettings)
        self.enableActions(False) 
        return widgets

    '''
    overwriting event seems to be the only way to find out WHEN there is the first
    time where we could display a dialog. So if Show && Activated have arrived
    the MainFrame sends a signal to whom it may concern...
    '''

    def event(self, event):
        if self.__initalMode < self.MODE_ACTIVE:
            if event.type() == QtCore.QEvent.Show or event.type() == QtCore.QEvent.WindowActivate:
                self.__initalMode += 1
                if self.isActivated():
                    self.signalActive.emit()
        return super(MainFrame, self).event(event)
    
    def isActivated(self):
        return self.__initalMode == self.MODE_ACTIVE
    
    def centerWindow(self):
        frameGm = self.frameGeometry()
        screen = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
        centerPoint = QApplication.desktop().screenGeometry(screen).center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())
    
    def updateWindowTitle(self, text):
        self.setWindowTitle("VideoCut - " + text)
    
    def openLanguageSettings(self):
        # TODO use the settings model!
        if self._videoController.streamData is None:
            return
        langMap = FFMPEGTools.createIso639Map()
        lang = self.settings.getPreferedLanguageCodes()
        dlg = LanguageSettingsDialog(self, lang, langMap, self._videoController.getLanguages())
        if dlg.exec_():
            print(dlg.getLanguages())
            self.settings.setPreferedLanguageCodes(dlg.getLanguages())
     
    def showInfo(self, text):
        self._widgets.showInfo(text)

    def syncSpinButton(self, frameNbr):
        self._widgets.syncSpinButton(frameNbr)

    def getVideoWidget(self):
        return self._widgets.ui_VideoFrame

    def syncSliderPos(self, pos):
        self._widgets.syncSliderPos(pos)
        
    def setDialResolution(self, fps):
        self._widgets.setDialResolution(fps)

    def setGotoMaximum(self, count):
        self._widgets.setGotoFieldMaximum(count)

    def setSliderTicks(self, ticks):
        self._widgets.setSliderTicks(ticks)        

    def addCutMark(self, frame, cutEntry, rowIndex):
        self._widgets.addCutMark(frame, cutEntry, rowIndex)
        
    def startProgress(self):
        self._widgets.startProgress()  # only the bar.
        self.toolbar.setEnabled(False)
        self._widgets.enableUserActions(False)
        
    def stopProgress(self):
        self._widgets.stopProgress()
        self.toolbar.setEnabled(True)
        self._widgets.enableUserActions(True)

    def showWarning(self, aMessage):
        pad = '\t'
        QtWidgets.QMessageBox.warning(self, "Warning!", aMessage + pad)
    
    def enableControls(self, enable):
        self._widgets.enableUserActions(enable)
        
    def enableActions(self,enable):
        self.saveAction.setEnabled(enable)
        self.infoAction.setEnabled(enable)
        self.playAction.setEnabled(enable)
        self.startAction.setEnabled(enable)
        self.stopAction.setEnabled(enable)   
        self.photoAction.setEnabled(enable)
        self.langSettings.setEnabled(enable)
             
                            
    #-------- ACTIONS ----------
    def loadFile(self):
        initalPath = self._videoController.getSourceFile()
        result = QtWidgets.QFileDialog.getOpenFileName(parent=self, directory=initalPath, caption="Load Video");
        if result[0]:
            fn = self.__encodeQString(result)
            self._widgets.clearMarkerList()
            self._videoController.clearVideoCutEntries()
            self._videoController.setFile(fn)  # encode error: str(result)
            
    def saveVideo(self):
        initalPath = self._videoController.getSourceFile()
        targetPath = self._videoController.getTargetFile()
        extn = self._videoController.getAllowedExtensions()
        fileFilter = "Video Files (%s)" % extn
        result = QtWidgets.QFileDialog.getSaveFileName(parent=self, directory=targetPath, filter=fileFilter, caption="Save Video");
        if result[0]:
            fn = self.__encodeQString(result)
            if initalPath == fn:
                self.showWarning("Can't overwrite source file!")
                return;
            self.startProgress()
            self._videoController.saveVideo(fn)
    
    def __encodeQString(self, stringTuple):
        text = stringTuple[0]
        return text
    
    def openMediaSettings(self):
        dlg = SettingsDialog(self, self.settings)
        dlg.show()
    
    def showCodecInfo(self):
        # TODO: More infos, better layout
        try:
            streamData = self._videoController.streamData 
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
            # text = '<table border=0 cellspacing="3",cellpadding="2"><tr border=1><td><b>Video Codec:</b></td><td> %s </td></tr><td><b>Dimension:</b></td><td> %s x %s </td></tr><tr><td><b>Aspect:</b></td><td> %s </td></tr><tr><td><b>FPS:</b></td><td> %s </td></tr><tr><td><b>Duration:</b></td><td> %s </td></tr><tr><td><b>Audio codec:</b></td><td> %s </td></tr></table>' %(videoData.getCodec(),videoData.getWidth(),videoData.getHeight(),videoData.getAspectRatio(),videoData.getFrameRate(),videoData.duration(),audioData.getCodec())
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
                    </table>""" % (container.formatNames()[0], container.getBitRate(), container.getSizeKB(), streamData.isTransportStream(), videoData.getCodec(), videoData.getWidth(), videoData.getHeight(), videoData.getAspectRatio(), videoData.getFrameRate(), videoData.duration(), audioData.getCodec())
            entries = []
            entries.append("""<br><\br><table border=0 cellspacing="3",cellpadding="2">""")
            
            for key, value in cvInfo.items():
                entries.append("<tr border=1><td><b>")
                entries.append(key)
                entries.append(":</b></td><td> ")
                entries.append(value)
                entries.append("</td></tr>")
            entries.append("</table>");
            text2 = ''.join(entries)
                                        
        except:
            Log.logException("Invalid codec format")
            text = "<br><b>No Information</b><br>"  
            text2= "<br> Please select a file first"
        self.__getInfoDialog(text + text2).show()
    
    def takeScreenShot(self):
        self._videoController.takeScreenShot()
        
    def playVideo(self):
        isPlaying = self._videoController.toggleVideoPlay()
        self.setVideoPlayerControls(isPlaying)
    
    def setVideoPlayerControls(self, isPlaying):
        if isPlaying:
            self.__enableActionsOnVideoPlay(False)
            self.playAction.setIcon(QtGui.QIcon('./icons/pause.png'))
        else:
            self.__enableActionsOnVideoPlay(True)
            self.playAction.setIcon(QtGui.QIcon('./icons/play.png'))            
               
    #-------- ACTIONS  END ----------    

    def __enableActionsOnVideoPlay(self, enable):
        self.enableControls(enable)
        self.loadAction.setEnabled(enable)
        self.saveAction.setEnabled(enable) 
        self._widgets.gotoAction.setEnabled(enable)        

    def __getInfoDialog(self, text):
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

    def getErrorDialog(self, text, infoText, detailedText):
        dlg = QtWidgets.QMessageBox(self)
        dlg.setIcon(QtWidgets.QMessageBox.Warning)
        dlg.setWindowModality(QtCore.Qt.WindowModal)
        dlg.setWindowTitle("Error")
        dlg.setText(text)
        dlg.setInformativeText(infoText)
        dlg.setDetailedText(detailedText)
        dlg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        spacer = QtWidgets.QSpacerItem(300, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        layout = dlg.layout()
        layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())
        return dlg
    
    def getMessageDialog(self, text, infoText):
        # dlg = DialogBox(self)
        dlg = QtWidgets.QMessageBox(self)
        dlg.setIcon(QtWidgets.QMessageBox.Information)
        dlg.setWindowModality(QtCore.Qt.WindowModal)
        dlg.setWindowTitle("Notice")
        dlg.setText(text)
        dlg.setInformativeText(infoText)
        dlg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        # Workaround to resize a qt dialog. WTF!
        spacer = QtWidgets.QSpacerItem(300, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        layout = dlg.layout()
        layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())
        
        # dlg.setMinimumSize(450, 0)
        return dlg;

'''    
class LanguageModel():
    def __init__(self,mainframe):
        lang = self.getAvailableLanguage(mainframe._videoController)
        self.parseIso692(lang)
        
        
    def parseIso692(self,langArray):
        #read the iso file
        HomeDir = os.path.dirname(__file__)
        DataDir=os.path.join(HomeDir,"data")
        path = os.path.join(DataDir,"unidueIso692.json")
        with open(path,'r')as f:
            self.langDict = json.load(f)
        #ned the items of arr 1
        data = self.langDict['items']
        for item in data.items():
            print(item)    
#         for lang in data:
#             if lang['ISO3']upper() in langArray:
#                 print("long:%s abbr:%s"%(lang['English'],lang['alpha3-b']))   
            
    def getAvailableLanguage(self,controller):
        lang= controller.getLanguages()
        print("avail:")
        for country in lang:
            print("   -%s"%(country))
        #this is alpha-3b code
        return lang    
'''


class SettingsModel():

    def __init__(self, mainframe):
        # keep flags- save them later
        self.fastRemux = vc_config.get("useRemux") == 'True'
        self.reencoding = vc_config.get("recode") == 'True'
#        vc_config.set("useRemux", "False")
#         vc_config.set("container","mp4")
#         vc_config.set("containerList","mp4,mpg,mkv,flv,m2t")
#         vc_config.set("recode","False")
#         vc_config.store()
#         self.fastRemux=False
#         self.selectedContainer="mp4" 
#         self.containerList=["mp4","mpg","mkv","flv","m2t"] 
#         self.reencoding=False
        self.mainFrame = mainframe
    
    def update(self):
        cutmode = "Fast"
        mode = "FFMPEG"
        if self.fastRemux:
            mode = "REMUX"
        if self.reencoding:
            cutmode = "Exact"
        self.mainFrame._widgets.ui_CutModeLabel.setText(cutmode)
        self.mainFrame._widgets.ui_BackendLabel.setText(mode)
        
        if self.fastRemux:
            vc_config.set("useRemux", "True")
        else:
            vc_config.set("useRemux", "False")
#         vc_config.set("container",self.selectedContainer)
#         vc_config.set("containerList",','.join(self.containerList))
        if self.reencoding:
            vc_config.set("recode", "True")
        else:
            vc_config.set("recode", "False")
        vc_config.store()
        
    def getPreferedLanguageCodes(self):
        lang = vc_config.get("LANG")
        if lang is None:
            lang = ["deu", "eng", "fra"]  # default
        else:
            lang = json.loads(lang)
        return lang

    def setPreferedLanguageCodes(self, langList):
        vc_config.set("LANG", json.dumps(langList))
        vc_config.store()
       
        
class SettingsDialog(QtWidgets.QDialog):

    def __init__(self, parent, model):
        """Init UI."""
        super(SettingsDialog, self).__init__(parent)
        self.model = model
        self.init_ui()

    def init_ui(self):
        self.setWindowModality(QtCore.Qt.WindowModal)
        self.setWindowTitle("Settings")

        outBox = QtWidgets.QVBoxLayout()
        # outBox.addStretch(1)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        versionBox = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel("Version:")
        ver = QtWidgets.QLabel(vc_config.get("version"))
        versionBox.addStretch(1)
        versionBox.addWidget(lbl)
        versionBox.addWidget(ver)
        versionBox.addStretch(1)

        frame1 = QtWidgets.QFrame()
        frame1.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Sunken)
        frame1.setLineWidth(1)
       
        frame2 = QtWidgets.QFrame()
        frame2.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Sunken)
        frame2.setLineWidth(1)
       
        encodeBox = QtWidgets.QVBoxLayout(frame1)
        self.check_reencode = QtWidgets.QCheckBox("Reencode (Slow!)")
        self.check_reencode.setToolTip("Force exact cut. Makes it real slow!")
        self.check_reencode.setChecked(self.model.reencoding)
        # connect
        self.check_reencode.stateChanged.connect(self.on_reencodeChanged)
        self.exRemux = QtWidgets.QCheckBox("VideoCut Muxer")
        self.exRemux.setToolTip("Uses the remux code instead of default ffmpeg commandline")
        self.exRemux.setChecked(self.model.fastRemux)
        self.exRemux.stateChanged.connect(self.on_fastRemuxChanged)
        
        encodeBox.addWidget(self.check_reencode)
       
        expoBox = QtWidgets.QVBoxLayout(frame2)
        expoBox.addWidget(self.exRemux)
        
        outBox.addLayout(versionBox)
        outBox.addWidget(frame1)
        outBox.addWidget(frame2)
        self.setLayout(outBox)
        # make it wider...
        self.setMinimumSize(400, 0)
        
#     def on_combobox_selected(self,value):
#         self.model.selectedContainer=value
#         self.model.update()
    
    def on_reencodeChanged(self, reencode):
        self.model.reencoding = QtCore.Qt.Checked == reencode
        # self.combo.setEnabled(self.model.reencoding)
        self.model.update()
        
    def on_fastRemuxChanged(self, isFastRemux):
        self.model.fastRemux = QtCore.Qt.Checked == isFastRemux
        self.model.update()    

        
class LanguageSettingsDialog(QtWidgets.QDialog):

    def __init__(self, parent, defCodes, langData, available3LetterCodes):
        """Init UI."""
        super(LanguageSettingsDialog, self).__init__(parent)
        self.model = langData
        self.setupLanguages(defCodes,available3LetterCodes)
        self.init_ui()
    
    def init_ui(self):
        self.setWindowModality(QtCore.Qt.WindowModal)
        self.setWindowTitle("Language")
        frame1 = QtWidgets.QFrame()
        frame1.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Sunken)
        frame1.setLineWidth(1)
        
        vBox = QtWidgets.QVBoxLayout()
        hBox = QtWidgets.QHBoxLayout(frame1)
        dlgBox = QtWidgets.QVBoxLayout() 
        self.btnup = QtWidgets.QPushButton()
        self.btnup.clicked.connect(self.onButtonUp)
        self.btnup.setIcon(QtGui.QIcon.fromTheme("up"))
        self.btndown = QtWidgets.QPushButton()
        self.btndown.setIcon(QtGui.QIcon.fromTheme("down"))
        self.btndown.clicked.connect(self.onButtonDown)
        vBox.addStretch(1)
        vBox.addWidget(self.btnup, 0)
        vBox.addWidget(self.btndown, 0)
        vBox.addStretch(1)
        
        self.listWidget = QtWidgets.QListWidget()
        self.listWidget.setAlternatingRowColors(True)
        self.listWidget.itemSelectionChanged.connect(self.onItemSelectionChanged)
        self.listWidget.itemChanged.connect(self.onChange)
        hBox.addWidget(self.listWidget)
        hBox.addLayout(vBox, 0)
        
        btnHBox = QtWidgets.QHBoxLayout()
        self.lbl = QtWidgets.QLabel("3 Languages max")
        pix = QtGui.QPixmap()
        pix.load("icons/info.png")
        pix = pix.scaledToWidth(32, mode=Qt.SmoothTransformation)
        info = QtWidgets.QLabel("")
        info.setPixmap(pix)
        btnHBox.addWidget(info)
        btnHBox.addWidget(self.lbl)
        self.button_box = QtWidgets.QDialogButtonBox(self)
        self.button_box.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Save)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        btnHBox.addWidget(self.button_box)
        
        dlgBox.addWidget(frame1)
        dlgBox.addLayout(btnHBox)
        
        self.setLayout(dlgBox)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.setMinimumSize(400, 0)   
        self.setModelData()
        item = self.listWidget.item(0)
        item.setSelected(True)
    
    def onChange(self, widget):
        state = widget.checkState()
        if state == Qt.Checked:
            self._limitCheckedItems()
    
    def _limitCheckedItems(self):
        selected = []
        for index in range(self.listWidget.count()):
            item = self.listWidget.item(index)
            if item.checkState() == Qt.Checked:
                selected.append(item)
                
        if len(selected) > 3:
            test = selected.pop()
            test.setCheckState(Qt.Unchecked)
        
    @QtCore.pyqtSlot()
    def onItemSelectionChanged(self):
        sel = len(self.listWidget.selectedIndexes())
        count = self.listWidget.count()
        if count > 1 and sel == 1:
            self.btnup.setDisabled(False)
            self.btndown.setDisabled(False) 
        else:
            self.btnup.setDisabled(True)
            self.btndown.setDisabled(True) 
        
    @QtCore.pyqtSlot()        
    def onButtonDown(self):
        currItem = self._getSelectedItem()
        if currItem is None:
            return
        currSel = self.listWidget.currentRow()
        count = self.listWidget.count()
        nextSel = currSel + 1
        if nextSel == count:
            nextSel = count - 1
        if nextSel == currSel:
            return
        self.listWidget.takeItem(currSel) 
        self.listWidget.insertItem(nextSel, currItem)
        self.listWidget.setCurrentRow(nextSel)
     
    @QtCore.pyqtSlot()        
    def onButtonUp(self):
        currItem = self._getSelectedItem()
        if currItem is None:
            return
        currSel = self.listWidget.currentRow()        
        nextSel = currSel - 1
        if nextSel < 0:
            nextSel = 0
        if nextSel == currSel:
            return
        self.listWidget.takeItem(currSel) 
        self.listWidget.insertItem(nextSel, currItem)
        self.listWidget.setCurrentRow(nextSel)
    
    def _getSelectedItem(self):
        sellist = self.listWidget.selectedItems()
        if len(sellist) == 0:
            return None
        return sellist[0]
                 
    def setModelData(self):
        if len(self.avail) == 0:
            item = QtWidgets.QListWidgetItem()                
            item.setText("No language data available")
            self.listWidget.addItem(item)
            return 0
        #codeToLang = self.model[0]
        primMix = [None, None, None]
        for lang in self.avail:
            if lang in self.defaultCodes:
                idx = self.defaultCodes.index(lang)
                primMix[idx] = lang
            else:
                primMix.append(lang)
            
        cnt = 0    
        for lang in primMix:
            if lang is None:
                continue

            item = QtWidgets.QListWidgetItem()                
            item.setText(lang)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            if lang in self.defaultCodes:
                item.setCheckState(QtCore.Qt.Checked)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)
            self.listWidget.addItem(item)
            cnt += 1
        
        return self.listWidget.count() 
    
    def getLanguages(self):
        lang = []
        langToCode = self.model[1]
        for index in range(self.listWidget.count()):
            item = self.listWidget.item(index)
            if item.checkState() == Qt.Checked:
                code = langToCode[item.text()]
                lang.append(code)
        
        return lang

    #defCodes = saved user selected codes, avail = Codes in film
    # need to be changed to a common denominatior: the country name (deu,ger...)
    def setupLanguages(self,defCodes,available3LetterCodes): 
        codeToLang = self.model[0]    
        self.avail = []
        self.defaultCodes = []
        for code in defCodes:
            self.defaultCodes.append(codeToLang[code])
             
        for code in available3LetterCodes:
            self.avail.append(codeToLang[code])
     
        
'''
Class may be replaced if the underlying interface is not opencv (e.g qt or ffmpeg or sth)
'''        


class VideoPlayerCV():

    def __init__(self, path, streamProbe, rotation):
        self.framecount = 0
        self.totalTimeMilliSeconds = 0.0 
        self._streamProbe = streamProbe
        self._capture = None
        self._file = str(path)
        self._zero = 0.0
        self._isValid = self._captureFromFile(rotation)
        self.currentFrame=None
        
    def _captureFromFile(self, rotation):
        if self._streamProbe is None or not self._streamProbe.isKnownVideoFormat():
            print ("STREAM NOT KNOWN")
            Log.logInfo("STREAM NOT KNOWN")
            return False
        self._capture = OPENCV.getCapture();
        if not self._capture.open(self._file):
            Log.logError("STREAM NOT OPENED")
            return False

        self.frameWidth = OPENCV.getFrameWidth()
        self.frameHeight = OPENCV.getFrameHeight()
        self.framecount = OPENCV.getFrameCount()
        test = self._streamProbe.getVideoStream().duration()
        self.fps = OPENCV.getFPS()

        # The problem: cv has a problem if it is BEHIND the last frame...
        # DO NOT USE>> cap.set(cv2.cv.CV_CAP_PROP_POS_AVI_RATIO,1);
        if self.framecount == 0:
            self.totalTimeMilliSeconds = test*1000
        else:
            self.totalTimeMilliSeconds = int(self.framecount / self.fps * 1000)
        self.calcZero(rotation)
        return True

    def calcZero(self, rotation):
        ret, frame = self._capture.read()
        if ret:
            CVImage.ROTATION = self.__getRotation(rotation)
            self._zero = OPENCV.getTimePosition()
            self.currentFrame=frame
        OPENCV.setFramePosition(0)  # position of the NEXT read 
    
    def __getRotation(self, rotation):
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

    """Milliseconds per frame."""

    def mspf(self):
        return int(1000 // (self.fps or 25))
            
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
            self.setFrameAt(frameNumber - 1)
            return self.getNextFrame()
        except: 
            Log.logException("Error Frame")
            return None
    
    def getCurrentFrameNumber(self):
        return OPENCV.getFramePosition()

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
        return max(OPENCV.getTimePosition() - self._zero, 0.0)

    def takeScreenShot(self,path):
        if self.currentFrame is None:
            return False
        cv2.imwrite(path,cv2.cvtColor(self.currentFrame, cv2.COLOR_RGB2BGR))
        return True

    def close(self):
        if self._capture is not None:
            self._capture.release()
             
'''
  handles the events from the GUI, connecting to the VideoPlayer and the VideoWidget... 
'''        


class VideoControl(QtCore.QObject):

    def __init__(self, mainFrame):
        super(VideoControl, self).__init__()
        self.player = None
        self.gui = mainFrame
        self._frameSet = False
        self._initTimer()
        self.videoCuts = []
        self.currentPath = OSTools().getHomeDirectory()
        self.streamData = None
        self._vPlayer = None
        mainFrame.signalActive.connect(self.displayWarningMessage)
        self.lastError = None
        self.sliderThread = None

    def _initTimer(self):
        self._timer = QtCore.QTimer(self.gui)
        self._timer.timeout.connect(self._displayAutoFrame)
   
    def getSourceFile(self):
        if self.streamData is not None:
            return self.currentPath + "." + self.streamData.getSourceExtension()

        return self.currentPath

    def getTargetFile(self):
        if self.streamData is not None:
            target= self.currentPath + "." + self.streamData.getTargetExtension()
            return target 

        return self.currentPath + "-vc.mp4"

    def getAllowedExtensions(self):
        if self.streamData is not None:
            return self.streamData.getDialogFileExtensions()
        else:
            return "*.*"
    
    def getLanguages(self):
        return self.streamData.getLanguages()
     
    def displayWarningMessage(self):
        if self.lastError is None:
            return
        self.gui.showWarning(self.lastError)
        self.lastError = None
        
    #-- Menu handling ---    
    def setFile(self, filePath):
        if self.player is not None:
            self.player.close()
            self.videoCuts = []
        try:
            self.streamData = FFStreamProbe(filePath)
            self.currentPath = OSTools().getPathWithoutExtension(filePath); 
        except: 
            Log.logException("Error 1")
            self.streamData = None  
            self.currentPath = OSTools().getHomeDirectory()    
        try:            
            rot = self.streamData.getRotation()
            self.player = VideoPlayerCV(filePath, self.streamData, rot)
            self._initSliderThread()
            self.player.validate()
            
            self.__initSliderTicks()
            self.gui.enableControls(True)
            self.gui.enableActions(True)
            ratio = self.streamData.getAspectRatio()

            self.gui.updateWindowTitle(OSTools().getFileNameOnly(filePath))
            self.gui.getVideoWidget().setVideoGeometry(ratio, rot)
            self._asyncInitVideoViews()
           
        except:
            print ("Error -see log")
            Log.logException("Error 2")
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

    def _createVideoCutEntry(self, mode, updateXML=True):
        self.sliderThread.wait()
        if updateXML:
            frame = self.player.getCurrentFrame()
        else:
            frame = self.player.getNextFrame()
        framePos = self.player.getCurrentFrameNumber()
        timePos = self.player.getCurrentFrameTime()
        cutEntry = VideoCutEntry(framePos, timePos, mode)
        self._addVideoCut(frame, cutEntry, updateXML)

    def _addVideoCut(self, frame, cutEntry, updateXML):
        rowIndex = len(self.videoCuts)
        for idx, videoEntry in enumerate(self.videoCuts):
            frameNbr = videoEntry.frameNumber
            testNbr = cutEntry.frameNumber
            if testNbr < frameNbr:
                rowIndex = idx
                break
        
        self.videoCuts.insert(rowIndex, cutEntry)
        self.gui.addCutMark(frame, cutEntry, rowIndex)
        if updateXML:
            XMLAccessor(self.currentPath).writeXML(self.videoCuts)

    def _asyncInitVideoViews(self):
        QtCore.QTimer.singleShot(10, self._grabNextFrame)
        QtCore.QTimer.singleShot(150, self.restoreVideoCuts)

    def restoreVideoCuts(self):
        self.sliderThread.wait()  # sync with the worker
        QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            cutList = XMLAccessor(self.currentPath).readXML()
        except Exception as error:
            print(error)
            return  
        for cut in cutList:
            fbnr = cut.frameNumber
            self.player.setFrameAt(fbnr - 1)
            mode = VideoCutEntry.MODE_STOP
            if cut.isStartMode():
                mode = VideoCutEntry.MODE_START
            self._createVideoCutEntry(mode, False)

        self.player.setFrameAt(0)
        QApplication.restoreOverrideCursor()          
    
    # remove/clear all cuts but leave the file untouched
    def clearVideoCutEntries(self):
        self.videoCuts = []

    # clear all cuts and its persistence
    def purgeVideoCuts(self):
        self.clearVideoCutEntries()
        XMLAccessor(self.currentPath).clear()        
    
    def removeVideoCutIndex(self, index):
        cut = self.videoCuts[index]
        self.videoCuts.remove(cut)
        XMLAccessor(self.currentPath).writeXML(self.videoCuts)
    
    def gotoCutIndex(self, index):
        cut = self.videoCuts[index]
        self._gotoFrame(cut.frameNumber)
    
    # callback from stop button
    def killSaveProcessing(self):
        if self.cutter is None:
            Log.logInfo("Can't kill process")
        else:
            self.cutter.stopCurrentProcess()

    def saveVideo(self, path):
        spanns = []
        block = None
        for cutEntry in self.videoCuts:
            
            if cutEntry.isStartMode():
                if block:
                    Log.logInfo("Start invalid: %s" % (cutEntry.getTimeString()))
                else:
                    block = []
                    block.append(cutEntry)
            else:
                if block:
                    block.append(cutEntry)
                    spanns.append(block)
                    block = None
                else:
                    Log.logInfo("Stop ignored:" + cutEntry.getTimeString())
        src = self.player._file
        # need that without extension!
        self.cutAsync(src, path, spanns)
    
    #-- Menu handling end ---
    #-- Exec cutting ---
    def calculateNewVideoTime(self, spanns):
        delta = 0;
        for index, cutmark in enumerate(spanns):
            t1 = cutmark[0].timePos
            t2 = cutmark[1].timePos
            delta = delta + (t2 - t1).seconds
        return timedelta(seconds=delta)

    def cutAsync(self, srcPath, targetPath, spanns):
        self.cutTimeStart = time();
        settings = self.gui.settings
        if settings.fastRemux:
            worker = LongRunningOperation(self.__directCut, srcPath, targetPath, spanns, settings)
        else:
            worker = LongRunningOperation(self.__makeCuts, srcPath, targetPath, spanns, settings)
        worker.signal.connect(self._cleanupWorker)
        # start the worker thread. 
        worker.startOperation()  

    def _cleanupWorker(self, worker):
        # QThread: Destroyed while thread is still running
         
        self.gui.stopProgress()
        worker.quit()
        worker.wait();
        if self.cutter is None or self.cutter.wasAborted():
            self.gui.getMessageDialog("Operation failed", "Cut aborted").show()
        elif self.cutter.hasErrors():
            self.lastError = "Remux failed: %s " % (self.cutter.getErrors()[0])
            self.displayWarningMessage()
        else:
            dx = time() - self.cutTimeStart
            delta = FFMPEGTools.timedeltaToFFMPEGString(timedelta(seconds=dx))
            self.gui.getMessageDialog("Operation done", "Cutting time: %s" % delta,).show()
        self.cutter = None 

    '''
    FFMPEG cutting API
    '''    

    def __makeCuts(self, srcPath, targetPath, spanns, settings):
        # TODO pass settings
        config = CuttingConfig(srcPath, targetPath, settings.getPreferedLanguageCodes())
        config.streamData = self.streamData
        config.reencode = settings.reencoding
        
        config.messenger = self.gui._widgets.statusMessenger
        self.cutter = FFMPEGCutter(config, self.calculateNewVideoTime(spanns))
        self.cutter.ensureAvailableSpace()
        slices = len(spanns)
        for index, cutmark in enumerate(spanns):
            t1 = cutmark[0].timePos
            t2 = cutmark[1].timePos
            hasSucess = self.cutter.cutPart(t1, t2, index, slices)
            if not hasSucess:
                Log.logError("***Cutting failed***")
                return
        self.cutter.join()  
        
    '''
    new VCCutter API
    '''

    def __directCut(self, srcPath, targetPath, spanns, settings):
        # TODO pass settings
        config = CuttingConfig(srcPath, targetPath, settings.getPreferedLanguageCodes())
        config.streamData = self.streamData
        config.messenger = self.gui._widgets.statusMessenger
        config.reencode = settings.reencoding
        
        self.cutter = VCCutter(config)
        self.cutter.cut(spanns)
    
    def _initSliderThread(self):
        if self.sliderThread is not None:
            Worker.stop;
            self.sliderThread.exit()
            sleep(0.1)
        self.sliderThread = Worker(self.player.getFrameAt)
        self.sliderThread.signal.connect(self._processFrame)
    
    # we want 1 minute per single step
    def __initSliderTicks(self):
        videoInfo = self.streamData.getVideoStream()
        fps = videoInfo.getFrameRate()
        if self.player.framecount > 0:
            ratio = round(LayoutWindow.SLIDER_RESOLUTION * 60 * fps / self.player.framecount, 1)
            self.gui.setSliderTicks(round(ratio))
            self.gui.setDialResolution(fps)
            self.gui.setGotoMaximum(int(self.player.framecount))
        self._frameSet = False 
        
    # connected to slider-called whenever position is changed.
    def sliderMoved(self, pos):
        if self.player is None or not self.player.isValid():
            self.gui.syncSliderPos(0)
            return
        if not self._frameSet: 
            frameNumber = round(self.player.framecount / LayoutWindow.SLIDER_RESOLUTION * pos, 0)
            self.__dispatchShowFrame(frameNumber)
        self._frameSet = False

    # display Frame with syncing the slider pos. 
    def _gotoFrame(self, frameNumber=0):
        if self.player is None:
            return;
        self._frameSet = True
        if self.player.framecount < 1:
            return;
        if frameNumber == 0:
            sliderPos = 0
        else:
            sliderPos = int(frameNumber * LayoutWindow.SLIDER_RESOLUTION / self.player.framecount)
        self.gui.syncSliderPos(sliderPos)
        self.__dispatchShowFrame(frameNumber)
    
    def __dispatchShowFrame(self, frameNumber):
        if self._vPlayer is None:
            self.sliderThread.showFrame(frameNumber)
    
    # connected to the dial
    def dialChanged(self, pos):
        if self.player is None or pos == 0:
            self._timer.stop()
            return
        self._dialStep = math.copysign(1, pos) * round(math.exp(abs(pos / 3.0) - 1))
        ts = int((1 / self.player.fps) * 2500)
        self._timer.start(ts)
 
    # called by timer on dial change...    
    def _displayAutoFrame(self):
        if self.player is None or not self.player.isValid():
            return
        self.sliderThread.wait()  # No concurrency with worker!
        self._frameSet = True
        frameNumber = max(0, self.player.getCurrentFrameNumber() + self._dialStep);
        sliderPos = int(frameNumber * LayoutWindow.SLIDER_RESOLUTION / self.player.framecount)
        self.gui.syncSliderPos(sliderPos)
        aFrame = self.player.getFrameAt(frameNumber)
        self._showFrame(aFrame)
        self._frameSet = False
        
    # called by worker ...
    def _processFrame(self):
        frm = self.sliderThread.result
        self._showFrame(frm)
        
    def _showFrame(self, aFrame):
        self._videoUI().showFrame(aFrame)
        x = self.player.getCurrentFrameNumber()
        self._showCurrentFrameInfo(x)
       
    def _videoUI(self):
        return self.gui.getVideoWidget()
    
    def _showCurrentFrameInfo(self, frameNumber):
        timeinfo = self.player.getCurrentTimeMS()
        s = int(timeinfo / 1000)
        ms = int(timeinfo % 1000)
        ts = '{:02}:{:02}:{:02}.{:03}'.format(s // 3600, s % 3600 // 60, s % 60, ms)
        out = "<b>Frame:</b> %08d of %d <b>Time:</b> %s " % (frameNumber, int(self.player.framecount) , ts,)
        # TODO: Pass 3 values for 3 widgets....
        self.gui.showInfo(out)
        self.gui.syncSpinButton(frameNumber)
    
    def takeScreenShot(self):
        if self.player is None:
            return;
        index=self.player.getCurrentFrameNumber()
        path = self.currentPath+str(int(index))+'.jpg'
        if self.player.takeScreenShot(path):
            self.gui.getMessageDialog("Screenshot saved at:", path).show()
             
    
    def toggleVideoPlay(self):
        if self.streamData is None:
            return False
        if self._vPlayer is None:
            return self.__playVideo()
        
        return self.__stopVideo()

    def __playVideo(self):
        self._vPlayer = QtCore.QTimer(self.gui)
        self._vPlayer.timeout.connect(self._grabNextFrame)
        # 50 ms if 25 fps and 25 if 50fps
        fRate = (1 / self.player.fps) * 1250
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
        frame = self.player.getNextFrame()
        if frame is not None:
            self._videoUI().showFrame(frame)
            frameNumber = self.player.getCurrentFrameNumber()
            sliderPos = int(frameNumber * LayoutWindow.SLIDER_RESOLUTION / self.player.framecount)
            self._showCurrentFrameInfo(frameNumber)
            
            if self.player.framecount == frameNumber:
                self.__stopVideo()
                self.gui.setVideoPlayerControls(False)
            
            self.gui.syncSliderPos(sliderPos)
        else:
            self.gui.setVideoPlayerControls(False)
            self.player.framecount = self.player.getCurrentFrameNumber()
            self.__stopVideo()        


# -- threads
class Worker(QtCore.QThread):
    signal = pyqtSignal()
    result = None
    stop = False

    def __init__(self, func):
        super(Worker, self).__init__()
        self.func = func
        self.fbnr = 0

        # self._dialStep = 1
    def run(self):
        current = -1;
        while self.fbnr != current:
            current = self.fbnr
            self.result = self.func(current)
            self.signal.emit()

    def __del__(self):
        self.wait()

    def showFrame(self, frameNumber):
        self.fbnr = frameNumber
        if not self.stop:
            self.start()

    
class SignalOnEvent(QtCore.QObject):
    clicked = pyqtSignal()
    
    def __init__(self, widget):
        QtCore.QObject.__init__(self)
        self.widget = widget
        widget.installEventFilter(self)

    def eventFilter(self, anyObject, event):
        if anyObject == self.widget:
            if event.type() == QtCore.QEvent.MouseButtonRelease and anyObject.rect().contains(event.pos()):
                    self.clicked.emit()
                    return True
            return False
        else:
            return super(SignalOnEvent, self).eventFilter(anyObject, event)
   
    def doit(self):
        self.widget.installEventFilter(self)

    
''' Long running operations for actions that do not draw or paint '''        


class LongRunningOperation(QtCore.QThread):
    signal = pyqtSignal(object) 

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
            self.signal.emit(self)

    def startOperation(self):
        self.start()  # invokes run - process pending QT events
        sleep(0.5)
        QtCore.QCoreApplication.processEvents()


class StatusDispatcher(QtCore.QObject):
    signal = pyqtSignal(str)
    progressSignal = pyqtSignal(int)

    def __init__(self):
        QtCore.QObject.__init__(self)
    
    def say(self, aString):
        self.signal.emit(aString)
    
    def progress(self, percent):
        self.progressSignal.emit(percent)


class ConfigAccessor():
    __SECTION = "videocut"

    def __init__(self, filePath):
        self._path = filePath
        self.parser = configparser.ConfigParser()
        self.parser.add_section(self.__SECTION)
        
    def read(self):
        self.parser.read(self._path)
        
    def set(self, key, value):
        self.parser.set(self.__SECTION, key, value)
    
    def get(self, key):
        if self.parser.has_option(self.__SECTION, key):
            return self.parser.get(self.__SECTION, key)
        return None

    def getInt(self, key):
        if self.parser.has_option(self.__SECTION, key):
            return self.parser.getint(self.__SECTION, key)
        return None
        
    def store(self):
        try:
            with open(self._path, 'w') as aFile:
                self.parser.write(aFile)
        except IOError:
            return False
        return True     


WIN = None


def handle_exception(exc_type, exc_value, exc_traceback):
    """ handle all exceptions """
    if WIN is not None:
        infoText = str(exc_value)
        detailText = "*".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        WIN.getErrorDialog("Unexpected error", infoText, detailText).show()
     

def main():
    try:
        global WIN
        global Log
        global vc_config
        Log = Logger()
        OSTools().setCurrentWorkingDirectory()
        #Log.logInfo('*** start in %s***' % OSTools().getWorkingDirectory())        
        vc_config = ConfigAccessor("data/vc.ini")
        vc_config.read();
        
        argv = sys.argv
        app = QApplication(argv)
        app.setWindowIcon(getAppIcon())
        if len(argv) == 1:
            WIN = MainFrame()  # keep python reference!
        else:
            WIN = MainFrame(argv[1])  
        app.exec_()
        Log.logClose()
    except:
        Log.logException("Error in main:")      
        traceback.print_exc(file=sys.stdout)

#TODO: Respect theme
def stylesheet(self):
    # return "QSlider{margin:1px;padding:1px;background:yellow}" #to view the focus border QSlider:focus{border: 1px solid  #000}
    # No focus and no ticks are available using stylesheets.
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
    sys.excepthook = handle_exception
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# copyright (c) 2016-2024 kanehekili (kanehekili.media@gmail.com)
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License,
# as published by the Free Software Foundation, either version 2 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the  GNU General Public License for more
# details.
#
# You should have received a copy of the  GNU General Public License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.


import sys, traceback, math, getopt

from PyQt6.QtCore import pyqtSignal
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QApplication, QWidget
import json
from PyQt6.QtCore import Qt
from datetime import timedelta
from FFMPEGTools import  FFStreamProbe,  OSTools, ConfigAccessor, FFmpegVersion
from Cutter import FFMPEGCutter,CuttingConfig,VCCutter
import FFMPEGTools 
import Cutter
from time import sleep, time
import xml.etree.cElementTree as CT
#####################################################
Version = "@xxx@"
#####################################################

global Log
Log = FFMPEGTools.Log

# sizes ..
SIZE_ICON = 80
ITEM_ROW_COUNT = 3


saneCheck = FFmpegVersion()
if not saneCheck.confirmFFmpegInstalled():
    app = QApplication(sys.argv)
    QtWidgets.QMessageBox.critical(None, "FFMPEG",
        ("FFMPEG must be installed to run VideoCut."))
    sys.exit(1)

def setUpVideoPlugin(mpv):
    if mpv:
        from MpvPlayer import MpvPlugin 
        return MpvPlugin(SIZE_ICON)
    else:
        #retained for testing - OpenCV is not precise enough
        from CvPlayer import CvPlugin
        return CvPlugin(SIZE_ICON) #TODO not the right place!    


def getAppIcon():
    return QtGui.QIcon('icons/movie-icon.png')

def timedeltaToString(deltaTime):
    s = deltaTime.seconds
    hours, remainder = divmod(s, 3600)
    minutes, seconds = divmod(remainder, 60)
    return '%s:%s:%s' % (hours, minutes, seconds)

 


class XMLAccessor():

    def __init__(self, path):
        self._path = path + ".xml"
        
    def writeXML(self, videoCutEntries):
        rootElement = CT.Element("VC_Data")
        for cut in videoCutEntries:
            entry = CT.SubElement(rootElement, "Entry")
            entry.attrib["frame"] = str(cut.frameNumber)
            entry.attrib["timepos"] = str(cut.timePosMS) 
            entry.attrib["mode"] = str(cut.modeString)
            entry.attrib["pix"] =self.toBase64(cut.pix)
        
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
            timePosSecs= float(info.get('timepos',0))
            pix=self.fromBase64(info.get('pix'))                            
            entry = VideoCutEntry(frameNbr, timePosSecs, markerType,pix)
            cutEntries.append(entry)
        
        return cutEntries

    def toBase64(self,pix):
        data = QtCore.QByteArray() 
        buf = QtCore.QBuffer(data)
        pix.save(buf, 'JPG')
        #breaks xml test=data.toBase64()
        t1=data.toBase64()
        t2= str(t1,'ascii')
        return t2
    
    def fromBase64(self,pixstr):
        if pixstr is None:
            return None
        t1=bytearray(pixstr,"ascii")
        #data = QtCore.QByteArray.fromBase64(pixstr,QtCore.QByteArray.Base64Encoding)
        data = QtCore.QByteArray.fromBase64(t1)
        pix=QtGui.QPixmap()
        pix.loadFromData(data)
        return pix

    def clear(self):
        OSTools().removeFile(self._path)

            
            
class VideoDial(QtWidgets.QDial):
    finetune = pyqtSignal(int)
    def __init__(self, parent):
        QtWidgets.QDial.__init__(self, parent)
        self.dir=0; #1 forw, 2 back, 0 center
                    
    def sliderChange(self,sliderChange):
        if sliderChange == QtWidgets.QDial.SliderChange.SliderValueChange:
            pos = self.value()
            if self.dir==0 and pos > 0:
                self.dir=1
            elif self.dir == 0 and pos < 0:
                self.dir =2 
            elif pos == 0:
                self.dir =0
            
            if self.dir==1 and pos < 0:
                self.setValue(self.maximum())
                return
            if self.dir==2 and pos > 0:
                self.setValue(self.minimum())
                return
            self.finetune.emit(pos)
        
        super(VideoDial, self).sliderChange(sliderChange)                                                        

    #GTK legacy?
    def minimumSizeHint(self):
        return QtCore.QSize(80,80);

       
    ''' That the native impl...
    from math import sin, cos, atan2, degrees, radians
    def  paintEvent(self,paintEvent):
        painter = QtGui.QPainter(self)
        option = QtWidgets.QStyleOptionSlider()
        #not used: brush = painter.pen()
        #brush.setColor(QtGui.QColor(255,0,0))
        painter.setPen(self.notchPen)
        self.initStyleOption(option);
        self.style().drawComplexControl(QtWidgets.QStyle.CC_Dial, option,painter,self);
    
            
    def paintEvent(self, event):        
        super(VideoDial, self).paintEvent(event)
        self.notchPen = QtGui.QPen(QtCore.Qt.red, 2)
        notchSize=5
        qp = QtGui.QPainter(self)
        qp.setRenderHints(qp.Antialiasing)
        #qp.translate(.5, .5)
        rad = radians(150)
        qp.setPen(self.notchPen)
        c = -cos(rad)
        s = sin(rad)
        # use minimal size to ensure that the circle used for notches
        # is always adapted to the actual dial size if the widget has
        # width/height ratio very different from 1.0
        maxSize = min(self.width() / 2, self.height() / 2)
        minSize = maxSize - notchSize
        center = self.rect().center()
        qp.drawLine(center.x(), center.y() -minSize, center.x(), center.y() - maxSize)
        qp.drawLine(center.x() + s * minSize, center.y() + c * minSize, center.x() + s * maxSize, center.y() + c * maxSize)
        qp.drawLine(center.x() - s * minSize, center.y() + c * minSize, center.x() - s * maxSize, center.y() + c * maxSize)
    '''

class VideoCutEntry():
    MODE_START = "Start"
    MODE_STOP = "Stop"

    def __init__(self, frameNbr, timepos, markerType,pix=None):
        self.frameNumber = frameNbr;
        self.modeString = markerType
        self.timePosMS = timepos #[ms]
        self.pix=pix #[qPixmap]
        
    def isStartMode(self):
        return self.MODE_START == self.modeString    
    
    def pixmap(self):
        return self.pix
    
    def getTimeString(self):
        timeinfo=self.timePosMS
        s = int(timeinfo / 1000)
        ms = int(timeinfo % 1000)
        ts = '{:02}:{:02}:{:02}.{:03}'.format(s // 3600, s % 3600 // 60, s % 60, ms)
        return ts

    def timeDelta(self):
        return timedelta(milliseconds=self.timePosMS)
    
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
    #SLIDER_RESOLUTION = 1000
    SLIDER_RESOLUTION = 1000*1000
    DIAL_RESOLUTION = 50 

    def __init__(self,settings,parent=None):
        QWidget.__init__(self, parent)
        self.initWidgets(settings)

    def initWidgets(self,settings):
        self.ui_VideoFrame = VideoPlugin.createWidget(settings.showGL,self) 
        
        self.ui_Slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.ui_Slider.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        # contribution:
        self.ui_Slider.setStyleSheet(stylesheet())
        
        self.ui_Slider.setMinimum(0)
        self.ui_Slider.setMaximum(self.SLIDER_RESOLUTION)
        self.ui_Slider.setToolTip("Video track")
        self.ui_Slider.setTickPosition(QtWidgets.QSlider.TickPosition.TicksAbove)
        self.ui_Slider.setTickInterval(0)
        
        #self.ui_Dial = QtWidgets.QDial(self)
        self.ui_Dial = VideoDial(self)
        
        self.ui_Dial.setProperty("value", 0)
        self.ui_Dial.setNotchesVisible(True)
        self.ui_Dial.setWrapping(False)
        self.ui_Dial.setNotchTarget(5.0)
        self.ui_Dial.setToolTip("Fine tuning")
        #styles don't work:
        #no gradients: self.ui_Dial.setStyleSheet("QDial { background-color: qradialgradient(cx:0, cy:0, radius: 1,fx:0.5, fy:0.5, stop:0 white, stop:1 green); }")
        self.setDialResolution(self.DIAL_RESOLUTION)

        self.ui_GotoField = VCSpinbox(self)
        self.ui_GotoField.setValue(0)
        self.ui_GotoField.setToolTip("Goto Frame")
        
        self.ui_InfoLabel = QtWidgets.QLabel(self)
        self.ui_InfoLabel.setStyleSheet("QLabel { border: 1px solid darkgray; border-radius: 3px; color: inherit; background: lightblue} ");
        self.ui_InfoLabel.setText("")
        self.ui_InfoLabel.setToolTip("Infos about the video position")
        
        self.ui_AudioModeLabel = QtWidgets.QLabel(self)
        self.ui_AudioModeLabel.setStyleSheet("QLabel { border: 1px solid darkgray; border-radius: 3px; color: inherit; background: lightgreen} ");
        self.ui_AudioModeLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.ui_AudioModeLabel.setToolTip("Toggle if audio should be saved")
        
        self.pixAudioOn = QtGui.QPixmap()
        #self.pixAudioOn.load("icons/speaker-high.png")
        self.pixAudioOn.load(ICOMAP.ico("audioOn"))
        self.pixAudioOn = self.pixAudioOn.scaledToWidth(32, mode=Qt.TransformationMode.SmoothTransformation)
        self.pixAudioOff = QtGui.QPixmap()
        #self.pixAudioOff.load("icons/speaker-muted.png")
        self.pixAudioOff.load(ICOMAP.ico("audioOff"))
        self.pixAudioOff = self.pixAudioOff.scaledToWidth(32, mode=Qt.TransformationMode.SmoothTransformation)
        
        self.ui_CutModeLabel = QtWidgets.QLabel(self)
        self.ui_CutModeLabel.setStyleSheet("QLabel { border: 1px solid darkgray; border-radius: 3px; color: inherit; background: lightgreen} ");
        self.ui_CutModeLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.ui_CutModeLabel.setToolTip("Toggle if exact or fast cut")
        
        self.ui_BackendLabel = QtWidgets.QLabel(self)
        self.ui_BackendLabel.setStyleSheet("QLabel { border: 1px solid darkgray; border-radius: 3px; color: inherit; background: lightgreen} ");
        self.ui_BackendLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.ui_BackendLabel.setToolTip("Toogle if precise remux or external ffmpeg")
        
        self.statusBox = QtWidgets.QHBoxLayout()
        self.statusBox.addWidget(self.ui_AudioModeLabel)
        self.statusBox.addWidget(self.ui_CutModeLabel)
        self.statusBox.addWidget(self.ui_BackendLabel)
        
        self.ui_List = self.__createListWidget()
        
        # self._listSplitter = QSplitter() ->add as widget...+QVBoxLayout
        # self._listSplitter.addWidget(iconList)
        
        # status bar
        self.statusbar = QtWidgets.QStatusBar(self)
        color = self.statusbar.palette().color(QtGui.QPalette.ColorRole.Window)
        darker = color.darker(150)
        lighter = color.darker(90)
        self.statusbar.setStyleSheet("QStatusBar { border: 1px inset %s; border-radius: 3px; background-color:%s;} "%(darker.name(),lighter.name()));
        self.statusbar.setSizeGripEnabled(False)
        self.statusbar.addPermanentWidget(self.__createProgressBar())
        self.buttonStop = QtWidgets.QToolButton(self)
        #self.buttonStop.setIcon(QtGui.QIcon('./icons/window-close.png'))
        self.buttonStop.setIcon(QtGui.QIcon(ICOMAP.ico("buttonStop")))
        self.buttonStop.setIconSize(QtCore.QSize(20, 20))
        self.buttonStop.setVisible(False)
        self.buttonStop.setToolTip("Stop processing")
        self.statusbar.addPermanentWidget(self.buttonStop, 0)
        self.setLayout(self.makeGridLayout())
        self.adjustSize()

    def makeGridLayout(self):
        gridLayout = QtWidgets.QGridLayout()
        self.ui_List.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Expanding)
        self.ui_List.setMaximumWidth(round(SIZE_ICON * 2.6))
        gridLayout.addWidget(self.ui_List, 0, 0, 5, 1)
        # from row,from col, rowSpan, columnSpan
        gridLayout.addWidget(self.ui_VideoFrame, 0, 1, 4, -1);
        gridLayout.addWidget(self.ui_GotoField, 4, 1, 1, 2)
        gridLayout.addWidget(self.ui_InfoLabel, 4, 3, 1, 6)
        gridLayout.addLayout(self.statusBox, 4, 9, 1, -1)
        gridLayout.addWidget(self.ui_Slider, 5, 0, 1, 11)
        gridLayout.addWidget(self.ui_Dial, 5, 11, 1, -1)
        gridLayout.addWidget(self.statusbar, 6, 0, 1, 12)
        
        gridLayout.setRowStretch(1, 1)

        return gridLayout
    #unused
    def makeBoxLayout(self):
        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.ui_VideoFrame)
        vbox.addWidget(self.ui_InfoLabel);
        
        slidehbox = QtWidgets.QHBoxLayout()
        slidehbox.addWidget(self.ui_Slider)
        slidehbox.addWidget(self.ui_Dial)

        midHBox = QtWidgets.QHBoxLayout()
        midHBox.addWidget(self.ui_List)
        self.ui_List.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
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

    #pos correction from somewhere else (edit or dial) -no need to trigger anything
    def syncSliderPos(self,pos): 
        if pos == self.ui_Slider.value():
            return
        if not self.ui_Slider.isSliderDown():
            self.ui_Slider.blockSignals(True)
            self.ui_Slider.setSliderPosition(pos)
            self.ui_Slider.blockSignals(False)
            
    
    def setSliderTicks(self, ticks):
        self.ui_Slider.setSingleStep(ticks)
        self.ui_Slider.setPageStep(ticks * 2)
    
    def setGotoFieldMaximum(self, count):
        self.ui_GotoField.blockSignals(True)
        self.ui_GotoField.setMaximum(count)
        self.ui_GotoField.blockSignals(False)
    
    #add cutmark with pixmap sized SIZE_ICON
    def addCutMark(self,cutEntry,rowIndex):
        item = QtWidgets.QListWidgetItem()
        item.setSizeHint(QtCore.QSize(SIZE_ICON, self.ITEM_HEIGHT))
        item.setIcon(QtGui.QIcon(cutEntry.pixmap()))
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

        self.ui_Dial.finetune.connect(aVideoController.dialChanged)
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
        #rmAction = QtGui.QAction(QtGui.QIcon('icons/close-x.png'), 'Delete', self)
        rmAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("rmAction")), 'Delete', self)
        
        rmAction.triggered.connect(self._removeMarker)
        #rmAllAction = QtGui.QAction(QtGui.QIcon('icons/clear-all.png'), 'Remove all', self)
        rmAllAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("rmAllAction")), 'Remove all', self)
        rmAllAction.triggered.connect(self.purgeMarker)
        #self.gotoAction = QtGui.QAction(QtGui.QIcon('icons/go-next.png'), 'Goto', self)
        self.gotoAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("gotoAction")), 'Goto', self)
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
        self.gotoAction.setEnabled(enable)
        self.ui_GotoField.setEnabled(enable)

    def updateProgressBar(self, percent):
        self.progressBar.setValue(percent)

    def __createListWidget(self):
        iconList = QtWidgets.QListWidget()
        iconList.setAlternatingRowColors(True)
        iconList.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        #TODO: Respect colors - needs delegate
        iconList.setStyleSheet("QListView{outline:none;} QListWidget::item:selected { background: #28D9FF;} ")  # that text color seems not to work!
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
        self._listMenu.exec(self.ui_List.viewport().mapToGlobal(position)) 
        

class MainFrame(QtWidgets.QMainWindow):
    
    def __init__(self, qapp,aPath=None):
        self._isStarted=False
        self.__qapp=qapp
        
        super(MainFrame, self).__init__()
        self.setWindowIcon(getAppIcon())
        self.settings = SettingsModel(self)
        self._videoController = VideoControl(self,aPath)
        self._widgets = self.initUI()
        self._widgets.hookEvents(self._videoController)
        self.settings.update()
        
        self.centerWindow()
        self._widgets.enableUserActions(False)
        self.show()
        qapp.applicationStateChanged.connect(self.__queueStarted) 
    
    def initUI(self):
        
        #self.exitAction = QtGui.QAction(QtGui.QIcon('icons/window-close.png'), 'Exit', self)
        self.exitAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("buttonStop")), 'Exit', self)
        self.exitAction.setShortcut('Ctrl+Q')
        self.exitAction.triggered.connect(QApplication.quit)
        
        #self.loadAction = QtGui.QAction(QtGui.QIcon('./icons/loadfile.png'), 'Load Video', self)
        self.loadAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("loadAction")), 'Load Video', self)
        self.loadAction.setShortcut('Ctrl+L')
        self.loadAction.triggered.connect(self.loadFile)

        #self.startAction = QtGui.QAction(QtGui.QIcon('./icons/start-icon.png'), 'Include from here', self)
        self.startAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("startAction")), 'Include from here', self)
        self.startAction.setShortcut('Ctrl+G')
        self.startAction.triggered.connect(self._videoController.addStartMarker)

        #self.stopAction = QtGui.QAction(QtGui.QIcon('./icons/stop-red-icon.png'), 'Exclude from here', self)
        self.stopAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("stopAction")), 'Exclude from here', self)
        self.stopAction.setShortcut('Ctrl+H')
        self.stopAction.triggered.connect(self._videoController.addStopMarker)
        
        #self.saveAction = QtGui.QAction(QtGui.QIcon('./icons/save-as-icon.png'), 'Save the video', self)
        self.saveAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("saveAction")), 'Save the video', self)
        self.saveAction.setShortcut('Ctrl+S')
        self.saveAction.triggered.connect(self.saveVideo)
        
        #self.infoAction = QtGui.QAction(QtGui.QIcon('./icons/info.png'), 'Codec info', self)
        self.infoAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("infoAction")), 'Codec info', self)
        self.infoAction.setShortcut('Ctrl+I')
        self.infoAction.triggered.connect(self.showCodecInfo)
        
        #self.playAction = QtGui.QAction(QtGui.QIcon('./icons/play.png'), 'Play video', self)
        self.playAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("playStart")), 'Play video', self)
        self.playAction.setShortcut('Ctrl+P')
        self.playAction.triggered.connect(self.playVideo)
        
        #self.photoAction = QtGui.QAction(QtGui.QIcon('./icons/screenshot.png'), 'Take screenshot', self)
        self.photoAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("photoAction")), 'Take screenshot', self)
        self.photoAction.setShortcut('Ctrl+P')
        self.photoAction.triggered.connect(self.takeScreenShot)
        
        '''
        the settings menues
        '''
#         self.extractMP3 = QtGui.QAction(QtGui.QIcon('./icons/stop-red-icon.png'),"Extract MP3",self)
        #self.mediaSettings = QtGui.QAction(QtGui.QIcon('./icons/settings.png'), "Output settings", self)
        self.mediaSettings = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("mediaSettings")), "Output settings", self)
        self.mediaSettings.setShortcut('Ctrl+T')
        self.mediaSettings.triggered.connect(self.openMediaSettings)

        '''
        audio language selection
        '''
        #self.langSettings = QtGui.QAction(QtGui.QIcon('./icons/langflags.png'), "Language settings", self)
        self.langSettings = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("langSettings")), "Language settings", self)
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

        widgets = LayoutWindow(self.settings)
        self.setCentralWidget(widgets);
        self.setWindowTitle("VideoCut")
      
        widgets.ui_VideoFrame.trigger.connect(self._videoController._onUpdateInfo)
        self.settings.trigger.connect(self._videoController.onSettingsChanged)
        
        # connect the labels to their dialogs
        # if not "self" - stops if out of scope!
        
        #--TOGGLE IT!
        
        self.audiofilter = SignalOnEvent(widgets.ui_AudioModeLabel)
        #self.audiofilter.clicked.connect(self.openMediaSettings)
        self.audiofilter.clicked.connect(self.settings.toggleMute)
        
        self.cutfilter = SignalOnEvent(widgets.ui_CutModeLabel)
        #self.cutfilter.clicked.connect(self.openMediaSettings)
        self.cutfilter.clicked.connect(self.settings.toggleEncode)
        
        self.backendfilter = SignalOnEvent(widgets.ui_BackendLabel)
        #self.backendfilter.clicked.connect(self.openMediaSettings)
        self.backendfilter.clicked.connect(self.settings.toggleRemux)
        self.enableActions(False) 
        return widgets

    ''' this is the place to start all graphical actions. Queue is running '''
    def __queueStarted(self,state):
        if state==Qt.ApplicationState.ApplicationActive:
            self.__qapp.disconnect()
            self._isStarted=True
            self._videoController.prepare()
    
    def isActivated(self):
        return self._isStarted
    
    def centerWindow(self):
        frameGm = self.frameGeometry()
        #screen = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
        #centerPoint = QApplication.desktop().screenGeometry(screen).center()
        centerPoint = self.screen().availableGeometry().center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())
    
    def updateWindowTitle(self, text):
        self.setWindowTitle("VideoCut - " + text)
    
    def openLanguageSettings(self):
        if self._videoController.streamData is None:
            return
        langMap = Cutter.IsoMap()
        lang = self.settings.getPreferedLanguageCodes()
        dlg = LanguageSettingsDialog(self, lang, langMap, self._videoController.getLanguages())
        if dlg.exec():
            self.settings.setPreferedLanguageCodes(dlg.getLanguages())
     
    def showInfo(self, text):
        self._widgets.showInfo(text)

    def syncSpinButton(self, frameNbr):
        self._widgets.syncSpinButton(frameNbr)

    def syncSliderPos(self, pos):
        self._widgets.syncSliderPos(pos)
        
    def setDialResolution(self, fps):
        self._widgets.setDialResolution(fps)

    def setGotoMaximum(self, count):
        self._widgets.setGotoFieldMaximum(count)

    def setSliderTicks(self, ticks):
        self._widgets.setSliderTicks(ticks)        

    def addCutMark(self, cutEntry, rowIndex):
        self._widgets.addCutMark(cutEntry, rowIndex)
        
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
        initalPath =self._videoController.getSourceDir()
        result = QtWidgets.QFileDialog.getOpenFileName(parent=self, directory=initalPath, caption="Load Video");
        if result[0]:
            fn = self.__encodeQString(result)
            self._widgets.clearMarkerList()
            self._videoController.clearVideoCutEntries()
            self._videoController.setFile(fn)  # encode error: str(result)
            
    def saveVideo(self):
        initalPath = self._videoController.getSourceFile()#The original filename...
        targetPath = self._videoController.getTargetFile()
        if not targetPath:
            self.showWarning("Can't process file!")
            return
        extn = self._videoController.getAllowedExtensions()
        fileFilter = "Video Files (%s);;All Files(*.*)" % extn
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
        try:
            streamData = self._videoController.streamData 
            container = streamData.formatInfo;
            videoData = streamData.getVideoStream()
            audioData = streamData.getAudioStream()
            if audioData is None:
                acodec = "N.A."
            else:
                acodec = audioData.getCodec();
                
            # text = '<table border=0 cellspacing="3",cellpadding="2"><tr border=1><td><b>Video Codec:</b></td><td> %s </td></tr><td><b>Dimension:</b></td><td> %s x %s </td></tr><tr><td><b>Aspect:</b></td><td> %s </td></tr><tr><td><b>FPS:</b></td><td> %s </td></tr><tr><td><b>Duration:</b></td><td> %s </td></tr><tr><td><b>Audio codec:</b></td><td> %s </td></tr></table>' %(videoData.getCodec(),videoData.getWidth(),videoData.getHeight(),videoData.getAspectRatio(),videoData.frameRateMultiple(),videoData.duration(),audioData.getCodec())
            text = """<table border=0 cellspacing="3",cellpadding="2">
                    <tr border=1><td><b>Container:</b></td><td> %s </td></tr>
                    <tr><td><b>Bitrate:</b></td><td> %s [kb/s]</td></tr>
                    <tr><td><b>Size:</b></td><td> %s [kb] </td></tr>
                    <tr><td><b>is TS:</b></td><td> %s </td></tr>
                    <tr><td><b>Video Codec:</b></td><td> %s </td></tr>
                    <tr><td><b>Dimension:</b></td><td> %sx%s </td></tr>
                    <tr><td><b>Aspect:</b></td><td> %s </td></tr>
                    <tr><td><b>FPS:</b></td><td> %.2f </td></tr>
                    <tr><td><b>Duration:</b></td><td> %.1f [sec]</td></tr>
                    <tr><td><b>Audio codec:</b></td><td> %s </td></tr>
                    </table>""" % (container.formatNames()[0], container.getBitRate(), container.getSizeKB(), streamData.isTransportStream(), videoData.getCodec(), videoData.getWidth(), videoData.getHeight(), videoData.getAspectRatio(), self._videoController.fps(), videoData.duration(), acodec)
            entries = []
            entries.append("""<br><\br><table border=0 cellspacing="3",cellpadding="2">""")
            #TODO -check the cvInfos (CvPlayer)
            
            #for key, value in cvInfo.items():
            for key, value in VideoPlugin.info().items():
                entries.append("<tr border=1><td><b>")
                entries.append(key)
                entries.append(":</b></td><td> ")
                entries.append(value)
                entries.append("</td></tr>")
            entries.append("</table>");
            
            text2 = ''.join(entries)
                                        
        except:
            Log.exception("Invalid codec format")
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
            #self.playAction.setIcon(QtGui.QIcon('./icons/pause.png'))
            self.playAction.setIcon(QtGui.QIcon(ICOMAP.ico("playPause")))
        else:
            self.__enableActionsOnVideoPlay(True)
            #self.playAction.setIcon(QtGui.QIcon('./icons/play.png'))            
            self.playAction.setIcon(QtGui.QIcon(ICOMAP.ico("playStart")))
               
    #-------- ACTIONS  END ----------    

    def __enableActionsOnVideoPlay(self, enable):
        self.enableControls(enable)
        self.loadAction.setEnabled(enable)
        self.saveAction.setEnabled(enable) 
        self._widgets.gotoAction.setEnabled(enable)        

    def __getInfoDialog(self, text):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dlg.setWindowTitle("Video Infos")
        layout = QtWidgets.QVBoxLayout(dlg)
        label = QtWidgets.QLabel(text)
        label.sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        label.setSizePolicy(label.sizePolicy)
        label.setMinimumSize(QtCore.QSize(450, 40))
        layout.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetFixedSize)
        layout.addWidget(label)
        return dlg

    def getErrorDialog(self, text, infoText, detailedText):
        dlg = QtWidgets.QMessageBox(self)
        dlg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        dlg.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dlg.setWindowTitle("Error")
        dlg.setText(text)
        dlg.setInformativeText(infoText)
        dlg.setDetailedText(detailedText)
        dlg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        spacer = QtWidgets.QSpacerItem(300, 0, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
        layout = dlg.layout()
        layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())
        return dlg
    
    def getMessageDialog(self, text, infoText):
        # dlg = DialogBox(self)
        dlg = QtWidgets.QMessageBox(self)
        dlg.setIcon(QtWidgets.QMessageBox.Icon.Information)
        dlg.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dlg.setWindowTitle("Notice")
        dlg.setText(text)
        dlg.setInformativeText(infoText)
        dlg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        # Workaround to resize a qt dialog. WTF!
        spacer = QtWidgets.QSpacerItem(300, 0, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
        layout = dlg.layout()
        layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())
        
        # dlg.setMinimumSize(450, 0)
        return dlg;
    
    def closeEvent(self,event):
        self._videoController.shutDown()
        try:
            super(MainFrame, self).closeEvent(event)
        except:
            Log.exception("Error Exit")

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


class SettingsModel(QtCore.QObject):
    trigger = pyqtSignal(object)
    
    def __init__(self, mainframe):
        # keep flags- save them later
        super(SettingsModel, self).__init__()
        self.fastRemux = vc_config.getBoolean("useRemux",True)
        self.reencoding = vc_config.getBoolean("recode",False)
        self.muteAudio = vc_config.getBoolean("muteAudio",False)
        self.iconSet = vc_config.get("icoSet",IconMapper.DEFAULT)
        self.mainFrame = mainframe
        self.showSubid=vc_config.getInt("subtitles",0)  #id if subtitle should be presented. mpv only
        self.showGL=vc_config.getBoolean("openGL",True) #GL Widgets, mpv only
    
    def update(self):
        cutmode = "Fast"
        mode = "FFMPEG"
        audio = self.mainFrame._widgets.pixAudioOn
        if self.fastRemux:
            mode = "REMUX"
        if self.reencoding:
            cutmode = "Exact"
        if self.muteAudio:
            audio=self.mainFrame._widgets.pixAudioOff
        
        self.mainFrame._widgets.ui_AudioModeLabel.setPixmap(audio)
        self.mainFrame._widgets.ui_CutModeLabel.setText(cutmode)
        self.mainFrame._widgets.ui_BackendLabel.setText(mode)
        
        if self.fastRemux:
            vc_config.set("useRemux", "True")
        else:
            vc_config.set("useRemux", "False")

        if self.reencoding:
            vc_config.set("recode", "True")
        else:
            vc_config.set("recode", "False")
        vc_config.set("subtitles",str(self.showSubid))
        
        if self.showGL:
            vc_config.set("openGL", "True")
        else:
            vc_config.set("openGL", "False")
            
        if self.muteAudio:
            vc_config.set("muteAudio", "True")
        else:
            vc_config.set("muteAudio", "False")
        
        #SET the icoset
        vc_config.set("icoSet", self.iconSet)
        
        vc_config.store()
        self.trigger.emit(self)
        
    def getPreferedLanguageCodes(self):
        lang = vc_config.get("LANG")
        if lang is None:
            lang = ["deu", "eng", "fra"]  # default
        else:
            lang = json.loads(lang)
        return lang

    def processSubtitles(self):
        return self.showSubid>0

    def setPreferedLanguageCodes(self, langList):
        vc_config.set("LANG", json.dumps(langList))
        vc_config.store()
    
    #UI toggle functions
    def toggleRemux(self):
        self.fastRemux = not self.fastRemux
        self.update()

    def toggleEncode(self):
        self.reencoding = not self.reencoding
        self.update()

    def toggleMute(self):
        self.muteAudio = not self.muteAudio
        self.update()    
    
       
        
class SettingsDialog(QtWidgets.QDialog):

    def __init__(self, parent, model):
        """Init UI."""
        super(SettingsDialog, self).__init__(parent)
        self.model = model
        self.init_ui()

    def init_ui(self):
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.setWindowTitle("Settings")

        outBox = QtWidgets.QVBoxLayout()
        # outBox.addStretch(1)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        versionBox = QtWidgets.QHBoxLayout()
        lbl = QtWidgets.QLabel("Version:")
        ver = QtWidgets.QLabel(Version)
        versionBox.addStretch(1)
        versionBox.addWidget(lbl)
        versionBox.addWidget(ver)
        versionBox.addStretch(1)

        frame1 = QtWidgets.QFrame()
        frame1.setFrameStyle(QtWidgets.QFrame.Shape.Box | QtWidgets.QFrame.Shadow.Sunken)
        frame1.setLineWidth(1)
       
        frame2 = QtWidgets.QFrame()
        frame2.setFrameStyle(QtWidgets.QFrame.Shape.Box | QtWidgets.QFrame.Shadow.Sunken)
        frame2.setLineWidth(1)
       
        #frame3 = QtWidgets.QFrame()
        #frame3.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Sunken)
        #frame3.setLineWidth(1)
       
        encodeBox = QtWidgets.QVBoxLayout(frame1)
        self.check_reencode = QtWidgets.QCheckBox("Reencode (Slow!)")
        self.check_reencode.setToolTip("Force exact cut. Makes it real slow!")
        self.check_reencode.setChecked(self.model.reencoding)
        # connect
        self.check_reencode.stateChanged.connect(self.on_reencodeChanged)
        self.exRemux = QtWidgets.QCheckBox("VideoCut Muxer")
        self.exRemux.setToolTip("Uses the fast remux code instead of ffmpeg commandline")
        self.exRemux.setChecked(self.model.fastRemux)
        self.exRemux.stateChanged.connect(self.on_fastRemuxChanged)

        self.muteAudio = QtWidgets.QCheckBox("Mute audio - Video only")
        self.muteAudio.setToolTip("Cut the video without any audio tracks")
        self.muteAudio.setChecked(self.model.muteAudio)
        self.muteAudio.stateChanged.connect(self._onAudioChanged)  

        self.showSub = QtWidgets.QCheckBox("Show subtitles")
        self.showSub.setToolTip("Toggle show subtitles (mpv only)")
        self.showSub.setChecked(self.model.showSubid>0)
        self.showSub.stateChanged.connect(self._onSubChanged)
        
        self.showGL = QtWidgets.QCheckBox("Use GL Widgets(mpv only) Restart required")
        self.showGL.setToolTip("Use GL widgets - must be activated for wayland\n Restart app on change")
        self.showGL.setChecked(self.model.showGL>0)
        self.showGL.stateChanged.connect(self._onGLChanged)        


        lbl = QtWidgets.QLabel("< Icon theme. Restart required")
        self.setIconTheme = QtWidgets.QComboBox()
        themes=ICOMAP.themes()
        for item in themes:
            self.setIconTheme.addItem(item)
        self.setIconTheme.setCurrentText(self.model.iconSet)
        self.setIconTheme.currentTextChanged.connect(self._onIconThemeChanged)
        self.setIconTheme.setToolTip("Select icon theme - restart to take effect")
        comboBox= QtWidgets.QHBoxLayout()
        comboBox.addWidget(self.setIconTheme)
        comboBox.addWidget(lbl)

        
        encodeBox.addWidget(self.check_reencode)
        encodeBox.addWidget(self.exRemux)
        encodeBox.addWidget(self.muteAudio)
        #expoBox = QtWidgets.QVBoxLayout(frame2)
        #expoBox.addWidget(self.exRemux)
        
        subBox= QtWidgets.QVBoxLayout(frame2)
        subBox.addWidget(self.showSub)
        subBox.addWidget(self.showGL)
        subBox.addLayout(comboBox)
        
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
        self.model.reencoding = QtCore.Qt.CheckState.Checked.value == reencode
        self.model.update()
        
    def on_fastRemuxChanged(self, isFastRemux):
        self.model.fastRemux = QtCore.Qt.CheckState.Checked.value == isFastRemux
        self.model.update() 
    
    def _onSubChanged(self,showsub):
        if showsub:
            val=1
        else:
            val=0
        self.model.showSubid=val
        self.model.update()       

    def _onGLChanged(self,useGL):
        self.model.showGL=QtCore.Qt.CheckState.Checked.value == useGL
        self.model.update() 
        
    def _onAudioChanged(self,muteAudio):
        self.model.muteAudio = QtCore.Qt.CheckState.Checked.value == muteAudio
        self.model.update()
        
    def _onIconThemeChanged(self,text):
        self.model.iconSet=text
        self.model.update()
        
class LanguageSettingsDialog(QtWidgets.QDialog):

    def __init__(self, parent, defCodes, langData, videoCodes):
        """Init UI."""
        super(LanguageSettingsDialog, self).__init__(parent)
        self.iso639 = langData
        self.available3LetterCodes=videoCodes
        self.setupLanguages(defCodes)
        self.init_ui()
    
    def init_ui(self):
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.setWindowTitle("Language")
        frame1 = QtWidgets.QFrame()
        frame1.setFrameStyle(QtWidgets.QFrame.Shape.Box | QtWidgets.QFrame.Shadow.Sunken)
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
        #pix.load("icons/info.png")
        pix.load(ICOMAP.ico("infoAction"))
        pix = pix.scaledToWidth(32, mode=Qt.TransformationMode.SmoothTransformation)
        info = QtWidgets.QLabel("")
        info.setPixmap(pix)
        btnHBox.addWidget(info)
        btnHBox.addWidget(self.lbl)
        self.button_box = QtWidgets.QDialogButtonBox(self)
        self.button_box.setStandardButtons(QtWidgets.QDialogButtonBox.StandardButton.Cancel | QtWidgets.QDialogButtonBox.StandardButton.Save)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        btnHBox.addWidget(self.button_box)
        
        dlgBox.addWidget(frame1)
        dlgBox.addLayout(btnHBox)
        
        self.setLayout(dlgBox)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.setMinimumSize(400, 0)   
        self.setModelData()
        item = self.listWidget.item(0)
        item.setSelected(True)
    
    def onChange(self, widget):
        state = widget.checkState()
        if state == Qt.CheckState.Checked:
            self._limitCheckedItems()
    
    def _limitCheckedItems(self):
        selected = []
        for index in range(self.listWidget.count()):
            item = self.listWidget.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item)
                
        if len(selected) > 3:
            test = selected.pop()
            test.setCheckState(Qt.CheckState.Unchecked)
        
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
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            if lang in self.defaultCodes:
                item.setCheckState(QtCore.Qt.CheckState.Checked)
            else:
                item.setCheckState(QtCore.Qt.CheckState.Unchecked)
            self.listWidget.addItem(item)
            cnt += 1
        
        return self.listWidget.count() 
    
    def getLanguages(self):
        lang = []
        for index in range(self.listWidget.count()):
            item = self.listWidget.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                #code= self.iso639.codeForCountry(item.text(),self.available3LetterCodes)
                lang.append(item.text()) #save the intl language
        
        return lang

    #defCodes = saved user selected codes (INTL name), avail = Codes in film
    def setupLanguages(self,defCodes): 
        self.avail = []
        self.defaultCodes = []
        for intlName in defCodes:
            #self.defaultCodes.append(self.iso639.countryForCode(code))
            self.defaultCodes.append(intlName)
             
        for code in self.available3LetterCodes:
            #self.avail.append(codeToLang.get(code,code))
            self.avail.append(self.iso639.countryForCode(code))
     
        
             
'''
  handles the events from the GUI, connecting to the VideoPlayer and the VideoWidget... 
'''        
class VideoControl(QtCore.QObject):

    def __init__(self, mainFrame,aPath):
        super(VideoControl, self).__init__()
        self.player = None
        self.gui = mainFrame
        self._initTimer()
        self.videoCuts = []
        self.currentPath = OSTools().getHomeDirectory()
        self._currentFile=aPath
        self.streamData = None
        self.lastError = None
        VideoPlugin.controller=self

    #the queue should be running now
    def prepare(self):
        if self._currentFile is None:
            VideoPlugin.showBanner()
        else:
            self.setFile(self._currentFile)
            
    def _initTimer(self):
        self._dialThread=DialThread(self._dxDialFrame)#exec in dial thread
        #self._dialThread.triggered.connect(self._dxDialFrame) #if in main thread-blocks any input
   
    #Why use soureextension? This may not be the original one.
    def getSourceFile(self):
        if self.streamData is not None:
            return self._currentFile
        return self.currentPath

    def getSourceDir(self):
        return OSTools().getDirectory(self.currentPath)

    def fps(self):
        if self.player:
            return self.player.fps
        else:
            return 1.0

    def getTargetFile(self):
        if self.streamData is not None:
            ext = self.streamData.getTargetExtension()
            if ext is None:
                return None 
            target= self.currentPath + "." + ext
            if target is None:
                return None 
            if self._currentFile == target:
                target= self.currentPath + "-cut." + ext
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
        self.gui.showWarning(self.lastError+"\nCheck log in .config/VideoCut for details")
        self.lastError = None
        
    #-- Menu handling ---    
    def setFile(self, filePath):
        if self.player is not None:
            VideoPlugin.closePlayer()
            self.videoCuts = []
        try:
            self.streamData = FFStreamProbe(filePath)
            self.currentPath = OSTools().getPathWithoutExtension(filePath);
            self._currentFile=filePath 
            if not self.streamData:
                raise Exception('Invalid file')
            
            QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            self.player = VideoPlugin.initPlayer(filePath, self.streamData)
            VideoPlugin.validate()
            
            self.__initSliderTicks()
            self.gui.enableControls(True)
            self.gui.enableActions(True)
            
            self.onSettingsChanged(self.gui.settings)
            self.gui.updateWindowTitle(OSTools().getFileNameOnly(filePath))
            self._initVideoViews()
        except Exception as ex:
            Log.exception("Setting file")
            if not OSTools().fileExists(filePath):
                self.lastError = "File not found"
            else:
                self.lastError = str(ex)
            
            VideoPlugin.showBanner()
            self.gui.enableControls(False)
            if self.gui.isActivated():
                self.displayWarningMessage()
        finally:
            QApplication.restoreOverrideCursor() 
    
    def statusbar(self):
        return self.gui._widgets.statusMessenger
    
    def addStartMarker(self):
        #TODO switch to timebase: ts=self.player.getCurrentFrameTime()
        pos=self.player.getCurrentFrameNumber()
        self._createVideoCutEntry(pos,VideoCutEntry.MODE_START)
        self.statusbar().say("Start video")

    def addStopMarker(self):
        #TODO switch to timebase: ts=self.player.getCurrentFrameTime()
        pos=self.player.getCurrentFrameNumber()
        self._createVideoCutEntry(pos,VideoCutEntry.MODE_STOP)
        self.statusbar().say("Stop video")

    def _createVideoCutEntry(self, pos, mode):
        cutEntry = VideoCutEntry(pos, -1, mode)
        VideoPlugin.setCutEntry(cutEntry)
        self._addVideoCut(cutEntry, True)
        
        
    def _restoreVideoCutEntry(self,cutEntry,mode):
        isLegacy = cutEntry.pixmap() is None 
        if isLegacy: #compatibility: read data and generate a thumbnail
            VideoPlugin.setCutEntry(cutEntry,restore=True)
        self._addVideoCut(cutEntry, isLegacy)
        return isLegacy
                

    def _addVideoCut(self, cutEntry, updateXML):
        rowIndex = len(self.videoCuts)
        for idx, videoEntry in enumerate(self.videoCuts):
            frameNbr = videoEntry.frameNumber
            testNbr = cutEntry.frameNumber
            if testNbr < frameNbr:
                rowIndex = idx
                break
        
        self.videoCuts.insert(rowIndex, cutEntry)
        self.gui.addCutMark(cutEntry, rowIndex)
        if updateXML:
            XMLAccessor(self.currentPath).writeXML(self.videoCuts)

    def _initVideoViews(self):
        VideoPlugin.showFirstFrame()
        #messages are not ready here...
        self.restoreVideoCuts()
        self.statusbar().say(("Ready"))
        

    def restoreVideoCuts(self):
        QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        recover=False
        try:
            cutList = XMLAccessor(self.currentPath).readXML()
        except Exception as error:
            Log.exception("Error restore:")  
            return  
        for cut in cutList:
            mode = VideoCutEntry.MODE_STOP
            if cut.isStartMode():
                mode = VideoCutEntry.MODE_START
            recover = self._restoreVideoCutEntry(cut,mode)
        if recover:    
            VideoPlugin.showFirstFrame()

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
        #self.__dispatchShowFrame(cut.frameNumber)
        self._gotoFrame(cut.frameNumber)
    
    # callback from stop button
    def killSaveProcessing(self):
        if self.cutter is None:
            Log.info("Can't kill process")
        else:
            self.cutter.stopCurrentProcess()

    def saveVideo(self, path):
        spanns = []
        block = None
        for cutEntry in self.videoCuts:
            
            if cutEntry.isStartMode():
                if block:
                    Log.info("Start invalid: %s" % (cutEntry.getTimeString()))
                else:
                    block = []
                    block.append(cutEntry)
            else:
                if block:
                    block.append(cutEntry)
                    spanns.append(block)
                    block = None
                else:
                    Log.info("Stop ignored:" + cutEntry.getTimeString())
        #src = self.player._file
        src = self._currentFile
        # need that without extension!
        self.cutAsync(src, path, spanns)
    
    #-- Menu handling end ---
    #-- Exec cutting ---
    def calculateNewVideoTime(self, spanns):
        delta = 0;
        for index, cutmark in enumerate(spanns):
            t1 = cutmark[0].timeDelta()
            t2 = cutmark[1].timeDelta()
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
        msg = worker.msg 
        self.gui.stopProgress()
        worker.quit()
        worker.wait();
        if self.cutter is None or self.cutter.wasAborted():
            self.gui.getMessageDialog("Operation failed", "Cut aborted").show()
        elif self.cutter.hasErrors():
            self.lastError = "Remux failed: %s " % (self.cutter.getErrors()[0])
            self.displayWarningMessage()
        elif msg is not None:
            self.lastError = "Remux failed: %s " % (msg)
            self.displayWarningMessage()
        else:
            dx = time() - self.cutTimeStart
            delta = Cutter.timedeltaToFFMPEGString(timedelta(seconds=dx))
            self.gui.getMessageDialog("Operation done", "Cutting time: %s" % delta,).show()
        self.cutter = None 

    '''
    FFMPEG cutting API
    '''    
    def __makeCuts(self, srcPath, targetPath, spanns, settings):
        config = CuttingConfig(srcPath, targetPath, settings.getPreferedLanguageCodes(),settings.processSubtitles())
        config.streamData = self.streamData
        config.reencode = settings.reencoding
        config.messenger = self.statusbar()
        config.muteAudio = settings.muteAudio

        self.cutter = FFMPEGCutter(config, self.calculateNewVideoTime(spanns))
        self.cutter.ensureAvailableSpace()
        slices = len(spanns)
        for index, cutmark in enumerate(spanns):
            t1 = cutmark[0].timeDelta()
            t2 = cutmark[1].timeDelta()
            hasSucess = self.cutter.cutPart(t1, t2, index, slices)
            if not hasSucess:
                Log.error("***Cutting failed***")
                return
        self.cutter.join()  
        
    '''
    new VCCutter API
    '''
    def __directCut(self, srcPath, targetPath, spanns, settings):
        zTime=VideoPlugin.hasVideoOffset()
        config = CuttingConfig(srcPath, targetPath, settings.getPreferedLanguageCodes(),settings.processSubtitles(),zTime)
        config.streamData = self.streamData
        config.messenger = self.statusbar()
        config.reencode = settings.reencoding
        config.muteAudio = settings.muteAudio
        
        self.cutter = VCCutter(config)
        if self.cutter.setupBinary():
            self.cutter.cut(spanns)
    
    
    
    # we want 1 minute per single step
    def __initSliderTicks(self):
        _fps = self.fps()
        if self.player.framecount > 1:
            ratio = round(LayoutWindow.SLIDER_RESOLUTION * 60 * _fps / self.player.framecount, 1)
            self.gui.setSliderTicks(round(ratio))
            self.gui.setGotoMaximum(int(self.player.framecount))
        
    # connected to slider-called whenever position is changed.
    def sliderMoved(self, pos):
        if self.player is None or not self.player.isValid():
            self.gui.syncSliderPos(0)
            return

        frameNumber = round(self.player.framecount / LayoutWindow.SLIDER_RESOLUTION * pos, 0)
        self.__dispatchShowFrame(frameNumber)

    # display Frame with syncing the slider pos. Called by spinbutton/thumb selection.
    #some frames may not be moved. Make sure the spin button is NOT updated.
    def _gotoFrame(self, frameNumber=0):
        VideoPlugin.setFrameDirect(frameNumber)
    
    def __dispatchShowFrame(self, frameNumber):
        VideoPlugin.enqueueFrame(frameNumber)
    
    # connected to the dial
    def dialChanged(self, pos):
        if pos == 0:
            self._dialThread.dialStep(0,0)
            return

        res = math.exp((-0.2*abs(pos) +7.0)/ 3.0)
        steps = math.copysign(1, pos)*math.ceil(abs(pos)/5)
        ts=round(res*20)
        self._dialThread.dialStep(int(ts),steps)
 
    #called by dialThread-via "func" runs in dial thread, (via signal in main)
    def _dxDialFrame(self,pos):
        QApplication.processEvents()
        VideoPlugin.onDial(pos)
    
    
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
        isPlaying = VideoPlugin.toggleVideoPlay()
        self.gui.setVideoPlayerControls(isPlaying)
        return isPlaying
 
    def shutDown(self):
        VideoPlugin.shutDown()
        self._dialThread.stop()
 
    #callback settings
    def onSettingsChanged(self,settingsModel):
        VideoPlugin.changeSettings("subtitle",settingsModel.showSubid)

    '''
    plugin callbacks
    '''
    #called by plugin: self.updateUI.emit(frameNumber,self.player.framecount,timeinfo)
    def _onUpdateInfo(self,frameNbr,frameCount,timeMS):
        s = int(timeMS / 1000)
        ms = int(timeMS % 1000)
        ts = '{:02}:{:02}:{:02}.{:03}'.format(s // 3600, s % 3600 // 60, s % 60, ms)
        out = "<b>Frame:</b> %08d of %d <b>Time:</b> %s " % (frameNbr, int(frameCount) , ts)
        if not frameCount:
            sliderPos=0
        else:
            sliderPos = int(frameNbr * LayoutWindow.SLIDER_RESOLUTION / frameCount)
        self.gui.showInfo(out)
        self.gui.syncSpinButton(frameNbr) 
        self.gui.syncSliderPos(sliderPos)
                
    def syncVideoPlayerControls(self,enabled):
        self.gui.setVideoPlayerControls(enabled)


# -- threads

#Delegates a message into the main queue...Main loop must be present..
class Delegator(QtCore.QThread):
    kick = pyqtSignal()
    def __init__(self,func):
        QtCore.QThread.__init__(self)
        self.func=func

    def run(self):
        self.kick.emit()  
        self.quit()
        self.deleteLater()
        
    def go(self):
        self.kick.connect(self.func)
        self.start()




class SignalOnEvent(QtCore.QObject):
    clicked = pyqtSignal()
    
    def __init__(self, widget):
        QtCore.QObject.__init__(self)
        self.widget = widget
        widget.installEventFilter(self)

    def eventFilter(self, anyObject, event):
        if anyObject == self.widget:
            if event.type() == QtCore.QEvent.Type.MouseButtonRelease and anyObject.rect().contains(event.pos()):
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
        self.msg=None

    def run(self):
        try:
            self.function(*self.arguments)
        except Exception as ex:
            Log.exception("***Error in LongRunningOperation***")
            self.msg = "Error while converting: "+str(ex)
        finally:
            self.signal.emit(self)

    def startOperation(self):
        self.start()  # invokes run - process pending QT events
        sleep(0.5)
        QtCore.QCoreApplication.processEvents()



#Standard QT thread impl: starts thread in an infinite loop
#waits on mutex until woken. 
class DialThread(QtCore.QThread):
    triggered=pyqtSignal(int)
    def __init__(self,func):
        QtCore.QThread.__init__(self)
        self.delay=0
        self.condition = QtCore.QWaitCondition()
        self.mutex = QtCore.QMutex()
        self.func=func #function will be executed here, not in main thread
        self.step=0
        self.__running=True
        self.start()
        
    def run(self):
        while self.__running:
            if self.delay > 0.0:
                #self.triggered.emit(self.step)#would pass execution to the main thread->massive afterrun
                self.func(self.step) #Pro: no queue build up
                self.msleep(self.delay)#any other sleep breaks!
            else:
                self.__wait() #wait until needed
    
    def __wait(self):
        self.mutex.lock()
        self.condition.wait(self.mutex)
        self.mutex.unlock()
    
    def stop(self):
        self.__running=False
        self.condition.wakeOne()
    
    def dialStep(self,delay,step):
        self.step=step
        if delay == 0:
            self.delay=0
            return
        if self.delay==delay:
            return
        self.delay=delay
        self.condition.wakeOne()#wake up the long wait
                   

class StatusDispatcher(QtCore.QObject):
    signal = pyqtSignal(str)
    progressSignal = pyqtSignal(int)

    def __init__(self):
        QtCore.QObject.__init__(self)
    
    def say(self, aString):
        self.signal.emit(aString)
    
    def progress(self, percent):
        self.progressSignal.emit(round(percent))


class IconMapper():
    DEFAULT="default"
    def __init__(self,section="default"):
        self.section=section
        self._read()
        
    def _read(self):
        ipath=OSTools().joinPathes(OSTools().getWorkingDirectory(),"icons","icomap.json")
        with open(ipath) as fn:
            self.map = json.load(fn)
            
    def ico(self,name):
        key=name.strip()
        submap=self.map.get(self.section,self.DEFAULT)
        return submap.get(key,self.getDefault(key))
     
    def getDefault(self,name):
        return self.map[self.DEFAULT].get(name,"")   
    
    def themes(self):
        return self.map.keys()

WIN = None  

def handle_exception(exc_type, exc_value, exc_traceback):
    """ handle all exceptions """
    if WIN is not None:
        infoText = str(exc_value)
        detailText = "*".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        WIN.getErrorDialog("Unexpected error", infoText, detailText).show()
        Log.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

def parseOptions(args):
    res={}
    res["mpv"]=True
    res["logConsole"]=False
    res["file"]=None
    try:
        opts,args=getopt.getopt(args[1:], "cdp:", ["console","debug","player="])
        if len(args)==1:
            res["file"]=args[0]
    except getopt.GetoptError as err:
        print(err)
        sys.exit(2)
    
    for o,a in opts:
        if o in ("-d","--debug"):
            FFMPEGTools.setLogLevel("Debug")
        elif o in ("-p","--player"):
            if a in "cv":
                res["mpv"]=False
        elif o in ("-c","--console"):
            res["logConsole"]=True
        else:
            print("Undef:",o) 
    return res
                                           
def main():
    try:
        global WIN
        global ICOMAP
        global VideoPlugin
        global vc_config
        localPath = OSTools().getActiveDirectory() #won't work after setting WD
        wd= OSTools().getLocalPath(__file__)
        OSTools().setMainWorkDir(wd)
        vc_config = ConfigAccessor("VideoCut","vc.ini","videocut") #folder,name&section
        vc_config.read();

        argv = sys.argv
        app = QApplication(argv)
        app.setWindowIcon(getAppIcon())
        res=parseOptions(argv)
        FFMPEGTools.setupRotatingLogger("VideoCut",res["logConsole"])
        VideoPlugin=setUpVideoPlugin(res["mpv"])
        ICOMAP=IconMapper(vc_config.get("icoSet","default"))
        fn =res["file"]
        if fn is None:
            WIN = MainFrame(app)  # keep python reference!
        else:
            if not OSTools().isAbsolute(fn):
                fn=OSTools().joinPathes(localPath,fn)
            WIN = MainFrame(app,fn)  
        app.exec()
        #logging.shutdown()
    except:
        Log.exception("Error in main:")
        #ex_type, ex_value, ex_traceback
        sys_tuple = sys.exc_info()
        QtWidgets.QMessageBox.critical(None,"Error!",str(sys_tuple[1]))

#TODO: Respect theme
def stylesheet():
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# copyright (c) 2025 kanehekili (kanehekili.media@gmail.com)
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License,
# as published by the Free Software Foundation, either version 2 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the  GNU General Public License for more
# details.
#
# You did not receive a copy of the  GNU General Public License along with this program.  See
# <http://www.gnu.org/licenses/>.

'''
Created on Dec 4, 2025

@author: matze
based on:
https://github.com/mpv-player/mpv-examples/blob/master/libmpv/qt_opengl/mpvwidget.cpp
https://gitlab.com/robozman/python-mpv-qml-example/-/blob/master/main.py?ref_type=heads

'''

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QOpenGLContext, QCloseEvent
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QByteArray, pyqtSignal, pyqtSlot, QThread
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from lib.mpv import MPV, MpvGlGetProcAddressFn, MpvRenderContext
from FFMPEGTools import  FFStreamProbe, OSTools, ConfigAccessor
import sys, json, FFMPEGTools, getopt, traceback, locale
from threading import Condition
from MpvPlayer import SliderThread


global Log
global AppName
AppName="EasyPlayer"
Log = FFMPEGTools.Log
#####################################################
Version = "@xxx@"
#####################################################


def get_process_address(_, name):
    glctx = QOpenGLContext.currentContext()
    address = int(glctx.getProcAddress(QByteArray(name)))
    # return ctypes.cast(address, ctypes.c_void_p).value
    return address


class Player(QOpenGLWidget):
    ERR_IDS = ["No video or audio streams selected.", "Failed to recognize file format."]
    triggerUpdate = pyqtSignal(float)
    triggerInitialized = pyqtSignal()
    fileLoaded = pyqtSignal()
    syncPlayStatus = pyqtSignal(int)
    onError = pyqtSignal(str)
    
    def __init__(self, parent, path=None, isVirtual=False):
        super().__init__(parent)
        self.closePending = False
        self.seekLock = Condition()
        self.ctx = None
        self._timePos = 0;
        self.streamData = None
        self._demuxOffset = 0.1
        self.mpv = MPV(**self._getMPVArgs(isVirtual))
        self.filePath = path
        self._hookEvents()
        self._proc_addr_wrapper = MpvGlGetProcAddressFn(get_process_address)
        self.triggerUpdate.connect(self.do_update)  # works only if video
        self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.PartialUpdate)
        self.duration = 0
        self.sliderThread = None
        self.lastError = None
        self.isAudioOnly = False
        self.durString = "00:00:00"
        self._opengl_fbo=None
        
    def initializeGL(self) -> None:
        self.ctx = MpvRenderContext(
            self.mpv, 'opengl',
            opengl_init_params={
                'get_proc_address': self._proc_addr_wrapper
            },
        )
        if self.ctx:
            if FFMPEGTools.OSTools().fileExists("/proc/driver/nvidia/version"):
                self.mpv.hwdec = "nvdec"
                Log.info("Switched to nvdec")            
            self.ctx.update_cb = self._on_update
            self.triggerInitialized.emit()

    def setStreamData(self, fn):
        self.filePath = None
        if fn:
            try:
                self.streamData = FFStreamProbe(fn)
                self.filePath = fn
                self.lastError = None
                self.isAudioOnly = self.streamData.getVideoStream() is None
                self._tweak(self.streamData)
                tx = FFMPEGTools.OSTools().getFileNameOnly(fn)
                return True
            except IOError:
                Log.exception("Setting Stream Data")
                self.lastError = "Invalid media file"
                self.onError.emit(self.lastError)

    def _tweak(self, streamData):
        if streamData.isVC1Codec(): 
            self.mpv.hwdec_codecs = "vc1"
            Log.info("Optimized for VC1")  
        else:
            self.mpv.hwdec_codecs = "all"

    def asyncSeek(self, seconds):
        self._muteWhileSeeking(True)
        if not self.sliderThread:
            self.sliderThread = SliderThread(self.seek) 
        self.sliderThread.seekTo(seconds)

    def seek(self, seconds):
        self.mpv.seek(seconds, "absolute")
        self._waitSeekDone()
        
    def seekRelative(self, seconds):
        self.mpv.seek(seconds, "relative")
        self._waitSeekDone()
        
    def _waitSeekDone(self):
        self.mpv.observe_property("seeking", self._onSeek)
        with self.seekLock:
            self.seekLock.wait(timeout=3)
            self._muteWhileSeeking(False)

    def _onSeek(self, name, val):
        if val == False:
            with self.seekLock:
                self.seekLock.notify()
                self.mpv.unobserve_property("seeking", self._onSeek)                 

    def _hookEvents(self):
        self.mpv.observe_property("eof-reached", self._onPlayEnd)
        self.mpv.observe_property("time-pos", self._onTimePos)  # messes up timing!

    def resizeGL(self, w, h):
        # Cache it here - resizeGL is called after the widget is properly initialized
        sc = self.devicePixelRatio()
        pw = int(w * sc)
        ph = int(h * sc)
        self._opengl_fbo = {'w': pw, 'h': ph, 'fbo': self.defaultFramebufferObject()}        
        

    def paintGL(self):
        if self.ctx and self._opengl_fbo:
            self.ctx.render(flip_y=True, opengl_fbo=self._opengl_fbo)
                  
    def do_update(self):
        self.update()

    @pyqtSlot()
    def _on_update(self):
        if not self.closePending:
            self.triggerUpdate.emit(self._timePos)

    def _onPlayEnd(self, _name, val):
        if val == True:
            self.toggleVideoPlay()

    def _onTimePos(self, _name, val):
        if val is not None:
            self._timePos = val
            if self.isAudioOnly:
                self._on_update()
            
    def startPlaying(self):
        if self.filePath is  not None:
            self.mpv.loadfile(self.filePath)
            self._getReady()
            if not self.lastError:
                self.mpv.pause = False
                self.syncPlayStatus.emit(True)
                self.fileLoaded.emit()
                return
        self.syncPlayStatus.emit(False)
    
    def _getReady(self):
        self.seekLock = Condition()
        self.mpv.observe_property("duration", self._onReadyWait)
        with self.seekLock:
            res = self.seekLock.wait(timeout=15.0)  # networking=15
            # broken = len(self.lastError)>0
            # print("ready: %d, broken:%s"%(res,self.lastError))
            # self.isReadable=res and not broken
            self.isReadable = res     
    
    def _onDuration(self, name, val):
        if val is not None:
            self.duration = val
            Log.info("durance detected:%.3f" % (val))  
            self.durString = '{:02.0f}:{:02.0f}:{:02.0f}'.format(val // 3600, val % 3600 // 60, val % 60)
            self._on_update()
    
    def _onReadyWait(self, name, val):
        if val is not None:
            with self.seekLock:
                    self.mpv.unobserve_property(name, self._onReadyWait)
                    self._onDuration(name, val)
                    self.seekLock.notify()
    
    def isPlaying(self):
        return not self.mpv.pause    

    def isEOF(self):
        return self.mpv.eof_reached

    def toggleVideoPlay(self):
        if self.mpv is None:
            self.syncPlayStatus.emit(False)
            return
        if self.mpv.eof_reached:
            self.mpv.pause = True
            self.syncPlayStatus.emit(False)
            return
        playing = self.mpv.pause  # what a dreher... playing= NOT pause
        self.mpv.pause = not playing
        self.syncPlayStatus.emit(playing)

    def setAudio(self, idx):
        if idx == 0:
            self.mpv["mute"] = "yes"
            self.mpv.audio = "no"
        else:
            self.mpv["mute"] = "no"
            self.mpv.audio = idx

    def _muteWhileSeeking(self, isSeeking):
        if self.mpv.audio == 0:
            return
        if isSeeking:
            self.mpv["mute"] = "yes"
        else:
            self.mpv["mute"] = "no"

    def setSubtitles(self, idx):
        self.mpv.sid = int(idx)

    def getSourceDir(self):
        if self.filePath:
            return OSTools().getDirectory(self.filePath)
        return OSTools().getHomeDirectory()

    def takeScreenShot(self):
        currentPath = OSTools().getPathWithoutExtension(self.filePath);
        path = currentPath + str(self.duration) + '.jpg'
        self.mpv.screenshot_to_file(path, includes="video")       

    def closeEvent(self, event: QCloseEvent) -> None:
        """free mpv_context and terminate player before closing the widget"""
        self.ctx.free()
        self.sliderThread.stop()
        self.mpv.terminate()
        self.mpv = None
        event.accept()

    def _getMPVArgs(self,isVirtual):
        kwArgs = {"hwdec":"auto-safe", "log_handler":self._passLog, "loglevel": 'error', "pause":False, "audio": "1", "keep_open": "always", "vo":"libmpv",
                "input_vo_keyboard": False, "video-latency-hacks": "yes", "hr_seek": 'yes', "hr_seek_demuxer_offset": self._demuxOffset,  # below is test
                "demuxer_max_back_bytes":'150M', "demuxer_max_bytes":'150M', "demuxer_cache_wait":'no', "stream_buffer_size":'255MiB',
                "audio-display":"embedded-first"
                }
        if isVirtual:
            kwArgs['gpu-dumb-mode'] = 'yes'
            kwArgs['vd-lavc-dr'] = 'no'
        return kwArgs

    def _passLog(self, loglevel, component, message):
        msg = '{}: {}'.format(component, message)
        with self.seekLock:
            if message.strip() in self.ERR_IDS:
                Log.error(">%s", msg)
                self.lastError = message
                self.onError.emit(message)
                self.seekLock.notify_all() 


class MainFrame(QtWidgets.QMainWindow):
    SLIDER_RESOLUTION = 1000 * 1000
    
    def __init__(self, qapp, aPath=None, isVirtual=False):
        self._isStarted = False
        self.__qapp = qapp
        super(MainFrame, self).__init__()
        self.player = Player(self, aPath, isVirtual)
        self.settings = SettingsModel(self)
        self.audioMapping = None
        self.setWindowIcon(getAppIcon())
        self._fullscreen = False
        self.initUI()
        self.centerWindow()
        self.show()
        QtCore.QTimer.singleShot(0, self.__queueStarted)
    
    def initUI(self):
        # ##the actions
        
        self.loadAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("loadAction")), 'Load media file (CRTL+L)', self)
        self.loadAction.setShortcut('Ctrl+L')
        self.loadAction.triggered.connect(self.loadFile)
        
        # self.exitAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("buttonStop")), 'Exit', self)
        # self.exitAction.setShortcut('Ctrl+Q')
        # self.exitAction.triggered.connect(QApplication.quit)        
        
        self.playAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("playStart")), 'Play media (toggle with space)', self)
        self.shortcutPlay = QtGui.QShortcut(QtGui.QKeySequence("Space"), self)
        self.shortcutPlay.setContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        self.shortcutPlay.activated.connect(self.playVideo)
        self.playAction.triggered.connect(self.playVideo)
        
        self.infoAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("infoAction")), 'Codec info (Crtl+I)', self)
        self.infoAction.setShortcut('Ctrl+I')
        self.infoAction.triggered.connect(self.showCodecInfo)

        self.photoAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("photoAction")), 'Take screenshot (Crtl+P)', self)
        self.photoAction.setShortcut('Ctrl+P')
        self.photoAction.triggered.connect(self.takeScreenShot)

        self.fsAction = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("fullscreen")), 'Fullscreen (F11 and ESC)', self)
        self.fsAction.setShortcut('F11')
        self.fsAction.triggered.connect(self._setFullscreen)

        self.mediaSettings = QtGui.QAction(QtGui.QIcon(ICOMAP.ico("mediaSettings")), 'Settings', self)
        self.mediaSettings.setShortcut('Ctrl+T')
        self.mediaSettings.triggered.connect(self._openMediaSettings)

        self.languagebox = QtWidgets.QComboBox()
        self.languagebox.currentTextChanged.connect(self._onLanguageChanged)
        self.languagebox.setToolTip("Select audio")

        '''
        self.checkSubtitle = QtWidgets.QCheckBox("Subtitles")
        self.checkSubtitle.setChecked(False)
        self.checkSubtitle.setToolTip("Subtitles")
        self.checkSubtitle.stateChanged.connect(self._onSubtitleChanged)
        '''
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        
        self.toolbar = self.addToolBar('Main')
        self.toolbar.addAction(self.loadAction)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.playAction)
        self.toolbar.addAction(self.infoAction)
        self.toolbar.addAction(self.photoAction)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.mediaSettings)
        self.toolbar.addWidget(self.languagebox)
        '''
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.checkSubtitle)
        '''
        self.toolbar.addWidget(spacer)
        self.toolbar.addAction(self.fsAction)
        
        color = self.toolbar.palette().color(QtGui.QPalette.ColorRole.Window)
        bc = color.darker(120)
        darker = color.darker(150)
        lighter = color.lighter(140)
        self.toolbar.setStyleSheet("QToolBar { background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,stop: 0 %s, stop: 1.0 %s); border: 1px solid %s;}" % (darker.name(), lighter.name(), bc.name()))                      

        self.ui_InfoLabel = QtWidgets.QLabel(self)
        self.ui_InfoLabel.setStyleSheet("QLabel { background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,stop: 0 %s, stop: 1.0 %s); border: 1px solid %s;}" % (darker.name(), lighter.name(), bc.name()))
        self.ui_InfoLabel.setText("0")
        fontM = QtGui.QFontMetrics(self.ui_InfoLabel.font())
        self.ui_InfoLabel.setFixedHeight(fontM.height() + round(fontM.height() * 0.5))
        self.ui_InfoLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight)
        self.ui_InfoLabel.setToolTip("Infos about the media position")
        
        self._createSlider()
       
        box = self._makeLayout()
        wid = QtWidgets.QWidget(self)
        self.setCentralWidget(wid)    
        wid.setLayout(box)
        self.resize(1024, 640) 
        # --- shortcut for fullscreen toggle ---
        # F11 Shortcut is defined in the fullscreen action
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Escape), self, activated=self._setNormalScreen)
        self.player.triggerInitialized.connect(self._initIcon)
        self.player.onError.connect(self._onPlayerError)

    def takeScreenShot(self):
        self.player.takeScreenShot()

    def _openMediaSettings(self):
        dlg = SettingsDialog(self, self.settings)
        dlg.show()

    def _setFullscreen(self):
        if not self._fullscreen:
            # hide all UI except player
            self.toolbar.hide()
            self.ui_InfoLabel.hide()
            self.ui_Slider.hide()
            self._fullscreen = True
            self.showFullScreen()
            self.player.setCursor(QtCore.Qt.CursorShape.BlankCursor)
            pos = QtGui.QCursor.pos()
            QtCore.QTimer.singleShot(50, lambda: (QtGui.QCursor.setPos(self.player.mapToGlobal(QtCore.QPoint(pos.x() + 1, pos.y())))))   
            self.player.grabKeyboard()
        
    def _setNormalScreen(self):
        if self._fullscreen:
            # restore UI
            self.toolbar.show()
            self.ui_InfoLabel.show()
            self.ui_Slider.show()
            self._fullscreen = False
            self.showNormal()
            self.player.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            self.player.releaseKeyboard()

    def _onLanguageChanged(self, text):
        if len(text) == 0:
            return  # when cleared again...
        idx = self.audioMapping.get(text, (0, 0))
        self.player.setAudio(idx[0])
        if self.settings.hasSubtitles():
            self._onSubtitleChanged(True)
        
    def _prepareNextStream(self, streamData):
        isVideo = not self.player.isAudioOnly
        self.languagebox.setEnabled(isVideo)
        self.photoAction.setEnabled(isVideo)
        if isVideo:
            self._updateLang(streamData)

    def _updateLang(self, streamData):
        self.languagebox.clear()
        if not streamData:
            self.audioMapping = {}
            self.audioMapping["Mute"] = (0, 0)
            self.languagebox.addItem("Mute")
        else:
            self.audioMapping = streamData.getLanguageMapping()
            audioCount = len(streamData.allAudioStreams())
            self.audioMapping["Mute"] = (0, 0)
            akeys = [k for k in self.audioMapping.keys() if self.audioMapping[k][0] >= 0 ]
            if len(akeys) == 1 and audioCount > 0:
                self.audioMapping["Audio"] = (1, 0)
                akeys = ["Audio", "Mute"]
            
            self.languagebox.addItems(akeys)

    # #settings callback 1
    def _onSubtitleChanged(self, isSelected):
        if self.audioMapping:
            idx = (0, 0)
            if isSelected:
                txt = self.languagebox.currentText()
                idx = self.audioMapping.get(txt, (0, 0))
            self.player.setSubtitles(max(0, idx[1]))  # negative means - no subtitle here

    # #settings callback 2
    def _onEQChanged(self, isSelected):
        print("Should be EQ:", isSelected)

    def _createSlider(self):
        self.ui_Slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        # contribution:
        self.ui_Slider.setStyleSheet(stylesheet())
        
        self.ui_Slider.setMinimum(0)
        self.ui_Slider.setMaximum(self.SLIDER_RESOLUTION)
        self.ui_Slider.setToolTip("Time track")
        self.ui_Slider.setTickInterval(0)
        self.ui_Slider.valueChanged.connect(self._onSliderMoved)
        
        self.shortcutSeekRight = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Right), self)
        self.shortcutSeekRight.activated.connect(lambda: self.player.seekRelative(10))
        self.shortcutSeekLeft = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Left), self)
        self.shortcutSeekLeft.activated.connect(lambda: self.player.seekRelative(-10))
        
        self.shortcutPageUp = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_PageUp), self)
        self.shortcutPageUp.activated.connect(lambda: self.player.seekRelative(60))
        
        self.shortcutPageDown = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_PageDown), self)
        self.shortcutPageDown.activated.connect(lambda: self.player.seekRelative(-60))        

    def _initIcon(self):
        self.player.mpv.loadfile("icons/easyPlay.png")

    def _makeLayout(self):
        mainBox = QtWidgets.QVBoxLayout()  # for all
        '''
        btn1Box = QtWidgets.QHBoxLayout()  # test widgets
        btn1Box.setSpacing(20)
        btn1Box.addWidget(self.uiLabel)
        btn1Box.addWidget(self.uiPlayButton)
        btn1Box.addWidget(self.uiStopButton)
        '''
        mainBox.addWidget(self.player)
        mainBox.addWidget(self.ui_InfoLabel)
        mainBox.addWidget(self.ui_Slider)
        return mainBox
     
    def centerWindow(self):
        frameGm = self.frameGeometry()
        centerPoint = self.screen().availableGeometry().center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())    
    
    def loadFile(self):
        initalPath = self.player.getSourceDir()
        result = QtWidgets.QFileDialog.getOpenFileName(parent=self, directory=initalPath, caption="Load Media");
        if result[0]:
            fn = self.__encodeQString(result)
            QtCore.QTimer.singleShot(10, lambda: self._switchStream(fn))
            
    
    def _switchStream(self, fn):
        if not fn:
            return
        try:
            self.player.setStreamData(fn)
            self.updateWindowTitle(fn)
            self.asyncPlay()
        except:
            self._initIcon()
            self.getErrorDialog("Invalid file", "%s is not a known media file" % (fn), "-").show()
    
    def __encodeQString(self, stringTuple):
        text = stringTuple[0]
        return text
    
    def playVideo(self):
        if self.player.isEOF():
            self.asyncPlay()
        else:
            QtCore.QTimer.singleShot(0, self.player.toggleVideoPlay)

    def _onSyncPlayerControls(self, isPlaying):
        if isPlaying:
            self.__enableActionsOnVideoPlay(False)
            self.playAction.setIcon(QtGui.QIcon(ICOMAP.ico("playPause")))
        else:
            self.__enableActionsOnVideoPlay(True)
            self.playAction.setIcon(QtGui.QIcon(ICOMAP.ico("playStart")))             

    # manual slider - sync with gui    
    def _onSliderMoved(self, pos):
        if self.player.streamData:
            dur = self.player.duration
        else:
            dur = 0
        if dur == 0:
            relpos = 0
        else:
            relpos = pos / self.SLIDER_RESOLUTION * dur 
        self.player.asyncSeek(relpos)
    
    # running stream - syn with slider
    @pyqtSlot(float)
    def _onSyncSlider(self, timepos):
        if timepos == self.ui_Slider.value():
            return
        if not self.ui_Slider.isSliderDown():
            self.ui_Slider.blockSignals(True)
            dur = self.player.duration
            if dur == 0:
                sliderPos=0
            else:
                sliderPos = self.SLIDER_RESOLUTION * timepos / dur 
            self.ui_Slider.setSliderPosition(int(sliderPos))
            self.ui_Slider.blockSignals(False)    
        s = int(timepos)
        ts = '{:02}:{:02}:{:02}'.format(s // 3600, s % 3600 // 60, s % 60)
        self.ui_InfoLabel.setText(ts + "  \u25C6  " + self.player.durString)
    
    @pyqtSlot(str)
    def _onPlayerError(self, errorMsg):
        self.getErrorDialog("Invalid file", "Not a valid codec found", "on_player error").show()
    
    def __enableActionsOnVideoPlay(self, enable):
        self.loadAction.setEnabled(enable)
        
    def __queueStarted(self):  # mpv thread
        self.player.syncPlayStatus.connect(self._onSyncPlayerControls) 
        self.player.fileLoaded.connect(lambda: self._prepareNextStream(self.player.streamData))
        self.player.triggerUpdate.connect(self._onSyncSlider)
        self.settings.changeEQ.connect(self._onEQChanged)
        self.settings.changeSub.connect(self._onSubtitleChanged)
        #self._switchStream(self.player.filePath)
        QtCore.QTimer.singleShot(10, lambda: self._switchStream(self.player.filePath))
    
    def asyncPlay(self):
        self.w = Worker(self.player.startPlaying)
        self.w.finished.connect(self.w.deleteLater)  # safer cleanup
        self.w.start()
    
    def showCodecInfo(self):
        na = "N.A."
        try:
            # fn = self.player.filePath
            # if not fn:
            #    self.__getInfoDialog("No data").show()
            #    return
             
            streamData = self.player.streamData
            container = streamData.formatInfo;
            videoData = streamData.getVideoStream()
            audioData = streamData.getAudioStream()
            if audioData is None:
                acodec = "N.A."
            else:
                acodec = audioData.getCodec();
            
            if not videoData:
                codec = na
                w = "0"
                h = "0"
                ar = "no Video"
                fr = 0.0
            else:
                codec = videoData.getCodec()
                w = videoData.getWidth()
                h = videoData.getHeight()
                ar = videoData.getAspectRatio()
                fr = videoData.frameRateAvg()                
                
            entries = []
            s = int(self.player.duration)
            ts = '{:02}:{:02}:{:02}'.format(s // 3600, s % 3600 // 60, s % 60)

            textDS = """<table style="border-collapse: collapse;">
            <tr>
                <td style="border: 1px solid darkgray; padding: 8px 15px;"><b>Container:</b></td>
                <td style="border: 1px solid darkgray; padding: 8px 15px;">%s</td>
            </tr>
            <tr>
                <td style="border: 1px solid darkgray; padding: 8px 15px;"><b>Bitrate:</b></td>
                <td style="border: 1px solid darkgray; padding: 8px 15px;">%s [kb/s]</td>
            </tr>
            <tr>
                <td style="border: 1px solid darkgray; padding: 8px 15px;"><b>Size:</b></td>
                <td style="border: 1px solid darkgray; padding: 8px 15px;">%.3f [mib]</td>
            </tr>
            <tr>
                <td style="border: 1px solid darkgray; padding: 8px 15px;"><b>is TS:</b></td>
                <td style="border: 1px solid darkgray; padding: 8px 15px;">%s</td>
            </tr>
            <tr>
                <td style="border: 1px solid darkgray; padding: 8px 15px;"><b>Video Codec:</b></td>
                <td style="border: 1px solid darkgray; padding: 8px 15px;">%s</td>
            </tr>
            <tr>
                <td style="border: 1px solid darkgray; padding: 8px 15px;"><b>Dimension:</b></td>
                <td style="border: 1px solid darkgray; padding: 8px 15px;">%sx%s</td>
            </tr>
            <tr>
                <td style="border: 1px solid darkgray; padding: 8px 15px;"><b>Aspect:</b></td>
                <td style="border: 1px solid darkgray; padding: 8px 15px;">%s</td>
            </tr>
            <tr>
                <td style="border: 1px solid darkgray; padding: 8px 15px;"><b>FPS:</b></td>
                <td style="border: 1px solid darkgray; padding: 8px 15px;">%.2f</td>
            </tr>
            <tr>
                <td style="border: 1px solid darkgray; padding: 8px 15px;"><b>Duration:</b></td>
                <td style="border: 1px solid darkgray; padding: 8px 15px;">%s</td>
            </tr>
            <tr>
                <td style="border: 1px solid darkgray; padding: 8px 15px;"><b>Audio codec:</b></td>
                <td style="border: 1px solid darkgray; padding: 8px 15px;">%s</td>
            </tr>
            </table>""" % (container.formatNames()[0], container.getBitRate(), container.getSizeKB() / 1024, streamData.isTransportStream(), codec, w, h, ar, fr, ts, acodec)

            '''
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
            '''
            text2 = ''.join(entries)
                                        
        except:
            Log.exception("Invalid codec format")
            text = "<br><b>No Information</b><br>"  
            text2 = "<br> Please select a file first"
        self.__getInfoDialog(textDS + text2).show()

    def __getInfoDialog(self, text):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        dlg.setWindowTitle("Media Infos")
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

    def updateWindowTitle(self, fnName):
        tx = FFMPEGTools.OSTools().getFileNameOnly(fnName)
        self.setWindowTitle(AppName + " - " + tx)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.player.closePending = True


class Worker(QThread):
    done = pyqtSignal()

    def __init__(self, func, *args, **kwargs):
        QThread.__init__(self)
        self.function = func
        self.arguments = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.function(*self.arguments, **self.kwargs)
            # self.function()
        except Exception as ex:
            Log.exception("***Error in Worker*** %s", ex)
        finally:
            self.done.emit()


class SettingsModel(QtCore.QObject):
    changeSub = pyqtSignal(object)
    changeEQ = pyqtSignal(object)
    
    def __init__(self, mainframe):
        # keep flags- save them later
        super(SettingsModel, self).__init__()
        self.iconSet = ep_config.get("icoSet", IconMapper.DEFAULT)
        self.showEQ = ep_config.getBoolean("showEQ", False)
        self.mainFrame = mainframe
        self.showSubs = ep_config.getBoolean("subtitles", False)  # id if subtitle should be presented. mpv only
        self.isoCodes = []
    
    def sync(self):
        if self.showEQ:
            ep_config.set("showEQ", "True")
        else:
            ep_config.set("showEQ", "False")
        
        if self.showSubs:
            ep_config.set("subtitles", "True")
        else:
            ep_config.set("subtitles", "False")
        
        # SET the icoset
        ep_config.set("icoSet", self.iconSet)
        
    def __update(self):
        self.sync()        
        ep_config.store()
        
    def hasSubtitles(self):
        return self.showSubs
    
    def hasEQ(self):
        return self.showEQ

    def setEQ(self, aBool):
        self.showEQ = aBool
        self.__update()
        self.changeEQ.emit(aBool)
        
    def setSubtitle(self, aBool):
        self.showSubs = aBool
        self.__update()
        self.changeSub.emit(aBool)   
        
    def setIconSet(self, icoType):
        self.iconSet = icoType
        self.__update() 


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
       
        self.showEQ = QtWidgets.QCheckBox("Show EQ - Audio only")
        self.showEQ.setToolTip("Display an EQ on music")
        self.showEQ.setChecked(self.model.hasEQ())
        self.showEQ.stateChanged.connect(self._onEQChanged)  

        self.showSub = QtWidgets.QCheckBox("Show subtitles")
        self.showSub.setToolTip("Toggle show subtitles")
        self.showSub.setChecked(self.model.hasSubtitles())
        self.showSub.stateChanged.connect(self._onSubChanged)
        
        frame2Header = QtWidgets.QLabel("Icon theme. Restart application after change")

        # lbl = QtWidgets.QLabel("< Icon theme")
        self.setIconTheme = QtWidgets.QComboBox()
        themes = ICOMAP.themes()
        for item in themes:
            self.setIconTheme.addItem(item)
        self.setIconTheme.setCurrentText(self.model.iconSet)
        self.setIconTheme.currentTextChanged.connect(self._onIconThemeChanged)
        self.setIconTheme.setToolTip("Select icon theme - restart to take effect")

        clickBox = QtWidgets.QVBoxLayout(frame1)
        # clickBox.addWidget(self.showEQ)
        clickBox.addWidget(self.showSub)

        subBox = QtWidgets.QVBoxLayout(frame2)
        subBox.addWidget(frame2Header)
        subBox.addWidget(self.setIconTheme)
        
        outBox.addLayout(versionBox)
        outBox.addWidget(frame1)
        outBox.addWidget(frame2)
        self.setLayout(outBox)
        # make it wider...
        self.setMinimumSize(550, 0)
   
    def _onSubChanged(self, showsub):
        self.model.setSubtitle(showsub)

    def _onGLChanged(self, useGL):
        self.model.setGL(QtCore.Qt.CheckState.Checked.value == useGL)
        
    def _onEQChanged(self, aBool):
        self.model.setEQ(QtCore.Qt.CheckState.Checked.value == aBool)
        
    def _onIconThemeChanged(self, text):
        self.model.setIconSet(text)


class IconMapper():
    DEFAULT = "default"

    def __init__(self, section="default"):
        self.section = section
        self._read()
        
    def _read(self):
        ipath = OSTools().joinPathes(OSTools().getWorkingDirectory(), "icons", "icomap.json")
        with open(ipath) as fn:
            self.map = json.load(fn)
            
    def ico(self, name):
        key = name.strip()
        submap = self.map.get(self.section, None)
        if not submap:
            submap = self.map[self.DEFAULT]
        return submap.get(key, self.getDefault(key))
     
    def getDefault(self, name):
        return self.map[self.DEFAULT].get(name, "")   
    
    def themes(self):
        return self.map.keys()


def handle_exception(exc_type, exc_value, exc_traceback):
    """ handle all exceptions """
    infoText = str(exc_value)
    detailText = "*".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    Log.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    if WIN is not None:
        WIN.getErrorDialog("Unexpected error", infoText, detailText).show()


def parseOptions(args):
    res = {}
    res["logConsole"] = False
    res["file"] = None
    res["virtual"]=False
    try:
        opts, args = getopt.getopt(args[1:], "cdv", ["console", "debug", "virtual"])
        if len(args) == 1:
            res["file"] = args[0]
        else:
            res["file"] = None
    except getopt.GetoptError as err:
        print(err)
        sys.exit(2)
    
    for o, a in opts:
        if o in ("-d", "--debug"):
            FFMPEGTools.setLogLevel("Debug")
        elif o in ("-c", "--console"):
            res["logConsole"] = True
        elif o in ("-v","--virtual"):
            res["virtual"]=True            
        else:
            print("Undef:", o) 
    return res


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


def getAppIcon():
    return QtGui.QIcon('icons/easyPlay.svg')


def main():
    try:
        global ICOMAP 
        global WIN 
        global ep_config
        wd = OSTools().getLocalPath(__file__)
        localPath = OSTools().getActiveDirectory()
        OSTools().setMainWorkDir(wd)
        ep_config = ConfigAccessor(AppName, "ep.ini")  # folder,name&section
        ep_config.read();    
        ICOMAP = IconMapper(ep_config.get("icoSet", "default"))  
        argv = sys.argv
        res = parseOptions(argv)    
        FFMPEGTools.setupRotatingLogger(AppName, res["logConsole"])
        de = OSTools().currentDesktop()
        if de not in OSTools.QT_DESKTOPS:        
            OSTools().setGTKEnvironment()
            Log.info("GTK based - switched to QT_QPA_PLATFORM = xcb" )
        app = QApplication(argv)
        # Set the application name (this sets WM_CLASS)
        app.setApplicationName(AppName)
        # Link to your desktop file (important for GNOME)
        app.setDesktopFileName(AppName)       
        
        locale.setlocale(locale.LC_NUMERIC, "C")
        fn = res["file"]
        if fn is None:
            WIN = MainFrame(app)  # keep python reference!
        else:
            if not OSTools().isAbsolute(fn):
                fn = OSTools().joinPathes(localPath, fn)
            WIN = MainFrame(app, fn, res['virtual']) 
        app.exec()
    except:
        Log.exception("Error in main:")
        # ex_type, ex_value, ex_traceback
        sys_tuple = sys.exc_info()
        QtWidgets.QMessageBox.critical(None, "Error!", str(sys_tuple[1]))        


if __name__ == '__main__':
    sys.excepthook = handle_exception
    sys.exit(main())

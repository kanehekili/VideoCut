'''
Created on 3 May 2024

@author: matze
'''
from PyQt6 import QtWidgets

"""
based on:
https://github.com/mpv-player/mpv-examples/blob/master/libmpv/qt_opengl/mpvwidget.cpp
https://gitlab.com/robozman/python-mpv-qml-example/-/blob/master/main.py?ref_type=heads
"""

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QOpenGLContext, QPainter, QBrush, QColor, QCloseEvent
from PyQt6.QtCore import QByteArray, pyqtSignal, pyqtSlot, Qt
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from lib.mpv import MPV, MpvGlGetProcAddressFn, MpvRenderContext
import sys

def get_process_address(_, name):
    glctx =  QOpenGLContext.currentContext()
    address = int(glctx.getProcAddress(QByteArray(name)))
    #return ctypes.cast(address, ctypes.c_void_p).value
    return address

def getMPV():
        kwArgs={"log_handler":print,"log-file":"gl.txt","loglevel" : 'info',"pause":False,"audio" : "1","keep_open" : "always","vo":"libmpv"}
        return MPV(**kwArgs)

class Player(QOpenGLWidget):
    onUpdate = pyqtSignal()
    initialized = pyqtSignal()
    
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.mpv = getMPV()
        self.ctx = None
        self._proc_addr_wrapper = MpvGlGetProcAddressFn(get_process_address)
        self.onUpdate.connect(self.do_update)
        self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.PartialUpdate)
        
    def initializeGL(self) -> None:
        self.ctx = MpvRenderContext(
            self.mpv, 'opengl',
            opengl_init_params={
                'get_proc_address': self._proc_addr_wrapper
            },    
        )

        if self.ctx:
            self.ctx.update_cb = self.on_update
            self.initialized.emit()

    def paintGL(self) -> None:
        rect = self.rect()
        if self.ctx:
            fbo = self.defaultFramebufferObject()
            self.ctx.render(flip_y=True, opengl_fbo={'w': rect.width(), 'h': rect.height(), 'fbo': fbo})
                  
    def do_update(self):
        self.update()

    @pyqtSlot()
    def on_update(self):
        self.onUpdate.emit()

    def play(self, url):
        self.mpv.play(url)

    def closeEvent(self, event: QCloseEvent) -> None:
        """free mpv_context and terminate player brofre closing the widget"""
        self.ctx.free()
        self.mpv.terminate()
        event.accept()


class MainFrame(QtWidgets.QMainWindow):
    
    def __init__(self, qapp,aPath=None):
        self._isStarted=False
        self.__qapp=qapp
        super(MainFrame, self).__init__()
        self.initUI()
        self.centerWindow()
        self.show()
        #qapp.applicationStateChanged.connect(self.__queueStarted)
     
    
    def initUI(self):
        self.player = Player(self)
        #self.player = VideoGLWidget(self,getMPV())
        
        self.uiLabel= QtWidgets.QLabel(self)
        self.uiLabel.setText("Player demo")
        self.uiPlayButton = QtWidgets.QPushButton(" Play")
        self.uiPlayButton.clicked.connect(self.execPlayButton)
        self.uiStopButton = QtWidgets.QPushButton(" Stop")
        self.uiStopButton.clicked.connect(self.execStopButton)
        
        
        box = self._makeLayout()
        wid = QtWidgets.QWidget(self)
        self.setCentralWidget(wid)    
        wid.setLayout(box)
        self.resize(500, 600) 
        #self.player.initialized.connect(lambda: [self.player.play("/media/disk1/UHD/gog.mp4")])
        #self.player.initialized.connect(lambda: [self.player.mpv.loadfile("icons/film-clapper.png")])
        self.player.initialized.connect(self._initIcon)

    def _initIcon(self):
        self.player.mpv.loadfile("icons/film-clapper.png")

    def _makeLayout(self):
        mainBox = QtWidgets.QVBoxLayout()  # for all
        btn1Box = QtWidgets.QHBoxLayout()  # test widgets
        btn1Box.setSpacing(20)
        btn1Box.addWidget(self.uiLabel)
        btn1Box.addWidget(self.uiPlayButton)
        btn1Box.addWidget(self.uiStopButton)

        mainBox.addWidget(self.player)
        mainBox.addLayout(btn1Box)
        return mainBox
     
    def centerWindow(self):
        frameGm = self.frameGeometry()
        #screen = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
        #centerPoint = QApplication.desktop().screenGeometry(screen).center()
        centerPoint = self.screen().availableGeometry().center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())    
    
    def execPlayButton(self):
        #self.player.play("/media/disk1/UHD/gog.mp4")
        self.player.play("/media/disk1/makemkv/title_t00.mkv")
    
    def execStopButton(self):
        playing = self.player.mpv.pause #property
        self.player.mpv.pause=not playing
        
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    import locale
    locale.setlocale(locale.LC_NUMERIC, "C")
    #player = Player()
    #player.initialized.connect(lambda: [player.play("/media/disk1/UHD/gog.mp4")])
    #player.show()
    WIN = MainFrame(app) 
    app.exec()
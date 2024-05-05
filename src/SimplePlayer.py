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
import ctypes,sys


def get_process_address(_, name):
    glctx =  QOpenGLContext.currentContext()
    address = int(glctx.getProcAddress(QByteArray(name)))
    #return ctypes.cast(address, ctypes.c_void_p).value
    return address

class Player(QOpenGLWidget):
    onUpdate = pyqtSignal()
    initialized = pyqtSignal()
    
    def __init__(self, parent) -> None:
        super().__init__(parent)
        kwArgs={"log_handler":print,"log-file":"gl.txt","loglevel" : 'trace',"audio" : "1","keep_open" : "always"}
        self.mpv = MPV(**kwArgs)
        self.ctx = None
        self._proc_addr_wrapper = MpvGlGetProcAddressFn(get_process_address)
        self.onUpdate.connect(self.do_update)
        self.c = 0

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
        if self.c > 100:
            self.c = 0
        else:
            self.c += 1
        rect = self.rect()
        if self.ctx:
            fbo = self.defaultFramebufferObject()
            self.ctx.render(flip_y=True, opengl_fbo={'w': rect.width(), 'h': rect.height(), 'fbo': fbo})

                    
        # Draw on bottom center
        '''
        p = QPainter(self)
        width = rect.size().width()
        height = rect.size().height()
        label_rect = rect.adjusted((width/2)-75, height-100, -(width/2)+75, -50)
        p.setPen(QColor("#ffffff"))
        
        text = '.'*int((self.c/20)) + "playing" + '.'*int((self.c/20))
        p.fillRect(label_rect, QBrush(QColor("#ff00ff"), Qt.BrushStyle.FDiagPattern))
        p.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, text)
        '''

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
        
        self.uiLabel= QtWidgets.QLabel(self)
        self.uiLabel.setText("Player demo")
        self.uiPlayButton = QtWidgets.QPushButton(" Play")
        
        box = self._makeLayout()
        wid = QtWidgets.QWidget(self)
        self.setCentralWidget(wid)    
        wid.setLayout(box)
        self.resize(500, 600) 
        #self.player.initialized.connect(lambda: [self.player.play("/media/disk1/UHD/gog.mp4")])
        self.player.initialized.connect(lambda: [self.player.mpv.loadfile("icons/film-clapper.png")])

    def _makeLayout(self):
        mainBox = QtWidgets.QVBoxLayout()  # for all
        btn1Box = QtWidgets.QHBoxLayout()  # test widgets
        btn1Box.setSpacing(20)
        btn1Box.addWidget(self.uiLabel)
        btn1Box.addWidget(self.uiPlayButton)

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
        
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    import locale
    locale.setlocale(locale.LC_NUMERIC, "C")
    #player = Player()
    #player.initialized.connect(lambda: [player.play("/media/disk1/UHD/gog.mp4")])
    #player.show()
    WIN = MainFrame(app) 
    app.exec()
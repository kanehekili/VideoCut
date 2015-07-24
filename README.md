# VideoCut
Version 0.0.1

MP4 Cutter for Linux on base of OpenCV and ffmpeg. Cutting is lossless, the target file will not be reencoded 

It can be used for cutting out certain parts of the film. 
 
###Prerequisites
* python2.7
* OpenCV 2.4
* ffmpeg 1.2.7
* python2-pyqt4

###Features
Cuts an mpg file into parts and joins them afterwards. All commands can be reached via the toolbar.

The cutout parts will be joined without beeing recoded - the quality stays the same
###Limitations
Audio sync seems to be ok, but needs observation on different players (no problem with vlc)
No codec Info shown
Playing the film not implemented yet (without sound)

Have fun

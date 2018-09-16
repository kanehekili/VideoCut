# VideoCut
Version 0.9.4

MP4 Cutter for Linux on base of OpenCV and ffmpeg. Cutting is lossless, the target file will not be reencoded 

It can be used for cutting out certain parts of the film. Has been written in conjunction with the MDVB Recorder for removing ads. Handles avi, mp2,mp4 (PS or TS). Other formats not tested but possible.

The new version is written in python3 and uses the qt5 widget kit.  
## Prerequisites
* python3
* OpenCV 2.4 or OPENCV 3 (must be build with ffmpeg)
* ffmpeg > 3.X
* python3-pyqt5

### Features
Cuts an mpg file into parts and joins them afterwards. All commands can be reached via the toolbar.

![Screenshot](https://github.com/kanehekili/VideoCut/blob/master/Videocut.png)

The cutout parts will be joined without beeing recoded - the quality stays the same
### Limitations
Using ffmpeg as cutting/joining tool. Some older versions of ffmpeg seem to have problems with syncing audio on avchd (mp4 TS) streams. 
Current git version of ffmpeg will yield the best results.
Latest opencv version in arch linux is compiled with gstreamer - it is necessary to get a version that has been compiled with ffmpeg

:boom: Be aware that this tool does not cut exact on frame - except you reencode the whole film.

### How to install
* Download the videocut*.tar contained in the "build" folder ![here](https://github.com/kanehekili/VideoCut/raw/master/VideoCutter/build/videocut0.9.2.tar)
* Upack it to a location that suits you.
* Copy the VideoCut.desktop file to ~/.local/share/applications
* Change the absolute paths & user name to the location where you've copied the files.

### Currently working on:
* Exact frame cut - by generating intermediate I-Frames until the cut point. 
* Conversion tools - from one container to another, change audio or video codecs...
* I'm experimenting with pyav, but it does not seem to be very stable..
* Replacement of opencv with pyav

### Changes 
08.07.2016
Added "Exact cut" feature. Ensures that the cut of the mp4 is exact (Frame exact). Takes longer, since the video has to be reencoded. 

30.11.2016 V 0.9.0
* Added filters for h264 and mpegts. 
* Fixed some minor UI issues
* Honored the "new" feature, that absolute paths in concat are not accepted
* Added support for OpenCV 3
* Cutting MOV,MP4,MPEG-TS, FLV and some more 

05.2017
* Added logging, some minor bugfixes/optimizations

09.2018
The final QT4 version has been committed. 

16.09.2018
Redesign of the frontend: Using python 3 and qt5.
Introduction of a native C ffmpeg layer, which can convert the videos much faster than the default interface. (Beta!)

In case of problems open an issue. 
Have fun. 

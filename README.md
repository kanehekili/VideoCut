# VideoCut
Version 1.3.2

![Download](https://github.com/kanehekili/VideoCut/raw/master/build/videocut1.3.2.tar)

MP2/MP4 Cutter for Linux on base of OpenCV and ffmpeg. Cutting is lossless, the target file will not be reencoded. 

It can be used for cutting out certain parts of the film. Has been written in conjunction with the MDVB Recorder for removing ads. Handles avi, mp2,mp4 (PS or TS). Other formats not tested but possible.

Lossless cutting implies not to reencode (decode/encode) the frames. So cutting can only be done at "I-Frames". The library searches for the closest Frame at the given cutting point.

The new version is written in python3 and uses the qt5 widget kit.  
### Prerequisites
* python3
* OpenCV 2.4 or OPENCV 3 (must be build with ffmpeg)
* ffmpeg > 3.X or 4.0.X
* python3-pyqt5
* hdf5 (Arch only)

#### Install dependencies on Linux Mint or Ubuntu (tested from 16.04 to 20.04)
```
sudo apt-get install python3-pyqt5 ffmpeg python3-opencv
```
#### Install dependencies on Arch or Manjaro
```
sudo pacman -Syu python-pyqt5 ffmpeg python-opencv
```

#### Set GTK Theme for this QT application
If you are running a DE with GTK/Gnome (as opposed to LXQT or KDE) you need to tweak your system:

`sudo nano /etc/environment`

add the follwing line:

`QT_QPA_PLATFORMTHEME=gtk2`

and logout/login (or reboot)

### Features
Cuts an mpg file into parts and joins them afterwards. All commands can be reached via the toolbar.

![Screenshot](https://github.com/kanehekili/VideoCut/blob/master/Videocut.png)

The cutout parts will be joined without beeing recoded - the quality stays the same
### Limitations
Using ffmpeg as cutting/joining tool. Some older versions of ffmpeg seem to have problems with syncing audio on avchd (mp4 TS) streams.

Only ffmpeg and libavformat versions >=3.1 are supported. 

OpenCV:  it is necessary to get a version that has been compiled with ffmpeg

:boom: Be aware that this tool does not cut exact on frame - except you reencode the whole film.

### Subtitles
Finalized in Version 1.3.0.  Not all containers (e.g. mp4) accept subtitles. A AVCH (h264 TS) Stream with DVB_SUB codec cannot be converted into mp4, so your miles may vary if you change the output container (defined by the file extension)

For DVB transport stream you should keep the ".m2t" ending, mkv containers shouldn't be changed either. See [here](https://en.wikipedia.org/wiki/Comparison_of_video_container_formats) for a overview of containers.

### Install VideoCut via AUR (Arch Linux only)
* Use pamac or other GUI tools, search for "videocut", click install
* Manually :
    * Download [PKGBUILD ](https://aur.archlinux.org/cgit/aur.git/snapshot/videocut.tar.gz)
    * unpack it and go into the "videocut" folder
    * execute `makepkg -s`
    * excute `sudo pacman -U videocut-1.x.x.x-1-x86_64.pkg.tar.zst` 
    * uninstall via `sudo pacman -Rs videocut`

### How to install with a terminal
* Install dependencies (see prerequisites)
* Download the videocut*.tar from the download link (see above)
* Extract it to a location that suits you.
* Open a terminal to execute the install.sh file inside the folder with sudo like `sudo ./install.sh`
* (if you are in the download directory - just an example)
* The app will be installed in /opt/videocut with a link to /usr/bin. 
* The app should be appear in a menu or "Actvities"
* Can be openend by selecting a video file & Open with...
* In the terminal can be started via `VideoCut`
* python qt5, opencv and ffmpeg are required
* you may now remove that download directory.
* logs can be found in the user homes ".config/VideoCut" folder

### How to remove
* Open a terminal
* execute `sudo /opt/videocut/uninstall.sh`

### Still on my list:
* Exact frame cut - see comment below 
* Kicking out opencv using SDL and the libavcodec libraries.
* Make debs packages for debian/ubuntu
* Multi language support

### Using remux instead of ffmpeg
remux5 is a c binary based on ffmpeg, but uses an integrated approach to cut and join videos. It seems to be more precise than the ffmpeg API. It is activated by default. To activate FFMPEG, use the "coggs" icon (or click on the green labels) and deselect "VideoCut Muxer".

Please note that excat cut (i.e. transcoding) is available for remux5. Its an optimized library based on libav.
In most cases this lib is faster than native ffmpeg, the cuts are exact when using the "Exact cut" option. Runs on all threads available. 

### Exact frame cut for one GOP only?
Can't be really implemented with the ffmpeg ABI. The transcoded part will have different coding parameters than the rest of the stream. A decoder cannot handle that change. On the other hand there is no way to transcode the GOP with the exact parameters of the original stream, since only a subset of h264 paramenters are accepted by the ffmpeg ABI. 

### Changes 
08.07.2016
* Added "Exact cut" feature. Ensures that the cut of the mp4 is exact (Frame exact). Takes longer, since the video has to be reencoded. 

30.11.2016 V 0.9.0
* Added filters for h264 and mpegts. 
* Fixed some minor UI issues
* Honored the "new" feature, that absolute paths in concat are not accepted
* Added support for OpenCV 3
* Cutting MOV,MP4,MPEG-TS, FLV and some more 

05.2017
* Added logging, some minor bugfixes/optimizations

09.2018
* The final QT4 version has been committed. 

16.09.2018
* Redesign of the frontend: Using python 3 and qt5.
* Introduction of a native C ffmpeg layer, which can convert the videos much faster than the default interface. (Beta!)

27.10.2018
* Minor changes on the UI
* Stabilized remux5 (native C ffmpeg lib). Better cut point recognition, transcoding fully implemented
* Currently transcoding is precise, but far too slow. Remuxing is faster than ffmpeg native 

10.11.2018 
* Increased the VBV Buffer for mpeg2 remuxing

22.12.2018
* Bug fix in remux5(native C ffmpeg lib) by correcting the time offset calculation on delayed/discarded frames

03.03.2019
* Introduced a stop button while processing. Fixed some audio time calculation issues

27.07.2019
* Changed remux5:. Exact PTS/DTS calculation for video. Rewrote transcoding. Supports multi threading.
* Allows mkv/VC1 codec, audio sync not good on source that has no PTS when decoding/muxing

15.08.2019
* refined remux5 - exact cut now possible on most codecs.
* no transcoding/remuxing with remux5 on mkv -> use ffmpeg switch

29.09.2019
* Changed remux5: Fine tuning for exact cut. Works now for webm, VC1/mkv and the standard mpeg sources (mp2 and mp4)
* Next steps: Select audio streams -  support ffmpeg cmd for transcoding/remuxing into other formats. Joining files

19.12.2019
* Added multi audio tracks. Support for vc1,vp8 and vp9 codecs. Handles AOMediaVideo (av1) on fast cut, but not on transcode. 
* Finalized cutting mpeg2 and h246 codecs.

10.06.2020
* Added install script.
* Introduced a "screen shot"
* Some internal polishment

13.02.2021
* Made clear what "Start" and "Stop" means (Tooltip)
* Increased precision for h264 (non TS) codecs. (remux)

23.04.2021
* Fixed unknown language codes
* Supports subtitles (ffmpeg & remux - remux only in "fast" mode) 
* Reworked remux5: better audio sync, more formats.
* Better support for mkv (only meager using the ffmpeg option)

25.04.2021
* Fix for mpegts target extensions (merci @ https://github.com/moebius1)
* DVB_SUBTITLE + eac3 audio support for m2t container 

02.05.2021
* Fix for webm container audio (parser based containers)
* changed rules for target file names and extensions
* update on roation informaton & handling OPENCV 4.5 +
* fix for slider crash on next file
* missing timestamp compensation (TS & VP8 streams)

28.05.2021
* Improve installation
* change VC.log location to /.config/VideoCut
* change vc.ini to the same location 
* prepare for PKGBUILD
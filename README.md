# VideoCut
Version 2.2.1

![Download](https://github.com/kanehekili/VideoCut/releases/download/2.2.1/videocut2.2.1.tar)

MP2/MP4 Cutter for Linux on base of mpv and ffmpeg. Cutting is lossless, the target file will not be reencoded. 

It can be used for cutting out certain parts of the film. Has been written in conjunction with the MDVB Recorder for removing ads. Handles avi,mkv,webm,vc1,mp2,mp4 (PS or TS). Other formats not tested but possible.

Lossless cutting implies not to reencode (decode/encode) the frames. So cutting can only be done at "I-Frames". The library searches for the closest Frame at the given cutting point.

Reencoding is possible for exact cutting as well as converting to different containers and codecs. 

VideoCut supports the cutting of subtitles when "Show subtitles"  in the settings dialog is enabled. This flag will display the "first" subtitles stream and will cut all subtitles that have been defined in the "language" dialog.

The current version is written in python3 and uses the qt5 widget kit.  

### Prerequisites
* Arch: python3, python-pillow and mpv
* Debian/Mint/Ubuntu: python3 python3-pil libmpv1 python3-pyqt5.qtopengl (no-recommends)
  #not working for Ubuntu 18.4: libmpv - use python3-opencv instead
* Fedora: python3-pillow-qt and mpv-libs.x86_64
* ffmpeg > 3.X to 5.X
* python3-pyqt5
* optional:(legacy) OpenCV 2.4 up to OpenCV 4.x (must be build with ffmpeg - with all its dependencies)

#### Set GTK Theme for this QT application
If you are running a DE with GTK/Gnome (as opposed to LXQT or KDE) you need to tweak your system:
(Arch users may have to install qt5-styleplugins from AUR)

`sudo nano /etc/environment`

add the follwing line:

`QT_QPA_PLATFORMTHEME=gtk2`

and logout/login (or reboot)

### Features
Cuts an mpg file into parts and joins them afterwards. All commands can be reached via the toolbar.

![Screenshot](https://github.com/kanehekili/VideoCut/blob/master/Videocut2.2.png)

The cutout parts will be joined without beeing recoded - the quality stays the same

The frame type (IBP) will be shown at the upper left corner. Subtitles can be displayed (Settings)

Instead of using the ffmpeg command line, Videocut offers its own muxer, which is based on the libavcodec libs. It provides better cuttings results and less artifacts than  ffmpeg.  This is set by default, but can be changed to the ffmpeg command line interface via the "Settings" dialog. 

Videocut supports subtitle cut. This is work in progress. 

As of version 2.1.x wayland is supported. For old hardware, the openGL feature may be disabled in the "Settings" dialog.
Since version 2.2.x the audio track can be omitted from the target file. (Video only) 

### Limitations
Using ffmpeg as cutting/joining tool some of the older versions of ffmpeg seem to have problems with syncing audio on avchd (mp4 TS) streams. (see Videocut muxer)

:boom: Only ffmpeg and libavformat versions >=3.1 are supported. 

:boom: Be aware that this tool does not cut exact on frame - except you reencode the whole film.

:boom: Subtitles come in differents flavours: Image and text. A conversion from image subs to text subs is not supported.

:boom: hevc codecs can be reencoded into an mp4 container but not remuxed - neither remux nor ffmpeg work can "copy" that codec. 

### Virtualenv or conda 
The fast remux binary doesn't run in a virtual environment, since the ffmpeg libraries used are not available. The ffmpeg blob could be used, if it would be on the /usr/bin path on the host system. Cross OS binary calls tend be a lot slower that in the native environment - so this software is limited to Linux (native or virtualized)

### Subtitles
Finalized in Version 1.3.0, improved in Version 2.0.0.  Not all containers (e.g. mp4) accept subtitles. A AVCH (h264 TS) Stream with DVB_SUB codec cannot be converted into mp4, so your miles may vary if you change the output container (defined by the file extension)

For DVB transport stream you should keep the ".m2t" ending, mkv containers shouldn't be changed either. See [here](https://en.wikipedia.org/wiki/Comparison_of_video_container_formats) for a overview of containers.

### Audio Monitoring
MPV supports audio streams while playing. Unfortunately it relies on the audio stream while seeking (precise) thus rendering exact seeking sometimes difficult due to problems decoding it. So audio is turned of (not just muted) while seeking. The "auto" mode has been replaced with the first valid audio stream and seems to work better for listening while cutting. 

### Settings
The cog icon at the toolbar will open the settings dialog, providing the following settings:

![Screenshot](https://github.com/kanehekili/VideoCut/blob/master/Settings.png)

* Reencode: Precice, frame exact cut. This option might take hours. Default is off
* VideoCut Muxer: Toggle between the internal Muxer or the ffmpeg command line. Default is on.
* Audio Mute: Mute all audio streams and extract video only. Default is off (no mute)
* Show Subtitles: Show subtitles in the preview window (mpv backend only)
* Usel GL Widgets (mpv backend only). Needed for wayland. Default is on (works with X11 as well)

Pressing one of the 3 lightgreen "buttons" toggles the upper 3 settings directly. 


### Languages
The flag icon opens the language dialog:

![Screenshot](https://github.com/kanehekili/VideoCut/blob/master/Language.png)

Select up to 3 languages for extraction. The tracks can be moved in order with the green arrows on the right side. 
Note that this selection is ignored if audio is muted. 


##Install

#### Install via ppa on Linux Mint or Ubuntu (focal/jammy/Mint20 and newer versions)
```
sudo add-apt-repository ppa:jentiger-moratai/mediatools
sudo apt update
sudo apt install --no-install-recommends videocut
```
(--no-install-recommends will install only what is required)
Select video and open it with "Open with ->VideoCut", oder via terminal "VideoCut"

Remove with:
`sudo apt remove videocut`

#### Install VideoCut via AUR (Arch Linux /Manjaro only)
* Use pamac or other GUI tools, search for "videocut" in AUR, click install
* Manually :
    * Download [PKGBUILD ](https://aur.archlinux.org/cgit/aur.git/snapshot/videocut.tar.gz)
    * unpack it and go into the "videocut" folder
    * execute `makepkg -s`
    * excute `sudo pacman -U videocut-2.x.x.x-1-x86_64.pkg.tar.zst` 
    * uninstall via `sudo pacman -Rs videocut`

Select video and open it with "Open with ->VideoCut", oder via terminal "VideoCut"


#### Install dependencies manually on Linux Mint or Ubuntu (tested from 20.04 to 22.04)
```
sudo apt –no-install-recommends install python3-pyqt5 ffmpeg python3-pil python3-pyqt5.qtopengl libmpv1
```
libmpv1 won't work on Ubuntu 18.04 - no bindings for the old libs - use opencv instead
For Ubuntu 23.04 or Debian 12 and newer libmpv2 should be used.

#### Install dependencies on Fedora
```
sudo dnf python3-qt5 ffmpeg python3-pillow-qt mpv-libs.x86_64
```

### How to install with a terminal
* Install dependencies (see prerequisites)
* Download the videocut*.tar from the download link (see above)
* Extract it to a location that suits you.
* Open a terminal to execute the install.sh file inside the folder with sudo like `sudo ./install.sh`
* (if you are in the download directory - just an example)
* The app will be installed in /opt/videocut with a link to /usr/bin. 
* The app should be appear in a menu or "Actvities"
* Can be openend by selecting a video file & Open with...
* In the terminal can be started via `videocut`
* python qt5, mpv and ffmpeg are required
* you may now remove that download directory.
* logs can be found in the user home ".config/VideoCut" folder

### How to remove
* Open a terminal
* execute `sudo /opt/videocut/uninstall.sh`

### Still on my list:
* Exact frame cut - see comment below 
* Differentiate between I-Fames and IDR-Frames
* Multi language support

### Using ffmpeg instead of Videocut muxer
remux5 is a c binary based on the libavcodec library, but uses an integrated approach to cut and join videos. It seems to be more precise than the ffmpeg API. It supports reencoding as well. It is activated by default and runs on all threads available. To activate FFMPEG, use the "coggs" icon (or click on the green labels) and deselect "VideoCut Muxer".

### Exact frame cut for one GOP only?
Can't be really implemented with the ffmpeg ABI. The transcoded part will have different coding parameters than the rest of the stream. A decoder cannot handle that change. On the other hand there is no way to transcode the GOP with the exact parameters of the original stream, since only a subset of h264 paramenters are accepted by the ffmpeg ABI. 

### Legacy Opencv (for Ubuntu 18.04 and older)
Since Videocut ran with OpenCV for many years it is still available. If needed it has to be downloaded 
* python3-opencv
* hdf5 (Arch only)

Copy the .desktop file and change the exec line to "Exec= python3 .../VideoCut.py -p cv %f"

Opencv will not be displaying subtitles nor frametypes.

### Changes 
28.03.2023
* Fix for target extension based on the codecs
* Added audio mute - idea by user ![RedFraction](https://github.com/RedFraction)

20.03.2023
* Dynamic ffmpeg build for Arch and debian
* Changed cutter

20.12.2022
* Fixed dialog handling on import and version errors 
* Refactored tools

28.11.2022
* Adapt to new mpv lib. Rel2: Fixed another mpv audio fluke
* No audio streams working again.

17.11.2022
* Audio fix vor very short cuts (< 1 min)
* Audio monitoring via mpv improved

04.05.2022
* Fixed ffmpeg3 build for older distros
* revamped logging

05.04.2022
* Support for wayland (OpenGL Widget)
* Tune MPV settings for older mpv versions

25.03.2022
* Improved seeking of mpeg2(ts) streams
* VC1 codec IDR frame recognition
* AV1 codec enhancements

06.03.2022
* adapted remux5 for ffmpeg version 5.0

03.03.2022
* remux fix for A/V offset. MPV VC1 support

05.02.2022
* Fixed failures on files recognition & analysis on NFS/Samba drives 

21.01.2022
* Replaced OpenCV with mpv for visualizing
* Show frame info and subtitles (inspired by @ https://github.com/lxs602)
* Reworked the ffmpeg API & improved some more subtitle features

25.11.2021
* ISO Code refactoring
* Bugfixing UI/Errorhandling

28.05.2021
* Improve installation
* change VC.log location to /.config/VideoCut
* change vc.ini to the same location 
* prepare for PKGBUILD

02.05.2021
* Fix for webm container audio (parser based containers)
* changed rules for target file names and extensions
* update on roation informaton & handling OPENCV 4.5 +
* fix for slider crash on next file
* missing timestamp compensation (TS & VP8 streams)

25.04.2021
* Fix for mpegts target extensions (merci @ https://github.com/moebius1)
* DVB_SUBTITLE + eac3 audio support for m2t container 

23.04.2021
* Fixed unknown language codes
* Supports subtitles (ffmpeg & remux - remux only in "fast" mode) 
* Reworked remux5: better audio sync, more formats.
* Better support for mkv (only meager using the ffmpeg option)

13.02.2021
* Made clear what "Start" and "Stop" means (Tooltip)
* Increased precision for h264 (non TS) codecs. (remux)

10.06.2020
* Added install script.
* Introduced a "screen shot"
* Some internal polishment

19.12.2019
* Added multi audio tracks. Support for vc1,vp8 and vp9 codecs. Handles AOMediaVideo (av1) on fast cut, but not on transcode. 
* Finalized cutting mpeg2 and h246 codecs.

29.09.2019
* Changed remux5: Fine tuning for exact cut. Works now for webm, VC1/mkv and the standard mpeg sources (mp2 and mp4)
* Next steps: Select audio streams -  support ffmpeg cmd for transcoding/remuxing into other formats. Joining files

15.08.2019
* refined remux5 - exact cut now possible on most codecs.
* no transcoding/remuxing with remux5 on mkv -> use ffmpeg switch

27.07.2019
* Changed remux5:. Exact PTS/DTS calculation for video. Rewrote transcoding. Supports multi threading.
* Allows mkv/VC1 codec, audio sync not good on source that has no PTS when decoding/muxing

03.03.2019
* Introduced a stop button while processing. Fixed some audio time calculation issues

22.12.2018
* Bug fix in remux5(native C ffmpeg lib) by correcting the time offset calculation on delayed/discarded frames

10.11.2018 
* Increased the VBV Buffer for mpeg2 remuxing

27.10.2018
* Minor changes on the UI
* Stabilized remux5 (native C ffmpeg lib). Better cut point recognition, transcoding fully implemented
* Currently transcoding is precise, but far too slow. Remuxing is faster than ffmpeg native 

16.09.2018
* Redesign of the frontend: Using python 3 and qt5.
* Introduction of a native C ffmpeg layer, which can convert the videos much faster than the default interface. (Beta!)

09.2018
* The final QT4 version has been committed. 

05.2017
* Added logging, some minor bugfixes/optimizations

30.11.2016 V 0.9.0
* Added filters for h264 and mpegts. 
* Fixed some minor UI issues
* Honored the "new" feature, that absolute paths in concat are not accepted
* Added support for OpenCV 3
* Cutting MOV,MP4,MPEG-TS, FLV and some more 

08.07.2016
* Added "Exact cut" feature. Ensures that the cut of the mp4 is exact (Frame exact). Takes longer, since the video has to be reencoded. 



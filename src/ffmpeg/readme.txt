ffmpeg:
remux5 copies packets from an input stream into an output stream without reencoding.
Fast, but cuts are only exact to the nearest I-frame.
Frame-exact cutting is available via the -r flag, which re-encodes the affected frames.

Supports ffmpeg 3.4 through 8.x (libavcodec major versions 57-62).
Tested on Arch Linux, Ubuntu Noble/Questing/Resolute and derivatives.

Is active by setting the "VideoCut Muxer" switch to on (Toolbar -> Cogs icon).


Building
--------
The src directory contains a makefile. Run:

    make          - release build (-O2, no debug symbols)
    make dev      - development build (-O2 -g -fanalyzer)
    make clean    - remove build artifacts

On Debian/Ubuntu the following packages are required:

    sudo apt-get install make gcc libavcodec-dev libavformat-dev libavutil-dev

On Arch Linux all headers are included in the ffmpeg package, no extra steps needed.


Standalone usage
----------------
remux5 can be used without VideoCut:

    remux5 -i inputFile -s ts1,ts2,ts3,ts4 outputFile

    -s  timestamps in seconds (decimals allowed). Always pairs: ts1=start1, ts2=stop1, ts3=start2, etc.
    -r  re-encode cut points for frame-exact cuts (slower)
    -l  select audio languages, e.g. -l eng,deu,fra
    -m  mute audio
    -n  strip subtitles
    -d  verbose/debug output
    -tp list all packets (no cutting)
    -tf list all packets and frames (no cutting)

Example:
    remux5 -i /home/user/Videos/film.m2t -s 386.080,415.760,510.460,529.320 /home/user/Videos/cut.mp4

Tested with mp2, mp4, mkv, vp8, vp9, av1, vc1 and TS streams.

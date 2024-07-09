ffmpeg:
remux5 is a prototype which simply copies packets from a stream and adds it to to the out put stream.
No reencoding involved. Fast.
Drawback: Not exact, since I frames need to be used for start/end.

currently the binary is compiled on arch linux against ffmpeg version 4.0.2 and 3.5
Tested on debian buster,Linux Mint and Ubuntu, as well as Fedora, propably on other distros with ffmpeg 4.0.2 and 3.5

Is activ by setting the "VideoCut Muxer" switch to on.(Toolbar ->Clogs icon)

The src directory contains a makefile, simply run "make" to build the executable.

On debian derivates follwing packes are needed to compile_
 sudo apt-get install make gcc libavcodec-dev libavformat-dev
 
 The binary may be used without VideoCut. The parameters:
 remux5 inputFile outputFile -s ts1,ts2,ts3,ts4...
 
 ts1-n are the timestamps in seconds, which should be taken over to the new file. ts1 is start1, ts2 is stop1, ts3 is start2 etc
 Will not work if there are not even numbers of timestamps- so always tuples.
 
 Still working on a more precise way to cut - but this is the fastest way to cut films.
 Tested with mp2 and mp4 vp8 vc1 and more. Mainly used TS streams that have been converted into PS streams.
 
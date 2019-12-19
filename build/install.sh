#!/bin/bash

#check if sudo
#if [ "$(id -u) !=0 ]; then
#  echo "Sorry, but you ain't root. Use sudo so run"
#  exit 1
#fi
#copy desktop to /usr/share applications
#cp Videocut.desktop /usr/share/applications
#mkdir -p /usr/local/sbin/VideoCut
#copy *.py /usr/local/sbin/VideoCut/
#copy -r icons/ to /usr/local/sbin/VideoCut/
#copy -r data to /usr/local/sbin/VideoCut/

#echo "App installed."

#generate a deskop with the current user.
touch /home/$USER/.local/share/applications/Videocut.desktop
echo "#!/usr/bin/env xdg-open" > /home/$USER/.local/share/applications/Videocut.desktop
echo "[Desktop Entry]" >> /home/$USER/.local/share/applications/Videocut.desktop
echo "Encoding=UTF-8" >> /home/$USER/.local/share/applications/Videocut.desktop
echo "Version=1.0" >> /home/$USER/.local/share/applications/Videocut.desktop
echo "Type=Application" >> /home/$USER/.local/share/applications/Videocut.desktop
echo "Exec=python2 /home/$USER/bin/videocut/VideoCut.py"  >> /home/$USER/.local/share/applications/Videocut.desktop
echo "Name=Video Cut" >> /home/$USER/.local/share/applications/Videocut.desktop
echo "Comment=MPG4 cutter" >> /home/$USER/.local/share/applications/Videocut.desktop
echo "Icon=/home/$USER/bin/videocut/icons/movie-icon.png" >> /home/$USER/.local/share/applications/Videocut.desktop
echo "NoDisplay=false" >> /home/$USER/.local/share/applications/Videocut.desktop
echo "Categories=GTK;AudioVideo" >> /home/$USER/.local/share/applications/Videocut.desktop
echo "MimeType=video/dv;video/mpeg;video/x-mpeg;video/msvideo;video/quicktime;video/x-anim;video/x-avi;video/x-ms-asf;video/x-ms-wmv;video/x-msvideo;video/x-nsv;video/x-flc;video/x-fli;video/x-flv;video/vnd.rn-realvideo;video/mp4;video/mp4v-es;video/mp2t;application/ogg;application/x-ogg;video/x-ogm+ogg;audio/x-vorbis+ogg;application/x-matroska;audio/x-matroska;video/x-matroska;video/webm;audio/webm;audio/x-mp3;audio/x-mpeg;audio/mpeg;audio/x-wav;audio/x-mpegurl;audio/x-scpls;audio/x-m4a;audio/x-ms-asf;audio/x-ms-asx;audio/x-ms-wax;application/vnd.rn-realmedia;audio/x-real-audio;audio/x-pn-realaudio;application/x-flac;audio/x-flac;application/x-shockwave-flash;misc/ultravox;audio/vnd.rn-realaudio;audio/x-pn-aiff;audio/x-pn-au;audio/x-pn-wav;audio/x-pn-windows-acm;image/vnd.rn-realpix;audio/x-pn-realaudio-plugin;application/x-extension-mp4;audio/mp4;audio/amr;audio/amr-wb;x-content/video-vcd;x-content/video-svcd;x-content/video-dvd;" >> /home/$USER/.local/share/applications/Videocut.desktop

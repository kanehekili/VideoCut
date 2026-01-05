#!/bin/bash
#check if sudo
if [ "$EUID" -ne 0 ] ; then
  echo "Sorry, but you are not root. Use sudo to run"
  exit 1
fi

sudo rm /usr/share/applications/VideoCut.desktop
sudo rm /usr/share/applications/EasyPlayer.desktop
sudo rm /usr/bin/VideoCut
sudo rm -rf /opt/videocut
echo "App removed."

#!/bin/bash
#check if sudo
if [ "$EUID" -ne 0 ] ; then
  echo "Sorry, but you are not root. Use sudo to run"
  exit 1
fi

sudo rm /usr/share/applications/VideoCut.desktop
sudo rm /usr/local/bin/VideoCut
sudo rm -rf /usr/local/bin/videocut
echo "App removed."
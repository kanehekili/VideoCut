#!/bin/bash
#check if sudo
if [ "$EUID" -ne 0 ] ; then
  echo "Sorry, but you are not root. Use sudo to run"
  exit 1
fi

sudo rm /usr/share/applications/VideoCut.desktop
#leftovers of the retired VideoPlay - gone in current installs, hence -f
sudo rm -f /usr/share/applications/VideoPlay.desktop /usr/bin/videoplay
sudo rm /usr/bin/VideoCut
sudo rm -rf /opt/videocut
echo "App removed."

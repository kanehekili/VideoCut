#!/bin/bash
#check if sudo
if [ "$EUID" -ne 0 ] ; then
  echo "Sorry, but you are not root. Use sudo to run"
  exit 1
fi
#copy desktop to /usr/share applications
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
sudo cp $DIR/VideoCut.desktop /usr/share/applications;
sudo mkdir -p /usr/local/bin/videocut;
sudo cp -r $DIR/* /usr/local/bin/videocut/;
sudo chmod  uo+rw /usr/local/bin/videocut/data;
sudo ln -s /usr/local/bin/videocut/VideoCut.py /usr/local/bin/VideoCut

echo "#########################################################################"
echo "#                  Ensure you have installed:                           #"                     
echo "#    debian/ubuntu/mint: python3-pyqt5 ffmpeg python3-opencv            #"
echo "#    arch &derivates:    python-pyqt5 python-numpy hdf5 ffmpeg opencv   #"
echo "#########################################################################"

echo "App installed."
#!/bin/bash
#check if sudo
if [ "$EUID" -ne 0 ] ; then
  echo "Sorry, but you are not root. Use sudo to run"
  exit 1
fi
#copy desktop to /usr/share applications
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
sudo cp $DIR/VideoCut.desktop /usr/share/applications;
sudo mkdir -p /opt/videocut;
sudo cp -r $DIR/* /opt/videocut/;
sudo ln -s /opt/videocut/VideoCut.py /usr/bin/VideoCut

echo "######################################################################"
echo "#                  Ensure you have installed:                        #"                     
echo "#    debian/ubuntu/mint: python3-pyqt6 ffmpeg python3-pil libmpv1    #"
echo "#    arch &derivates:    python-pyqt6 ffmpeg python-pillow mpv       #"
echo "######################################################################"

echo "App installed."
#!/bin/bash
ort=$(dirname "$0")
echo "updating mpv in ${ort}"
cd ../src/lib/
wget -O mpv.py https://raw.githubusercontent.com/jaseg/python-mpv/main/mpv.py

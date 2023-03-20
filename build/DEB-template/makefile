remux5: remux5.o
	gcc -o src/ffmpeg/bin/remux5 remux5.o -g -lavutil -lavformat -lavcodec 

remux5.o: src/ffmpeg/src/remux5.c
	gcc -c src/ffmpeg/src/remux5.c 

.PHONY: clean

clean:
	rm -f *.o remux5

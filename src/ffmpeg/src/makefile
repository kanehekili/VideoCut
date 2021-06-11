remux5: remux5.o
	gcc -Wno-deprecated-declarations -o ../bin/V4/remux5 remux5.o -g -lavutil -lavformat -lavcodec 

remux5.o: remux5.c
	gcc -Wno-deprecated-declarations -c remux5.c 

.PHONY: clean

clean:
	rm -f *.o remux5

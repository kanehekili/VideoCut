remux5: remux5.o
	gcc -o ../bin/remux5 remux5.o -g -lavutil -lavformat -lavcodec 

remux5.o: remux5.c
	gcc -c remux5.c 

.PHONY: clean

clean:
	rm -f *.o remux5

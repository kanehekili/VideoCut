CFLAGS += -g
LDLIBS += -lavcodec -lavformat -lavutil

all: ./../bin/remux5

./../bin/remux5: remux5
	cp $< $@

.PHONY: all clean

clean:
	rm -f *.o remux5

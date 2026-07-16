CFLAGS += -O2 -Wall -Wextra -Wno-unused-parameter
LDLIBS += -lavcodec -lavformat -lavutil

all: ./../bin/remux5

./../bin/remux5: remux5
	cp $< $@

dev: CFLAGS += -g -fanalyzer
dev: ./../bin/remux5

.PHONY: all dev clean

clean:
	rm -f *.o remux5

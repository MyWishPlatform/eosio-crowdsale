NAME=crowdsale

all:
	rm -rf build
	mkdir build
	eosiocpp -o build/$(NAME).wast src/$(NAME).cpp
	eosiocpp -g build/$(NAME).abi src/$(NAME).cpp

.PHONY: all clean test debug
NAME=crowdsale

all:
	git submodule init
	git submodule update
	make -C eosiotoken
	rm -rf $(NAME)
	mkdir $(NAME)
	cp *.abi $(NAME)
	eosiocpp -o $(NAME)/$(NAME).wast $(NAME).cpp

build:
	make -C eosiotoken
	rm -rf $(NAME)
	mkdir $(NAME)
	cp *.abi $(NAME)
	eosiocpp -o $(NAME)/$(NAME).wast $(NAME).cpp

clean:
	rm -rf build

test:
	python3 unittest_crowdsale.py

debug:
	python3 unittest_crowdsale.py --verbose

NAME=crowdsale

all:
	rm -rf $(NAME)/$(NAME).wasm
	rm -rf $(NAME)/$(NAME).wast
	git submodule init
	git submodule update
	make -C eosiotoken
	eosiocpp -o $(NAME)/$(NAME).wast $(NAME).cpp

test:
	python3 unittest_crowdsale.py

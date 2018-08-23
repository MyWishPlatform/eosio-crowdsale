NAME=crowdsale

all:
	mv $(NAME)/$(NAME).abi .
	rm -rf $(NAME)
	mkdir $(NAME)
	mv $(NAME).abi $(NAME)
	eosiocpp -o $(NAME)/$(NAME).wast $(NAME).cpp
#	eosiocpp -g $(NAME)/$(NAME).abi $(NAME).cpp

test:
	git submodule init
	git submodule update
	make -C eosiotoken
	python3 unittest_crowdsale.py

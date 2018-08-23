NAME=crowdsale

all:
	mv $(NAME)/$(NAME).abi .
	rm -rf $(NAME)
	mkdir $(NAME)
	mv $(NAME).abi $(NAME)
#	git submodule init
#	git submodule update
#	make -C eosiotoken
	eosiocpp -o $(NAME)/$(NAME).wast $(NAME).cpp
#	eosiocpp -g $(NAME)/$(NAME).abi $(NAME).cpp

test:
	python3 unittest_crowdsale.py

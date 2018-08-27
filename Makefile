NAME=crowdsale

all:
	mv $(NAME)/*.abi .
	rm -rf $(NAME)
	mkdir $(NAME)
	mv *.abi $(NAME)
	eosiocpp -o $(NAME)/$(NAME).wast $(NAME).cpp
#	eosiocpp -g $(NAME)/$(NAME).abi $(NAME).cpp

test:
	git submodule init
	git submodule update
	make -C eosiotoken
	mv $(NAME)/crowdsale.abi .
	python3 unittest_crowdsale.py ; mv crowdsale.abi $(NAME)

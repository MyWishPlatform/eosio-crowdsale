NAME=crowdsale

all:
	git submodule init
	git submodule update
	make -C eosiotoken
	rm -rf $(NAME)
	mkdir $(NAME)
	cp *.abi $(NAME)
	eosiocpp -o $(NAME)/$(NAME).wast $(NAME).cpp

test:
	python3 unittest_crowdsale.py

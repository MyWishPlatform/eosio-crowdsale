#pragma once

#include <eosiolib/currency.hpp>
#include <eosiolib/vector.hpp>
#include <eosiolib/eosio.hpp>

#include <string>

class crowdsale : public eosio::contract {
private:
	struct userchoice_t {
		account_name user;
		account_name token_contract;
		eosio::symbol_type symbol;
        uint64_t primary_key() const { return user; }
	};

	struct crowdsale_t {
		account_name issuer;
		account_name token_contract;
		eosio::symbol_type symbol;
        uint64_t primary_key() const { return symbol.name(); }
	};

	typedef eosio::multi_index<N(userchoice_t), userchoice_t> user_choice_index;
	typedef eosio::multi_index<N(crowdsale_t), crowdsale_t> crowdsale_index;

public:
	crowdsale(account_name self) :
		eosio::contract(self)
	{}

	void regcrowdsale(account_name issuer, account_name token_contract, eosio::asset asset);
	void selcrowdsale(account_name user, account_name token_contract, eosio::asset asset);
	void transfer(account_name from, account_name to);
};

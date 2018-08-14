#pragma once

#include <eosiolib/currency.hpp>
#include <eosiolib/vector.hpp>
#include <eosiolib/eosio.hpp>
#include <eosiolib/singleton.hpp>

#include <string>

#include "config.h"

#define STR_EXPAND(C) #C
#define STR(C) STR_EXPAND(C)

class crowdsale : public eosio::contract {
private:
	struct multiplier_t {
		int num;
		int denom;
	};

	struct state_t {
		bool finalized;
		bool whitelist;
		multiplier_t multiplier;
	} state;

	struct whitelist_t {
		account_name account;
        uint64_t primary_key() const { return account; }
	};

	eosio::extended_asset asset;
	eosio::singleton<N(state), state_t> state_singleton;
	eosio::multi_index<N(whitelist), whitelist_t> whitelist;

	state_t default_parameters() {
		return state_t{
			.finalized = false,
			.whitelist = WHITELIST,
			.multiplier = multiplier_t{
				.num = MULTIPLIER_NUM,
				.denom = MULTIPLIER_DENOM
			}
		};
	}

public:
	crowdsale(account_name self);
	~crowdsale();
	void transfer(uint64_t sender, uint64_t receiver);
	void on_deposit(account_name investor, eosio::asset quantity);
	void white(account_name account);
	void unwhite(account_name account);
	void setwhite(bool value); // TODO: remove
	void finalize();
	void setfinalize(bool value); // TODO: remove
};

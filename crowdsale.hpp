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
	struct transfer_t {
		account_name from;
		account_name to;
		eosio::asset quantity;
		eosio::string memo;
	};

	struct multiplier_t {
		int num;
		int denom;
	};

	struct state_t {
		bool finalized;
		multiplier_t multiplier;
	};

	eosio::extended_asset asset;
	eosio::singleton<N(state), state_t> state_singleton;
	state_t state;

	state_t default_parameters() {
		return state_t{
			.finalized = false,
			.multiplier = multiplier_t{
				.num = 3,
				.denom = 2
			}
		};
	}

public:
	crowdsale(account_name self);
	~crowdsale();
	void transfer(uint64_t sender, uint64_t receiver);
	void finalize();
	void unfinalize();
};

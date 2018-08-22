#pragma once

#include <eosiolib/currency.hpp>
#include <eosiolib/vector.hpp>
#include <eosiolib/eosio.hpp>
#include <eosiolib/singleton.hpp>

#include <string>

#include "config.h"

class crowdsale : public eosio::contract {
private:
	struct multiplier_t {
		uint32_t num;
		uint32_t denom;
	};

	struct state_t {
		bool finalized;
		int64_t total_deposit;
		int64_t total_tokens;
		time_t start;
		time_t finish;
	};

	struct deposit_t {
		account_name account;
		int64_t amount;
		int64_t tokens;
		uint64_t primary_key() const { return account; }
	};

	struct whitelist_t {
		account_name account;
		uint64_t primary_key() const { return account; }
	};

	eosio::singleton<N(state), state_t> state_singleton;
	eosio::multi_index<N(deposit), deposit_t> deposits;
	eosio::multi_index<N(whitelist), whitelist_t> whitelist;

	eosio::extended_asset asset_eos;
	eosio::extended_asset asset_tkn;

	state_t state;

	state_t default_parameters() {
		return state_t{
			.finalized = false,
			.total_tokens = 0,
			.start = START_DATE,
			.finish = FINISH_DATE
		};
	}

	void send_funds(account_name target, eosio::extended_asset asset);

public:
	crowdsale(account_name self);
	~crowdsale();
	void init();
	void transfer(uint64_t sender, uint64_t receiver);
	void on_deposit(account_name investor, eosio::asset quantity);
	void white(account_name account);
	void unwhite(account_name account);
	void finalize();
};

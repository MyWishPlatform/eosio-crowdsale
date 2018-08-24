#pragma once

#include <eosiolib/eosio.hpp>
#include <eosiolib/singleton.hpp>
#include <eosiolib/asset.hpp>

#include "config.h"
#include "pow10.h"
#include "str_expand.h"

class crowdsale : public eosio::contract {
private:
	struct multiplier_t {
		uint32_t num;
		uint32_t denom;
	};

	struct state_t {
		int64_t total_eoses;
		int64_t total_tokens;
		time_t start;
		time_t finish;
		int32_t inline_call;
	};

	// @abi table deposit
	struct deposit_t {
		account_name account;
		int64_t eoses;
		int64_t tokens;
		uint64_t primary_key() const { return account; }
	};

	// @abi table whitelist
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
			.total_eoses = 0,
			.total_tokens = 0,
			.start = START_DATE,
			.finish = FINISH_DATE,
			.inline_call = 0
		};
	}

	void send_funds(account_name target, eosio::extended_asset asset, std::string memo);

public:
	crowdsale(account_name self);
	~crowdsale();
	void transfer(uint64_t sender, uint64_t receiver);
	void unlock(uint64_t sender, uint64_t receiver);
	void init();
	void on_deposit(account_name investor, eosio::asset quantity);
	void white(account_name account);
	void unwhite(account_name account);
	void finalize(account_name withdraw_to);
	void refund(account_name investor);
};

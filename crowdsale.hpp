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
#ifdef DEBUG
		time_t time;
#endif
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

	account_name issuer;

	state_t state;

	void on_deposit(account_name investor, eosio::asset quantity);

	state_t default_parameters() const {
		return state_t{
			.total_eoses = 0,
			.total_tokens = 0,
			.start = 0,
			.finish = 0,
#ifdef DEBUG
			.time = 0
#endif
		};
	}

	void inline_issue(account_name to, eosio::extended_asset quantity, std::string memo) const {
		struct issue {
			account_name to;
			eosio::asset quantity;
			std::string memo;
		};
		eosio::action(
			eosio::permission_level(this->_self, N(active)),
			quantity.contract,
			N(issue),
			issue{to, quantity, memo}
		).send();
	}

	void inline_transfer(account_name from, account_name to, eosio::extended_asset quantity, std::string memo) const {
		struct transfer {
			account_name from;
			account_name to;
			eosio::asset quantity;
			std::string memo;
		};
		eosio::action(
			eosio::permission_level(this->_self, N(active)),
			quantity.contract,
			N(transfer),
			transfer{from, to, quantity, memo}
		).send();
	}

public:
	crowdsale(account_name self);
	~crowdsale();
	void transfer(uint64_t sender, uint64_t receiver);
	void init(time_t start, time_t finish);
	void setfinish(time_t finish);
	void white(account_name account);
	void unwhite(account_name account);
	void finalize();
	void withdraw();
	void refund(account_name investor);
#ifdef DEBUG
	void settime(time_t time);
#endif
};

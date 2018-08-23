#include "crowdsale.hpp"
#include "override.h"

crowdsale::crowdsale(account_name self) :
	eosio::contract(self),
	state_singleton(this->_self, this->_self),
	deposits(this->_self, this->_self),
	whitelist(this->_self, this->_self),
	asset_eos(
		eosio::asset(0, eosio::string_to_symbol(4, "EOS")),
		eosio::string_to_name("eosio.token")
	),
	asset_tkn(
		eosio::asset(0, eosio::string_to_symbol(DECIMALS, STR(SYMBOL))),
		eosio::string_to_name(STR(CONTRACT))
	),
	state(state_singleton.exists() ? state_singleton.get() : default_parameters())
{
}

crowdsale::~crowdsale() {
	this->state_singleton.set(this->state, this->_self);
}

void crowdsale::init() {
	if (this->state_singleton.exists()) return;
	require_auth(this->_self);

	struct dest {
		account_name to;
		int64_t amount;
	} dests[MINTCNT];
	#define FILLDESTS(z, i, data)\
		dests[i] = dest{\
			eosio::string_to_name(STR(MINTDEST ## i)),\
			MINTVAL ## i\
		};
	BOOST_PP_REPEAT(MINTCNT, FILLDESTS, );

	struct issue {
		account_name to;
		eosio::asset quantity;
		eosio::string memo;
	};

	for (int i = 0; i < MINTCNT; i++) {
		this->asset_tkn.set_amount(dests[i].amount);
		eosio::action(
			eosio::permission_level(this->_self, N(active)),
			asset_tkn.contract,
			N(issue),
			issue{dests[i].to, this->asset_tkn, "Initial token distribution"}
		).send();
	}

	this->asset_tkn.set_amount(HARD_CAP_TKN);
	eosio::action(
		eosio::permission_level(this->_self, N(active)),
		asset_tkn.contract,
		N(issue),
		issue{this->_self, this->asset_tkn, "Generate tokens"}
	).send();
}

void crowdsale::send_funds(account_name target, eosio::extended_asset asset, eosio::string memo) {
	struct transfer {
		account_name from;
		account_name to;
		eosio::asset quantity;
		eosio::string memo;
	};
	eosio::action(
		eosio::permission_level(this->_self, N(active)),
		asset.contract,
		N(transfer),
		transfer{this->_self, target, this->asset_tkn, memo}
	).send();
}

void crowdsale::transfer(uint64_t sender, uint64_t receiver) {
	struct transfer_t {
		account_name from;
		account_name to;
		eosio::asset quantity;
		eosio::string memo;
	} data = eosio::unpack_action_data<transfer_t>();
	eosio_assert(data.quantity.amount > 0, "Transfer must be positive");
	eosio_assert(data.quantity.is_valid(), "Invalid token transfer");
	if (data.quantity.symbol == this->asset_eos.symbol) {
		if (data.from == this->_self) {
			eosio_assert(this->state.finalized, "Funds can be withdrawn only after finalize");
		} else {
			this->on_deposit(data.from, data.quantity);
		}
	} else if (data.quantity.symbol == this->asset_tkn.symbol) {
		eosio_assert(data.from == this->_self, "Only EOS Deposits");
		eosio_assert(sender == this->_self, "Only inline token transfers");
	}
}

void crowdsale::on_deposit(account_name investor, eosio::asset quantity) {
	eosio_assert(now() >= this->state.start, "Crowdsale hasn't started");
	eosio_assert(!this->state.finalized, "Crowdsale finished");
	if (WHITELIST) {
		auto it = this->whitelist.find(investor);
		eosio_assert(it != this->whitelist.end(), "Account not whitelisted");
	}
	auto it = this->deposits.find(investor);
	int64_t tokens_to_give = quantity.amount * RATE / RATE_DENOM;
	int64_t entire_deposit = quantity.amount;
	int64_t entire_tokens = tokens_to_give;
	if (it != this->deposits.end()) {
		entire_deposit += it->amount;
		entire_tokens += it->tokens;
	}
	eosio_assert(entire_deposit >= MIN_CONTRIB, "Contribution too low");
	eosio_assert((entire_deposit <= MAX_CONTRIB) || !MAX_CONTRIB, "Contribution too high");
	int64_t new_total_tokens = this->state.total_tokens + tokens_to_give;
	eosio_assert(new_total_tokens <= HARD_CAP_TKN, "Token hard cap reached");
	this->state.total_tokens = new_total_tokens;
	if (it == this->deposits.end()) {
		this->deposits.emplace(investor, [investor, entire_deposit, entire_tokens](auto& deposit) {
			deposit.account = investor;
			deposit.amount = entire_deposit;
			deposit.tokens = entire_tokens;
		});
	} else {
		this->deposits.modify(it, investor, [investor, entire_deposit, entire_tokens](auto& deposit) {
			deposit.account = investor;
			deposit.amount = entire_deposit;
			deposit.tokens = entire_tokens;
		});
	}
	if (TRANSFERABLE) {
		this->asset_tkn.set_amount(tokens_to_give);
		send_funds(investor, this->asset_tkn, "Crowdsale");
	}
}

void crowdsale::white(account_name account) {
	require_auth(this->_self);
	eosio_assert(WHITELIST, "Whitelist not enabled");
	auto it = this->whitelist.find(account);
	eosio_assert(it == this->whitelist.end(), "Account already whitelisted");
	this->whitelist.emplace(this->_self, [account](auto& e) {
		e.account = account;
	});
}

void crowdsale::unwhite(account_name account) {
	require_auth(this->_self);
	eosio_assert(WHITELIST, "Whitelist not enabled");
	auto it = this->whitelist.find(account);
	eosio_assert(it != this->whitelist.end(), "Account not whitelisted");
	whitelist.erase(it);
}

void crowdsale::finalize() {
	eosio_assert(now() > this->state.finish, "Crowdsale hasn't finished");
	eosio_assert(!this->state.finalized, "Crowdsale already finalized");
	bool success = this->state.total_tokens >= SOFT_CAP_TKN;
	if (!TRANSFERABLE || !success) {
		size_t offset_eos = offsetof(deposit_t, amount);
		size_t offset_tkn = offsetof(deposit_t, tokens);
		size_t offset = success ? offset_tkn : offset_eos;
		eosio::string memo = success ? "Crowdsale" : "Refund";
		eosio::extended_asset& asset = success ? this->asset_tkn : this->asset_eos;
		for (auto it = this->deposits.begin(); it != this->deposits.end(); it++) {
			asset.set_amount(*static_cast<const int64_t*>(static_cast<const void*>(static_cast<const char*>(static_cast<const void*>(&(*it))) + offset)));
			send_funds(it->account, asset, memo);
		}
	}
	this->state.finalized = true;
}

EOSIO_ABI(crowdsale, (init)(transfer)(white)(unwhite)(finalize));

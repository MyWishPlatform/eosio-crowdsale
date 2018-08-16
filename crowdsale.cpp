#include "crowdsale.hpp"
#include "override.h"

crowdsale::crowdsale(account_name self) :
	eosio::contract(self),
	state_singleton(this->_self, this->_self),
	deposits(this->_self, this->_self),
	whitelist(this->_self, this->_self)
{
	this->state = state_singleton.exists() ? state_singleton.get() : default_parameters();
}

crowdsale::~crowdsale() {
	this->state_singleton.set(this->state, this->_self);
}

void crowdsale::init() {
	this->state = default_parameters();
}

void crowdsale::transfer(uint64_t sender, uint64_t receiver) {
	struct transfer_t {
		account_name from;
		account_name to;
		eosio::asset quantity;
		eosio::string memo;
	} data = eosio::unpack_action_data<transfer_t>();
	if (data.to != this->_self) {
		return;
	}
	eosio_assert(data.quantity.symbol == eosio::string_to_symbol(4, "EOS"), "Only EOS deposits");
	eosio_assert(data.quantity.is_valid(), "Invalid token transfer");
	eosio_assert(data.quantity.amount > 0, "Deposit must be positive");
	this->on_deposit(data.from, data.quantity);
}

void crowdsale::on_deposit(account_name investor, eosio::asset quantity) {
	eosio_assert(now() >= this->state.start, "Crowdsale hasn't started");
	eosio_assert(!this->state.finalized, "Crowdsale finished");
	if (WHITELIST) {
		auto it = this->whitelist.find(investor);
		eosio_assert(it != this->whitelist.end(), "Account not whitelisted");
	}
	auto it = this->deposits.find(investor);
	int64_t entire_deposit = quantity.amount;
	int64_t entire_tokens = quantity.amount * MULTIPLIER_NUM / MULTIPLIER_DENOM;
	if (it != this->deposits.end()) {
		entire_deposit += it->amount;
		entire_tokens += it->tokens;
	}
	eosio_assert(entire_deposit >= MIN_CONTRIB, "Contribution too low");
	eosio_assert(entire_deposit <= MAX_CONTRIB, "Contribution too high");
	int64_t new_total_deposit = this->state.total_deposit + quantity.amount;
	eosio_assert(new_total_deposit <= HARD_CAP, "Hard cap reached");
	this->state.total_deposit = new_total_deposit;
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
	bool success = this->state.total_deposit >= SOFT_CAP;
	eosio::extended_asset asset(
		eosio::asset(0, eosio::string_to_symbol(success ? PRECISION : 4, success ? STR(SYMBOL) : "EOS")),
		eosio::string_to_name(success ? STR(CONTRACT) : "eosio.token")
	);
	auto send_funds = [this, asset](account_name account) {
		eosio::currency::inline_transfer(this->_self, account, asset, "crowdsale");
	};
	if (success) {
		for (auto it = this->deposits.begin(); it != this->deposits.end(); it++) {
			asset.set_amount(it->tokens);
			send_funds(it->account);
		}
	} else {
		for (auto it = this->deposits.begin(); it != this->deposits.end(); it++) {
			asset.set_amount(it->amount);
			send_funds(it->account);
		}
	}
	this->state.finalized = true;
}

// debug
void crowdsale::setfinalize(bool value) {
	require_auth(this->_self);
	this->state.finalized = !!value;
}

EOSIO_ABI(crowdsale, (init)(transfer)(white)(unwhite)(finalize)(setfinalize));

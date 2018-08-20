#include "crowdsale.hpp"
#include "override.h"

#define STR_EXPAND(C) #C
#define STR(C) STR_EXPAND(C)

#define CONTRACT mywishtoken5

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
	if (!state_singleton.exists()) {
		struct create {
			account_name issuer;
			eosio::asset maximum_supply;
		};
		struct issue {
			account_name to;
			eosio::asset quantity;
			eosio::string memo;
		};
		struct chissuer {
			eosio::symbol_type symbol;
			account_name new_issuer;
		};
		struct dest {
			account_name to;
			int64_t amount;
		};

		int64_t premint_amount = 0;
		dest dests[MINTCNT];

		#define FILLDESTS(z, i, data) dests[i] = dest{eosio::string_to_name(STR(MINTDEST ## i)), MINTVAL ## i}; premint_amount += MINTVAL ## i;
		BOOST_PP_REPEAT(MINTCNT, FILLDESTS, );

		this->asset_tkn.set_amount(HARD_CAP_TKN);
		this->asset_tkn += eosio::asset(premint_amount, this->asset_tkn.symbol);
		eosio::action(eosio::permission_level(this->_self, N(active)), asset_tkn.contract, N(create), create{this->_self, this->asset_tkn}).send();
		for (int i = 0; i < MINTCNT; i++) {
			this->asset_tkn.set_amount(dests[i].amount);
			eosio::action(eosio::permission_level(this->_self, N(active)), asset_tkn.contract, N(issue), issue{dests[i].to, this->asset_tkn, "initial token distribution"}).send();
		}
		eosio::action(eosio::permission_level(this->_self, N(active)), asset_tkn.contract, N(chissuer), chissuer{this->asset_tkn.symbol, eosio::string_to_name(STR(ISSUER))}).send();
	}
}

crowdsale::~crowdsale() {
	this->state_singleton.set(this->state, this->_self);
}

// debug
void crowdsale::init() {
	this->state = default_parameters();
}

void crowdsale::send_funds(account_name target, eosio::extended_asset asset) {
	eosio::currency::inline_transfer(this->_self, target, asset, "crowdsale");
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
	int64_t tokens_to_give = quantity.amount * RATE / RATE_DENOM;
	int64_t entire_deposit = quantity.amount;
	int64_t entire_tokens = tokens_to_give;
	if (it != this->deposits.end()) {
		entire_deposit += it->amount;
		entire_tokens += it->tokens;
	}
	eosio_assert(entire_deposit >= MIN_CONTRIB, "Contribution too low");
	eosio_assert(entire_deposit <= MAX_CONTRIB, "Contribution too high");
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
		send_funds(investor, this->asset_tkn);
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
		eosio::extended_asset& asset = success ? this->asset_tkn : this->asset_eos;
		for (auto it = this->deposits.begin(); it != this->deposits.end(); it++) {
			asset.set_amount(*static_cast<const int64_t*>(static_cast<const void*>(static_cast<const char*>(static_cast<const void*>(&(*it))) + offset)));
			send_funds(it->account, asset);
		}
	}
	this->state.finalized = true;
}

EOSIO_ABI(crowdsale, (init)(transfer)(white)(unwhite)(finalize));

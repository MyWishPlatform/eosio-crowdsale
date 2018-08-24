#include "crowdsale.hpp"
#include "override.hpp"

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

void crowdsale::send_funds(account_name target, eosio::extended_asset asset, std::string memo) {
	struct transfer {
		account_name from;
		account_name to;
		eosio::asset quantity;
		std::string memo;
	};
	this->state.inline_call++;
	eosio::action(
		eosio::permission_level(this->_self, N(active)),
		asset.contract,
		N(transfer),
		transfer{this->_self, target, this->asset_tkn, memo}
	).send();
}

void crowdsale::init() {
	eosio_assert(!this->state_singleton.exists(), "Already initialized");
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
		std::string memo;
	};

	for (int i = 0; i < MINTCNT; i++) {
		this->state.inline_call++;
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

void crowdsale::on_deposit(account_name investor, eosio::asset quantity) {
	eosio_assert(now() >= this->state.start, "Crowdsale hasn't started");
	eosio_assert(now() <= this->state.finish, "Crowdsale finished");

	eosio_assert(quantity.amount >= MIN_CONTRIB, "Contribution too low");
	eosio_assert((quantity.amount <= MAX_CONTRIB) || !MAX_CONTRIB, "Contribution too high");

	if (WHITELIST) {
		auto it = this->whitelist.find(investor);
		eosio_assert(it != this->whitelist.end(), "Account not whitelisted");
	}

	auto it = this->deposits.find(investor);

	int64_t tokens_to_give = quantity.amount * POW10(DECIMALS) * RATE / (POW10(4) * RATE_DENOM);

	this->state.total_eoses += quantity.amount;
	this->state.total_tokens += tokens_to_give;

	eosio_assert(this->state.total_tokens <= HARD_CAP_TKN, "Hard cap reached");

	int64_t entire_eoses = quantity.amount;
	int64_t entire_tokens = tokens_to_give;
	if (it != this->deposits.end()) {
		entire_eoses += it->eoses;
		entire_tokens += it->tokens;
	}

	if (it == this->deposits.end()) {
		this->deposits.emplace(investor, [investor, entire_eoses, entire_tokens](auto& deposit) {
			deposit.account = investor;
			deposit.eoses = entire_eoses;
			deposit.tokens = entire_tokens;
		});
	} else {
		this->deposits.modify(it, investor, [investor, entire_eoses, entire_tokens](auto& deposit) {
			deposit.account = investor;
			deposit.eoses = entire_eoses;
			deposit.tokens = entire_tokens;
		});
	}

	this->asset_tkn.set_amount(tokens_to_give);
	send_funds(investor, this->asset_tkn, "Crowdsale");
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

void crowdsale::finalize(account_name withdraw_to) {
	eosio_assert(now() > this->state.finish || this->state.total_tokens >= HARD_CAP_TKN, "Crowdsale hasn't finished");
	eosio_assert(this->state.total_tokens >= SOFT_CAP_TKN, "Softcap not reached");

	require_auth(this->_self);

	if (!TRANSFERABLE) {
		struct unlock {
			eosio::symbol_type symbol;
		};
		eosio::action(
			eosio::permission_level(this->_self, N(active)),
			this->asset_tkn.contract,
			N(transfer),
			unlock{this->asset_tkn.symbol}
		).send();
	}

	this->asset_eos.set_amount(this->state.total_eoses);
	send_funds(withdraw_to, this->asset_eos, "Withdraw");
}

void crowdsale::refund(account_name investor) {
	eosio_assert(now() > this->state.finish, "Crowdsale hasn't finished");
	eosio_assert(this->state.total_tokens < SOFT_CAP_TKN, "Softcap reached");

	require_auth(investor);

	auto it = this->deposits.find(investor);
	eosio_assert(it != this->deposits.end(), "Nothing to refund");

	this->asset_eos.set_amount(it->eoses);
	send_funds(investor, this->asset_eos, "Refund");
}

EOSIO_ABI(crowdsale, (init)(white)(unwhite)(finalize)(refund)(transfer)(unlock));

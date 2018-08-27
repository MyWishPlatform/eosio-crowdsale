#include "crowdsale.hpp"
#include "override.hpp"

#define EOS2TKN(EOS) EOS * POW10(DECIMALS) * RATE / (POW10(4) * RATE_DENOM)

#ifdef DEBUG
#define NOW this->state.time
#else
#define NOW now()
#endif

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
	issuer(eosio::string_to_name(STR(ISSUER))),
	state(state_singleton.exists() ? state_singleton.get() : default_parameters())
{
}

crowdsale::~crowdsale() {
	this->state_singleton.set(this->state, this->_self);
}

void crowdsale::on_deposit(account_name investor, eosio::asset quantity) {
	eosio_assert(NOW >= this->state.start, "Crowdsale hasn't started");
	eosio_assert(NOW <= this->state.finish, "Crowdsale finished");

	eosio_assert(quantity.amount >= MIN_CONTRIB, "Contribution too low");
	eosio_assert((quantity.amount <= MAX_CONTRIB) || !MAX_CONTRIB, "Contribution too high");

	if (WHITELIST) {
		auto it = this->whitelist.find(investor);
		eosio_assert(it != this->whitelist.end(), "Account not whitelisted");
	}

	auto it = this->deposits.find(investor);

	int64_t tokens_to_give = EOS2TKN(quantity.amount);

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
	this->inline_issue(investor, this->asset_tkn, "Crowdsale");
}

void crowdsale::init(time_t start, time_t finish) {
	eosio_assert(!this->state_singleton.exists(), "Already initialized");
	require_auth(this->_self);

	this->state.start = start;
	this->state.finish = finish;

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

	for (int i = 0; i < MINTCNT; i++) {
		this->asset_tkn.set_amount(dests[i].amount);
		this->inline_issue(dests[i].to, this->asset_tkn, "Initial token distribution");
	}
}

void crowdsale::white(account_name account) {
	require_auth(this->issuer);
	eosio_assert(WHITELIST, "Whitelist not enabled");
	auto it = this->whitelist.find(account);
	eosio_assert(it == this->whitelist.end(), "Account already whitelisted");
	this->whitelist.emplace(this->_self, [account](auto& e) {
		e.account = account;
	});
}

void crowdsale::unwhite(account_name account) {
	require_auth(this->issuer);
	eosio_assert(WHITELIST, "Whitelist not enabled");
	auto it = this->whitelist.find(account);
	eosio_assert(it != this->whitelist.end(), "Account not whitelisted");
	whitelist.erase(it);
}

void crowdsale::finalize(account_name withdraw_to) {
	eosio_assert(NOW > this->state.finish || this->state.total_tokens + EOS2TKN(MIN_CONTRIB) >= HARD_CAP_TKN, "Crowdsale hasn't finished");
	eosio_assert(this->state.total_tokens >= SOFT_CAP_TKN, "Softcap not reached");
	eosio_assert(!TRANSFERABLE, "There is no reason to call finalize");

	struct unlock {
		eosio::symbol_type symbol;
	};
	eosio::action(
		eosio::permission_level(this->_self, N(active)),
		this->asset_tkn.contract,
		N(unlock),
		unlock{this->asset_tkn.symbol}
	).send();
}

void crowdsale::withdraw() {
	eosio_assert(this->state.total_tokens >= SOFT_CAP_TKN, "Softcap not reached");

	require_auth(this->issuer);

	this->asset_eos.set_amount(this->state.total_eoses);
	this->inline_transfer(this->_self, this->issuer, this->asset_eos, "Withdraw");

	this->state.total_eoses = 0;
}

void crowdsale::refund(account_name investor) {
	eosio_assert(NOW > this->state.finish, "Crowdsale hasn't finished");
	eosio_assert(this->state.total_tokens < SOFT_CAP_TKN, "Softcap reached");

	require_auth(investor);

	auto it = this->deposits.find(investor);
	eosio_assert(it != this->deposits.end(), "Nothing to refund");

	this->asset_eos.set_amount(it->eoses);
	this->inline_transfer(this->_self, investor, this->asset_eos, "Refund");

	this->deposits.modify(it, investor, [](auto& d) {
		d.eoses = 0;
	});
}

#ifdef DEBUG
void crowdsale::settime(time_t time) {
	this->state.time = time;
}
EOSIO_ABI(crowdsale, (init)(white)(unwhite)(finalize)(withdraw)(refund)(transfer)(settime));
#else
EOSIO_ABI(crowdsale, (init)(white)(unwhite)(finalize)(withdraw)(refund)(transfer));
#endif

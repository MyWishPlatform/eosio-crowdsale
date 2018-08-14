#include "crowdsale.hpp"

#undef EOSIO_ABI
#define EOSIO_ABI(TYPE, MEMBERS)\
extern "C" {\
	void apply(uint64_t receiver, uint64_t code, uint64_t action) {\
		auto self = receiver;\
		if (action == N(onerror)) {\
			eosio_assert(code == N(eosio), "onerror action's are only valid from the \"eosio\" system account");\
		}\
		if (code == self || action == N(onerror) || code == N(eosio.token)) {\
			TYPE thiscontract(self);\
			switch (action) {\
				EOSIO_API(TYPE, MEMBERS)\
			}\
		}\
	}\
}

crowdsale::crowdsale(account_name self) :
	eosio::contract(self),
	asset(
		eosio::asset(0, eosio::string_to_symbol(PRECISION, STR(SYMBOL))),
		eosio::string_to_name(STR(CONTRACT))
	),
	state_singleton(_self, _self)
{
	this->state = state_singleton.exists() ? state_singleton.get() : default_parameters();
}

crowdsale::~crowdsale() {
	this->state_singleton.set(this->state, _self);
}

void crowdsale::transfer(uint64_t sender, uint64_t receiver) {
	if (receiver != _self) {
		return;
	}
	eosio_assert(!this->state.finalized, "Crowdsale finished");
	transfer_t data = eosio::unpack_action_data<transfer_t>();
	this->asset.set_amount(data.quantity.amount * this->state.multiplier.num / this->state.multiplier.denom);
	eosio::currency::inline_transfer(
		this->_self,
		data.from,
		this->asset,
		"crowdsale"
	);
}

void crowdsale::finalize() {
	require_auth(_self);
	this->state.finalized = true;
}

// debug
void crowdsale::unfinalize() {
	require_auth(_self);
	this->state.finalized = false;
}

EOSIO_ABI(crowdsale, (finalize)(unfinalize)(transfer));

#include "crowdsale.hpp"

#undef EOSIO_ABI
#define EOSIO_ABI(TYPE, MEMBERS)\
extern "C" {\
	void apply(uint64_t receiver, uint64_t code, uint64_t action) {\
		auto self = receiver;\
		if (action == N(onerror)) {\
			eosio_assert(code == N(eosio), "onerror action's are only valid from the \"eosio\" system account");\
		}\
		if (code == self || action == N(onerror) || code == N(eosio.token) ) {\
			TYPE thiscontract(self);\
			switch (action) {\
				EOSIO_API(TYPE, MEMBERS)\
			}\
		}\
	}\
}

void crowdsale::regcrowdsale(account_name issuer, account_name token_contract, eosio::asset asset) {
	require_auth(issuer);
	crowdsale_index crowdsales(this->_self, token_contract);
	eosio_assert(crowdsales.find(asset.symbol.name()) == crowdsales.end(), "Crowdsale for this contract and symbol already exists");
	crowdsales.emplace(this->_self, [&](auto& crowdsale) {
		crowdsale.issuer = issuer;
		crowdsale.token_contract = token_contract;
		crowdsale.symbol = asset.symbol;
	});
}

void crowdsale::selcrowdsale(account_name user, account_name token_contract, eosio::asset asset) {
	require_auth(user);
	crowdsale_index crowdsales(this->_self, token_contract);
	eosio_assert(crowdsales.find(asset.symbol.name()) != crowdsales.end(), "User selected invalid crowdsale");
	user_choice_index user_choices(this->_self, this->_self);
	auto user_choice = user_choices.find(user);
	if (user_choice == user_choices.end()) {
		user_choices.emplace(user, [&](auto& choice) {
			choice.user = user;
			choice.token_contract = token_contract;
			choice.symbol = asset.symbol;
		});
	} else {
		user_choices.modify(user_choice, user, [&](auto& choice) {
			choice.user = user;
			choice.token_contract = token_contract;
			choice.symbol = asset.symbol;
		});
	}
}

void crowdsale::transfer(account_name sender, account_name receiver) {
	if (receiver != _self) {
		return;
	}
	user_choice_index user_choices(this->_self, this->_self);
	auto user_choice = user_choices.find(sender);
	eosio_assert(user_choice != user_choices.end(), "User did't choose crowdsale");
	crowdsale_index crowdsales(this->_self, user_choice->token_contract);
	auto crowdsale = crowdsales.find(user_choice->symbol);
	eosio::currency::inline_transfer(this->_self, sender, eosio::extended_asset(eosio::asset(1, crowdsale->symbol), crowdsale->token_contract), "airdrop");
}

EOSIO_ABI(crowdsale, (regcrowdsale)(selcrowdsale)(transfer));

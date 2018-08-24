#undef EOSIO_ABI
#define EOSIO_ABI(TYPE, MEMBERS)\
extern "C" {\
	void apply(uint64_t receiver, uint64_t code, uint64_t action) {\
		auto self = receiver;\
		if (action == N(onerror)) {\
			eosio_assert(code == N(eosio), "onerror action's are only valid from the \"eosio\" system account");\
		}\
		if (code == self || action == N(onerror) || code == N(eosio.token) || code == eosio::string_to_name(STR(CONTRACT))) {\
			TYPE thiscontract(self);\
			switch (action) {\
				EOSIO_API(TYPE, MEMBERS)\
			}\
		}\
	}\
}

void crowdsale::transfer(uint64_t sender, uint64_t receiver) {
	struct transfer_t {
		account_name from;
		account_name to;
		eosio::asset quantity;
		std::string memo;
	} data = eosio::unpack_action_data<transfer_t>();
	eosio_assert(data.quantity.amount > 0, "Transfer must be positive");
	eosio_assert(data.quantity.is_valid(), "Invalid token transfer");
	if (data.from == this->_self) {
		eosio_assert(this->state.inline_call, "Only inline transfer call");
		this->state.inline_call--;
	} else {
		eosio_assert(data.quantity.symbol == this->asset_eos.symbol, "Only EOS Deposits");
		this->on_deposit(data.from, data.quantity);
	}
}

void crowdsale::unlock(uint64_t sender, uint64_t receiver) {
	eosio_assert(this->state.inline_call, "Only inline unlock call");
	this->state.inline_call--;
}

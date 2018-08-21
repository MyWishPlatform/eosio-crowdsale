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

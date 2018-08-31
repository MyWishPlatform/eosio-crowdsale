import setup
import json
import eosf
from termcolor import cprint
import node
import unittest
import re
from decimal import Decimal
from math import ceil

setup.set_verbose(False)
setup.set_json(False)
setup.use_keosd(False)


class CrowdsaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = {}
        with open('config.h', 'r') as cfg_file:
            for line in cfg_file.readlines():
                match = re.search('#define (\w+) ([\w.]+)', line)
                if match:
                    cls.cfg[match.group(1)] = match.group(2)

        cls.issuer_acc_name = cls.cfg["ISSUER"]
        cls.symbol = cls.cfg["SYMBOL"]
        cls.decimals = int(cls.cfg["DECIMALS"])
        cls.whitelist = bool(cls.cfg["WHITELIST"] == "true")
        cls.transferable = bool(cls.cfg["TRANSFERABLE"] == "true")
        cls.rate = int(cls.cfg["RATE"]) / int(cls.cfg["RATE_DENOM"])
        cls.min_contrib_eos_cent = int(cls.cfg["MIN_CONTRIB"])
        cls.min_contrib_eos = cls.min_contrib_eos_cent / 10 ** 4
        cls.max_contrib_eos_cent = int(cls.cfg["MAX_CONTRIB"])
        cls.max_contrib_eos = cls.max_contrib_eos_cent / 10 ** 4
        cls.soft_cap_tkn_cent = int(cls.cfg["SOFT_CAP_TKN"])
        cls.soft_cap_tkn = cls.soft_cap_tkn_cent / 10 ** cls.decimals
        cls.soft_cap_eos_cent = int(cls.soft_cap_tkn / cls.rate * 10 ** 4)
        cls.soft_cap_eos = cls.soft_cap_eos_cent / 10 ** 4
        cls.hard_cap_tkn_cent = int(cls.cfg["HARD_CAP_TKN"])
        cls.hard_cap_tkn = cls.hard_cap_tkn_cent / 10 ** cls.decimals
        cls.hard_cap_eos_cent = ceil(cls.hard_cap_tkn / cls.rate * 10 ** 4)
        cls.hard_cap_eos = cls.hard_cap_eos_cent / 10 ** 4
        cls.start_date = 1534780454
        cls.finish_date = 1534781454
        cls.token_deployer_acc_name = cls.cfg["CONTRACT"]
        cls.mintcnt = int(cls.cfg["MINTCNT"])

    @classmethod
    def tearDownClass(cls):
        pass

    def run(self, result=None):
        """ Stop after first error """
        if not result.failures:
            super().run(result)

    def setUp(self):
        # start node
        assert (not node.reset().error)

        # create wallet
        eosf.set_verbosity([])  # disable logs
        self.wallet = eosf.Wallet()

        # create eosio account
        self.eosio_acc = eosf.AccountMaster()
        self.wallet.import_key(self.eosio_acc)
        eosf.set_verbosity()  # enable logs

        # create issuer account
        self.issuer_acc = eosf.account(self.eosio_acc, self.issuer_acc_name)
        self.wallet.import_key(self.issuer_acc)

        # create MINTDEST accounts
        for x in range(self.mintcnt):
            dest_acc_name = self.cfg["MINTDEST" + str(x)]
            if dest_acc_name not in eosf.account_map():
                dest = eosf.account(self.eosio_acc, dest_acc_name)
                self.wallet.import_key(dest)

        # create system token deployer account
        self.system_token_deployer_acc = eosf.account(self.eosio_acc, "eosio.token")
        self.wallet.import_key(self.system_token_deployer_acc)

        # create token deployer account
        if self.token_deployer_acc_name not in eosf.account_map():
            self.token_deployer_acc = eosf.account(self.eosio_acc, self.token_deployer_acc_name)
            self.wallet.import_key(self.token_deployer_acc)

        # create crowdsale deployer account
        self.crowdsale_deployer_acc = eosf.account(self.eosio_acc, "ico.deployer")
        self.wallet.import_key(self.crowdsale_deployer_acc)

        # deploy eosio.bios contract
        self.eosio_bios_contract = eosf.Contract(self.eosio_acc, "eosio.bios")
        assert (not self.eosio_bios_contract.error)
        deployment_bios = self.eosio_bios_contract.deploy()
        assert (not deployment_bios.error)

        # deploy system token contract
        self.system_token_contract = eosf.Contract(self.system_token_deployer_acc, "eosio.token")
        assert (not self.system_token_contract.error)
        deployment_system_token_contract = self.system_token_contract.deploy()
        assert (not deployment_system_token_contract.error)
        assert (not self.system_token_deployer_acc.code().error)

        # deploy custom eosio.token contract
        self.token_contract = eosf.Contract(
            self.token_deployer_acc,
            "eosio-crowdsale/eosiotoken/eosio.token",
            wast_file='eosio.token.wast',
            abi_file='eosio.token.abi'
        )
        assert (not self.token_contract.error)
        deployment_token = self.token_contract.deploy()
        assert (not deployment_token.error)
        assert (not self.token_deployer_acc.code().error)

        # create system eos asset
        assert (not self.system_token_contract.push_action(
            "create",
            json.dumps({
                "issuer": str(self.system_token_deployer_acc),
                "maximum_supply": self.toAsset(460000000000000, 4, 'EOS')
            }),
            self.system_token_deployer_acc
        ).error)

        # create custom token asset
        max_supply = self.hard_cap_tkn_cent
        for x in range(self.mintcnt):
            max_supply += int(self.cfg["MINTVAL" + str(x)])
        max_supply /= 10 ** self.decimals

        assert (not self.token_contract.push_action(
            "create",
            json.dumps({
                "issuer": str(self.crowdsale_deployer_acc),
                "maximum_supply": self.toAsset(max_supply, self.decimals, self.symbol),
                "lock": not self.transferable
            }),
            self.token_deployer_acc
        ).error)

        # deploy crowdsale contract
        self.crowdsale_contract = eosf.Contract(
            self.crowdsale_deployer_acc,
            "eosio-crowdsale/crowdsale",
            wast_file='crowdsale.wast',
            abi_file='crowdsale.debug.abi'
        )
        assert (not self.crowdsale_contract.error)
        deployment_crowdsale = self.crowdsale_contract.deploy()
        assert (not deployment_crowdsale.error)
        assert (not self.crowdsale_deployer_acc.code().error)

        # set eosio.code permission
        self.addEosioCodePermission(self.crowdsale_deployer_acc)

    def addEosioCodePermission(self, account):
        assert (not self.eosio_bios_contract.push_action(
            "updateauth",
            json.dumps({
                "account": str(account),
                "permission": "active",
                "parent": "owner",
                "auth": {
                    "threshold": 1,
                    "keys": [
                        {
                            "key": str(account.json["permissions"][1]["required_auth"]["keys"][0]["key"]),
                            "weight": 1
                        }
                    ],
                    "accounts": [
                        {
                            "permission": {
                                "actor": str(account),
                                "permission": "eosio.code"
                            },
                            "weight": 1
                        }
                    ],
                    "waits": []
                }
            }),
            account
        ).error)

    def toAsset(self, amount, decimals, symbol):
        amount = ceil(amount * 10 ** decimals) / 10 ** decimals
        return str(Decimal(amount).quantize(Decimal('1.' + '0' * int(decimals)))) + " " + symbol

    def fromAsset(self, asset):
        dictionary = {}
        split = asset.split(" ")
        dictionary["amount"] = float(split[0])
        dictionary["symbol"] = split[1]
        dictionary["decimals"] = len(split[0].split(".")[1])
        return dictionary

    def reach_cap(self, cap_tkn_cent, buyer_acc):
        contributed = 0
        eos_to_transfer = cap_tkn_cent / 10 ** self.decimals / self.rate
        if self.max_contrib_eos > 0:
            eos_to_transfer = self.max_contrib_eos
            times = int(cap_tkn_cent / 10 ** self.decimals / self.rate / eos_to_transfer)
            for x in range(times):
                assert (not self.system_token_contract.push_action(
                    "transfer",
                    json.dumps({
                        "from": str(buyer_acc),
                        "to": str(self.crowdsale_deployer_acc),
                        "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                        "memo": ""
                    }),
                    buyer_acc,
                    forceUnique=1
                ).error)
                contributed += eos_to_transfer

            remain_eos_to_cap = (cap_tkn_cent - contributed * self.rate * 10 ** self.decimals) \
                                / 10 ** self.decimals / self.rate
            if remain_eos_to_cap > 0:
                if remain_eos_to_cap > self.min_contrib_eos or self.min_contrib_eos == 0:
                    if int((contributed + eos_to_transfer) * self.rate * 10 ** self.decimals) > cap_tkn_cent:
                        remain_eos_to_cap -= 0.0001
                    assert (not self.system_token_contract.push_action(
                        "transfer",
                        json.dumps({
                            "from": str(buyer_acc),
                            "to": str(self.crowdsale_deployer_acc),
                            "quantity": self.toAsset(remain_eos_to_cap, 4, "EOS"),
                            "memo": ""
                        }),
                        buyer_acc
                    ).error)
                    contributed += eos_to_transfer
        else:
            will_be = int(int((contributed + eos_to_transfer) * 10 ** 4) / 10 ** 4 * self.rate * 10 ** self.decimals)
            if will_be > cap_tkn_cent:
                eos_to_transfer -= 0.0001
            assert (not self.system_token_contract.push_action(
                "transfer",
                json.dumps({
                    "from": str(buyer_acc),
                    "to": str(self.crowdsale_deployer_acc),
                    "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                    "memo": ""
                }),
                buyer_acc
            ).error)
            contributed += eos_to_transfer

    def tearDown(self):
        node.stop()

    def test_01(self):
        cprint(".1. Check premint", 'green')

        # check that destination accounts has no tokens before initialize
        for x in range(self.mintcnt):
            assert (len(self.token_contract.table("accounts", self.cfg["MINTDEST" + str(x)]).json["rows"]) == 0)

        # execute 'init'
        assert (not self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc
        ).error)

        # check that destination addresses received their tokens after 'init'
        for x in range(self.mintcnt):
            expected_value = int(self.cfg["MINTVAL" + str(x)]) / 10 ** self.decimals
            real_value_with_symbol = self.token_contract \
                .table("accounts", self.cfg["MINTDEST" + str(x)]) \
                .json["rows"][0]["balance"]
            real_value = float(real_value_with_symbol[:-(len(self.symbol) + 1)])
            assert (expected_value == real_value)

        # check that you cannot execute 'init' second time
        assert (self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc,
            forceUnique=1,
        ).error)

    def test_02(self):
        cprint("2. Check buy tokens", 'green')

        # check that destination accounts has no tokens before initialize
        for x in range(self.mintcnt):
            assert (len(self.token_contract.table("accounts", self.cfg["MINTDEST" + str(x)]).json["rows"]) == 0)

        # execute 'init'
        assert (not self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc
        ).error)

        # rewind time to start
        assert (not self.crowdsale_contract.push_action(
            "settime",
            json.dumps({
                "time": self.start_date
            }),
            self.crowdsale_deployer_acc
        ).error)

        # create account for buyer
        buyer_acc = eosf.account(self.eosio_acc, "buyer")
        self.wallet.import_key(buyer_acc)

        # calculate how much EOS to send
        eos_to_transfer = self.soft_cap_eos
        if eos_to_transfer < self.min_contrib_eos:
            eos_to_transfer = self.min_contrib_eos
        elif eos_to_transfer > self.max_contrib_eos != 0:
            eos_to_transfer = self.max_contrib_eos

        # issue tokens to buyer
        eos_to_issue = eos_to_transfer + 50
        assert (not self.system_token_contract.push_action(
            "issue",
            json.dumps({
                "to": str(buyer_acc),
                "quantity": self.toAsset(eos_to_issue, 4, "EOS"),
                "memo": ""
            }),
            self.system_token_deployer_acc
        ).error)
        assert (eos_to_issue == self.fromAsset(self.system_token_contract.table("accounts", buyer_acc)
                                               .json["rows"][0]["balance"])["amount"])

        if self.whitelist:
            # check that not whitelisted user cannot send EOS to contract
            assert (self.system_token_contract.push_action(
                "transfer",
                json.dumps({
                    "from": str(buyer_acc),
                    "to": str(self.crowdsale_deployer_acc),
                    "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                    "memo": ""
                }),
                buyer_acc
            ).error)

            # whitelist account if needed
            assert (not self.crowdsale_contract.push_action(
                "white",
                json.dumps({
                    "account": str(buyer_acc)
                }),
                self.issuer_acc
            ).error)

        # transfer EOS to crowdsale contract
        assert (not self.system_token_contract.push_action(
            "transfer",
            json.dumps({
                "from": str(buyer_acc),
                "to": str(self.crowdsale_deployer_acc),
                "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                "memo": ""
            }),
            buyer_acc
        ).error)

        # check EOS balances
        assert (eos_to_transfer == self.fromAsset(self.system_token_contract
                                                  .table("accounts", self.crowdsale_deployer_acc)
                                                  .json["rows"][0]["balance"])["amount"])
        assert ((eos_to_issue - eos_to_transfer) == self.fromAsset(self.system_token_contract
                                                                   .table("accounts", buyer_acc)
                                                                   .json["rows"][0]["balance"])["amount"])

        # check state in crowdsale
        deposit = self.crowdsale_contract.table("deposit", self.crowdsale_deployer_acc).json["rows"][0]
        expected_tokens = int(eos_to_transfer * self.rate * 10 ** self.decimals)

        assert (deposit["account"] == buyer_acc.name)
        assert (int(deposit["eoses"]) == int(eos_to_transfer * 10 ** 4))
        assert (int(deposit["tokens"]) == expected_tokens)
        if self.whitelist:
            assert (buyer_acc.name == self.crowdsale_contract.table("whitelist", self.crowdsale_deployer_acc)
                    .json["rows"][0]["account"])

        assert (expected_tokens == int(self.crowdsale_contract
                .table("state", self.crowdsale_deployer_acc).json["rows"][0]["total_tokens"]))

        # check token balance
        assert (expected_tokens == int(self.fromAsset(self.token_contract.table("accounts", buyer_acc)
                                                      .json["rows"][0]["balance"])["amount"] * 10 ** self.decimals))

    def test_03(self):
        cprint("3. Check buy from several accounts", "green")

        # execute 'init'
        assert (not self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc
        ).error)

        # rewind time to start
        assert (not self.crowdsale_contract.push_action(
            "settime",
            json.dumps({
                "time": self.start_date
            }),
            self.crowdsale_deployer_acc
        ).error)

        # create accounts for buyers
        buyers_accs = []
        for x in range(4):
            buyers_accs.append(eosf.account(self.eosio_acc, "buyer" + str(x + 1)))
            self.wallet.import_key(buyers_accs[x])

        # calculate how much EOS to send
        eos_to_transfer = self.soft_cap_eos
        if eos_to_transfer < self.min_contrib_eos:
            eos_to_transfer = self.min_contrib_eos
        elif eos_to_transfer > self.max_contrib_eos != 0:
            eos_to_transfer = self.max_contrib_eos

        # issue tokens to buyers
        eos_to_issue = eos_to_transfer + 1
        for buyer in buyers_accs:
            assert (not self.system_token_contract.push_action(
                "issue",
                json.dumps({
                    "to": str(buyer),
                    "quantity": self.toAsset(eos_to_issue, 4, "EOS"),
                    "memo": ""
                }),
                self.system_token_deployer_acc
            ).error)

            assert (eos_to_issue == self.fromAsset(self.system_token_contract.table("accounts", buyer)
                                                   .json["rows"][0]["balance"])["amount"])

        # whitelist accounts if needed
        if self.whitelist:
            for buyer in buyers_accs:
                assert (not self.crowdsale_contract.push_action(
                    "white",
                    json.dumps({
                        "account": str(buyer)
                    }),
                    self.issuer_acc
                ).error)

        # calculate how much tokens each buyer will receive
        expected_tokens_per_buyer = int(eos_to_transfer * self.rate * 10 ** self.decimals)
        expected_all_tokens = 0
        expected_all_eos = 0

        # transfer EOS to crowdsale contract
        for buyer in buyers_accs:
            if (expected_all_tokens + expected_tokens_per_buyer) <= self.hard_cap_tkn_cent:
                assert (not self.system_token_contract.push_action(
                    "transfer",
                    json.dumps({
                        "from": str(buyer),
                        "to": str(self.crowdsale_deployer_acc),
                        "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                        "memo": ""
                    }),
                    buyer
                ).error)
                expected_all_eos += eos_to_transfer
                expected_all_tokens += expected_tokens_per_buyer

                # check EOS balances
                assert (int(expected_all_eos * 10 ** 4) == int(self.fromAsset(self.system_token_contract
                                                                              .table("accounts",
                                                                                     self.crowdsale_deployer_acc)
                                                                              .json["rows"][0]["balance"])[
                                                                   "amount"] * 10 ** 4))
                assert ((eos_to_issue - eos_to_transfer) == self.fromAsset(self.system_token_contract
                                                                           .table("accounts", buyer)
                                                                           .json["rows"][0]["balance"])["amount"])

                # check token balances
                assert (expected_tokens_per_buyer == int(self.fromAsset(self.token_contract
                                                                        .table("accounts", buyer)
                                                                        .json["rows"][0]["balance"])
                                                         ["amount"] * 10 ** self.decimals))
                assert (expected_all_tokens == int(self.crowdsale_contract
                        .table("state", self.crowdsale_deployer_acc)
                        .json["rows"][0]["total_tokens"]))
            else:
                break

    def test_04(self):
        cprint("4. Check white & unwhite", 'green')

        if self.whitelist:
            # execute 'init'
            assert (not self.crowdsale_contract.push_action(
                "init",
                json.dumps({
                    "start": self.start_date,
                    "finish": self.finish_date
                }),
                self.crowdsale_deployer_acc
            ).error)

            # rewind time to start
            assert (not self.crowdsale_contract.push_action(
                "settime",
                json.dumps({
                    "time": self.start_date
                }),
                self.crowdsale_deployer_acc
            ).error)

            # create accounts
            buyers_accs = []
            for x in range(4):
                buyers_accs.append(eosf.account(self.eosio_acc, "buyer" + str(x + 1)))
                self.wallet.import_key(buyers_accs[x])

            # whitelist all buyers
            for buyer in buyers_accs:
                assert (not self.crowdsale_contract.push_action(
                    "white",
                    json.dumps({
                        "account": str(buyer)
                    }),
                    self.issuer_acc
                ).error)

            # check that all buyers successfully whitelisted
            buyers_names = list(map(lambda buyer: buyer.name, buyers_accs))
            whitelisted_names = list(map(lambda row: row["account"], self.crowdsale_contract
                                         .table("whitelist", self.crowdsale_deployer_acc).json["rows"]))
            assert (buyers_names == whitelisted_names)

            # unwhite all buyers
            for buyer in buyers_accs:
                assert (not self.crowdsale_contract.push_action(
                    "unwhite",
                    json.dumps({
                        "account": str(buyer)
                    }),
                    self.issuer_acc
                ).error)
            assert (len(self.crowdsale_contract.table("whitelist", self.crowdsale_deployer_acc).json["rows"]) == 0)

            # calculate how much EOS to send
            eos_to_transfer = self.soft_cap_eos
            if eos_to_transfer < self.min_contrib_eos:
                eos_to_transfer = self.min_contrib_eos
            elif eos_to_transfer > self.max_contrib_eos != 0:
                eos_to_transfer = self.max_contrib_eos

            # issue tokens to buyers
            eos_to_issue = eos_to_transfer + 1
            for buyer in buyers_accs:
                assert (not self.system_token_contract.push_action(
                    "issue",
                    json.dumps({
                        "to": str(buyer),
                        "quantity": self.toAsset(eos_to_issue, 4, "EOS"),
                        "memo": ""
                    }),
                    self.system_token_deployer_acc
                ).error)

            # check that unwhited users cannot send EOS to crowdsale
            for buyer in buyers_accs:
                assert (self.system_token_contract.push_action(
                    "transfer",
                    json.dumps({
                        "from": str(buyer),
                        "to": str(self.crowdsale_deployer_acc),
                        "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                        "memo": ""
                    }),
                    buyer
                ).error)

    def test_05(self):
        cprint("5. Check whitemany & unwhitemany", 'green')

        if self.whitelist:
            # execute 'init'
            assert (not self.crowdsale_contract.push_action(
                "init",
                json.dumps({
                    "start": self.start_date,
                    "finish": self.finish_date
                }),
                self.crowdsale_deployer_acc
            ).error)

            # rewind time to start
            assert (not self.crowdsale_contract.push_action(
                "settime",
                json.dumps({
                    "time": self.start_date
                }),
                self.crowdsale_deployer_acc
            ).error)

            # create accounts
            buyers_accs = []
            for x in range(4):
                buyers_accs.append(eosf.account(self.eosio_acc, "buyer" + str(x + 1)))
                self.wallet.import_key(buyers_accs[x])

            # whitelist all buyers
            assert (not self.crowdsale_contract.push_action(
                "whitemany",
                json.dumps({
                    "accounts": list(map(lambda buyer: buyer.name, buyers_accs))
                }),
                self.issuer_acc
            ).error)

            # check that all buyers successfully whitelisted
            buyers_names = list(map(lambda buyer: buyer.name, buyers_accs))
            whitelisted_names = list(map(lambda row: row["account"], self.crowdsale_contract
                                         .table("whitelist", self.crowdsale_deployer_acc).json["rows"]))
            assert (buyers_names == whitelisted_names)

            # unwhite all buyers
            assert (not self.crowdsale_contract.push_action(
                "unwhitemany",
                json.dumps({
                    "accounts": list(map(lambda buyer: buyer.name, buyers_accs))
                }),
                self.issuer_acc
            ).error)
            assert (len(self.crowdsale_contract.table("whitelist", self.crowdsale_deployer_acc).json["rows"]) == 0)

            # calculate how much EOS to send
            eos_to_transfer = self.soft_cap_eos
            if eos_to_transfer < self.min_contrib_eos:
                eos_to_transfer = self.min_contrib_eos
            elif eos_to_transfer > self.max_contrib_eos != 0:
                eos_to_transfer = self.max_contrib_eos

            # issue tokens to buyers
            eos_to_issue = eos_to_transfer + 1
            for buyer in buyers_accs:
                assert (not self.system_token_contract.push_action(
                    "issue",
                    json.dumps({
                        "to": str(buyer),
                        "quantity": self.toAsset(eos_to_issue, 4, "EOS"),
                        "memo": ""
                    }),
                    self.system_token_deployer_acc
                ).error)

            # check that unwhited users cannot send EOS to crowdsale
            for buyer in buyers_accs:
                assert (self.system_token_contract.push_action(
                    "transfer",
                    json.dumps({
                        "from": str(buyer),
                        "to": str(self.crowdsale_deployer_acc),
                        "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                        "memo": ""
                    }),
                    buyer
                ).error)

    def test_06(self):
        cprint("6. Check min and max restrictions", 'green')

        # execute 'init'
        assert (not self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc
        ).error)

        # rewind time to start
        assert (not self.crowdsale_contract.push_action(
            "settime",
            json.dumps({
                "time": self.start_date
            }),
            self.crowdsale_deployer_acc
        ).error)

        # create account for buyer
        buyer_acc = eosf.account(self.eosio_acc, "buyer")
        self.wallet.import_key(buyer_acc)

        if self.min_contrib_eos_cent != 0 and self.min_contrib_eos_cent > 1 \
                or self.max_contrib_eos_cent != 0 and self.max_contrib_eos_cent < self.hard_cap_eos_cent:
            if self.whitelist:
                # whitelist account if needed
                assert (not self.crowdsale_contract.push_action(
                    "white",
                    json.dumps({
                        "account": str(buyer_acc)
                    }),
                    self.issuer_acc
                ).error)

            def issueAndTransfer(eos_to_transfer):
                # issue tokens to buyer
                assert (not self.system_token_contract.push_action(
                    "issue",
                    json.dumps({
                        "to": str(buyer_acc),
                        "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                        "memo": ""
                    }),
                    self.system_token_deployer_acc
                ).error)

                # transfer EOS to crowdsale contract
                assert (self.system_token_contract.push_action(
                    "transfer",
                    json.dumps({
                        "from": str(buyer_acc),
                        "to": str(self.crowdsale_deployer_acc),
                        "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                        "memo": ""
                    }),
                    buyer_acc
                ).error)

            # check that cannot send less than min
            if self.min_contrib_eos_cent != 0 and self.min_contrib_eos_cent > 1:
                issueAndTransfer(self.min_contrib_eos / 2)

            # check that cannot send more than max
            if self.max_contrib_eos_cent != 0 and self.max_contrib_eos_cent < self.hard_cap_eos_cent:
                issueAndTransfer(self.max_contrib_eos + 0.0001)

    def test_07(self):
        cprint("7. Check cannot buy before start and after finish", 'green')

        # execute 'init'
        assert (not self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc
        ).error)

        # create account for buyer
        buyer_acc = eosf.account(self.eosio_acc, "buyer")
        self.wallet.import_key(buyer_acc)

        # whitelist account if needed
        if self.whitelist:
            assert (not self.crowdsale_contract.push_action(
                "white",
                json.dumps({
                    "account": str(buyer_acc)
                }),
                self.issuer_acc
            ).error)

        # calculate how much EOS to send
        eos_to_transfer = self.soft_cap_eos
        if eos_to_transfer < self.min_contrib_eos:
            eos_to_transfer = self.min_contrib_eos
        elif eos_to_transfer > self.max_contrib_eos != 0:
            eos_to_transfer = self.max_contrib_eos

        # issue tokens to buyer
        eos_to_issue = eos_to_transfer + 50
        assert (not self.system_token_contract.push_action(
            "issue",
            json.dumps({
                "to": str(buyer_acc),
                "quantity": self.toAsset(eos_to_issue, 4, "EOS"),
                "memo": ""
            }),
            self.system_token_deployer_acc
        ).error)
        assert (eos_to_issue == self.fromAsset(self.system_token_contract.table("accounts", buyer_acc)
                                               .json["rows"][0]["balance"])["amount"])

        # function setting time and sending EOS
        def set_time_and_transfer(timestamp):
            assert (not self.crowdsale_contract.push_action(
                "settime",
                json.dumps({
                    "time": timestamp
                }),
                self.crowdsale_deployer_acc
            ).error)

            # transfer EOS to crowdsale contract
            assert (self.system_token_contract.push_action(
                "transfer",
                json.dumps({
                    "from": str(buyer_acc),
                    "to": str(self.crowdsale_deployer_acc),
                    "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                    "memo": ""
                }),
                buyer_acc
            ).error)

        # check that you cannot send EOS before CS start
        set_time_and_transfer(self.start_date - 10)

        # check that you cannot send EOS after CS end
        set_time_and_transfer(self.finish_date + 10)

    def test_08(self):
        cprint("8. Check finalization after reaching hard cap", 'green')

        # execute 'init'
        assert (not self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc
        ).error)

        # rewind time to start
        assert (not self.crowdsale_contract.push_action(
            "settime",
            json.dumps({
                "time": self.start_date
            }),
            self.crowdsale_deployer_acc
        ).error)

        # create account for buyer
        buyer_acc = eosf.account(self.eosio_acc, "buyer")
        self.wallet.import_key(buyer_acc)

        # issue tokens to buyer
        assert (not self.system_token_contract.push_action(
            "issue",
            json.dumps({
                "to": str(buyer_acc),
                "quantity": self.toAsset(self.hard_cap_eos, 4, "EOS"),
                "memo": ""
            }),
            self.system_token_deployer_acc
        ).error)

        # whitelist account if needed
        if self.whitelist:
            assert (not self.crowdsale_contract.push_action(
                "white",
                json.dumps({
                    "account": str(buyer_acc)
                }),
                self.issuer_acc
            ).error)

        # reach hard cap
        self.reach_cap(self.hard_cap_tkn_cent, buyer_acc)

        # finalize and withdraw EOS
        eos_at_crowdsale = self.system_token_contract.table("accounts", self.crowdsale_deployer_acc).json["rows"][0]
        if not self.transferable:
            assert (not self.crowdsale_contract.push_action(
                "finalize",
                json.dumps({}),
                self.issuer_acc
            ).error)

        assert (not self.crowdsale_contract.push_action(
            "withdraw",
            json.dumps({}),
            self.issuer_acc
        ).error)

        # check balance afer withdraw
        eos_at_issuer_acc = self.system_token_contract.table("accounts", self.issuer_acc).json["rows"][0]
        assert (eos_at_crowdsale == eos_at_issuer_acc)

    def test_09(self):
        cprint('9. Check refund from multiple accounts', 'green')

        if self.soft_cap_eos > 0:
            # execute 'init'
            assert (not self.crowdsale_contract.push_action(
                "init",
                json.dumps({
                    "start": self.start_date,
                    "finish": self.finish_date
                }),
                self.crowdsale_deployer_acc
            ).error)

            # rewind time to start
            assert (not self.crowdsale_contract.push_action(
                "settime",
                json.dumps({
                    "time": self.start_date
                }),
                self.crowdsale_deployer_acc
            ).error)

            buyers_accs = []
            for x in range(2):
                # create account for buyers
                buyers_accs.append(eosf.account(self.eosio_acc, "buyer" + str(x + 1)))
                self.wallet.import_key(buyers_accs[x])

                # issue tokens to buyers
                assert (not self.system_token_contract.push_action(
                    "issue",
                    json.dumps({
                        "to": str(buyers_accs[x]),
                        "quantity": self.toAsset(self.soft_cap_eos, 4, "EOS"),
                        "memo": ""
                    }),
                    self.system_token_deployer_acc
                ).error)

                # whitelist account if needed
                if self.whitelist:
                    assert (not self.crowdsale_contract.push_action(
                        "white",
                        json.dumps({
                            "account": str(buyers_accs[x])
                        }),
                        self.issuer_acc
                    ).error)

            for buyer in buyers_accs:
                # reach quarter of soft cap
                self.reach_cap(self.soft_cap_tkn_cent / 4, buyer)

            # rewind time to finish
            assert (not self.crowdsale_contract.push_action(
                "settime",
                json.dumps({
                    "time": self.finish_date + 1
                })
            ).error)

            # refund
            for buyer in buyers_accs:
                assert (not self.crowdsale_contract.push_action(
                    "refund",
                    json.dumps({
                        "investor": str(buyer)
                    }),
                    buyer
                ).error)

                assert (self.toAsset(self.soft_cap_eos, 4, "EOS") == self.system_token_contract
                        .table("accounts", buyer).json["rows"][0]["balance"])

    def test_10(self):
        cprint('10. Cannot refund after reaching hard cap', 'green')

        if self.soft_cap_eos + self.min_contrib_eos <= self.hard_cap_eos:
            # execute 'init'
            assert (not self.crowdsale_contract.push_action(
                "init",
                json.dumps({
                    "start": self.start_date,
                    "finish": self.finish_date
                }),
                self.crowdsale_deployer_acc
            ).error)

            # rewind time to start
            assert (not self.crowdsale_contract.push_action(
                "settime",
                json.dumps({
                    "time": self.start_date
                }),
                self.crowdsale_deployer_acc
            ).error)

            # create account for buyer
            buyer_acc = eosf.account(self.eosio_acc, "buyer")
            self.wallet.import_key(buyer_acc)

            # issue tokens to buyer
            assert (not self.system_token_contract.push_action(
                "issue",
                json.dumps({
                    "to": str(buyer_acc),
                    "quantity": self.toAsset(self.hard_cap_eos, 4, "EOS"),
                    "memo": ""
                }),
                self.system_token_deployer_acc
            ).error)

            # whitelist account if needed
            if self.whitelist:
                assert (not self.crowdsale_contract.push_action(
                    "white",
                    json.dumps({
                        "account": str(buyer_acc)
                    }),
                    self.issuer_acc
                ).error)

            # reach soft cap
            self.reach_cap((self.hard_cap_tkn_cent + self.soft_cap_tkn_cent) / 2, buyer_acc)

            # rewind time to finish
            assert (not self.crowdsale_contract.push_action(
                "settime",
                json.dumps({
                    "time": self.finish_date + 1
                }),
                self.crowdsale_deployer_acc
            ).error)

            assert (self.crowdsale_contract.push_action(
                "refund",
                json.dumps({
                    "investor": str(buyer_acc)
                }),
                buyer_acc
            ).error)

    def test_11(self):
        cprint('11. Check changing finish date', 'green')

        # execute 'init'
        assert (not self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc
        ).error)

        # rewind time to start
        assert (not self.crowdsale_contract.push_action(
            "settime",
            json.dumps({
                "time": self.start_date
            }),
            self.crowdsale_deployer_acc
        ).error)

        # change finish date
        assert (not self.crowdsale_contract.push_action(
            "setfinish",
            json.dumps({
                "finish": self.finish_date + 10
            }),
            self.issuer_acc
        ).error)
        assert (self.finish_date + 10 == self.crowdsale_contract
                .table("state", self.crowdsale_deployer_acc).json["rows"][0]["finish"])

        # change finish date back
        assert (not self.crowdsale_contract.push_action(
            "setfinish",
            json.dumps({
                "finish": self.finish_date
            }),
            self.issuer_acc
        ).error)
        assert (self.finish_date == self.crowdsale_contract
                .table("state", self.crowdsale_deployer_acc).json["rows"][0]["finish"])

        # try to change finish date after CS finished
        assert (not self.crowdsale_contract.push_action(
            "settime",
            json.dumps({
                "time": self.finish_date + 1
            })
        ).error)
        assert (self.crowdsale_contract.push_action(
            "setfinish",
            json.dumps({
                "finish": self.finish_date
            }),
            self.issuer_acc,
            forceUnique=1
        ).error)

    def test_12(self):
        cprint('12. Check changing start date', 'green')

        # execute 'init'
        assert (not self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc
        ).error)

        # rewind time to before start
        assert (not self.crowdsale_contract.push_action(
            "settime",
            json.dumps({
                "time": self.start_date - 10
            })
        ).error)

        assert (not self.crowdsale_contract.push_action(
            "setstart",
            json.dumps({
                "start": self.start_date + 10
            }),
            self.issuer_acc
        ).error)

        assert (self.start_date + 10 == self.crowdsale_contract
                .table("state", self.crowdsale_deployer_acc).json["rows"][0]["start"])

        # change finish date back
        assert (not self.crowdsale_contract.push_action(
            "setstart",
            json.dumps({
                "start": self.start_date
            }),
            self.issuer_acc
        ).error)
        assert (self.start_date == self.crowdsale_contract
                .table("state", self.crowdsale_deployer_acc).json["rows"][0]["start"])

        # try to change finish date after CS finished
        assert (not self.crowdsale_contract.push_action(
            "settime",
            json.dumps({
                "time": self.start_date + 1
            })
        ).error)
        assert (self.crowdsale_contract.push_action(
            "setstart",
            json.dumps({
                "start": self.start_date
            }),
            self.issuer_acc,
            forceUnique=1
        ).error)


if __name__ == "__main__":
    unittest.main()

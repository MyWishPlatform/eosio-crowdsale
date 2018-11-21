import json
from eosfactory.eosf import *
from termcolor import cprint
#import node
import unittest
import re
from decimal import Decimal
from math import ceil
import argparse
import warnings


class CrowdsaleTests(unittest.TestCase):


    def ignore_warnings(test_func):
        def do_test(self, *args, **kwargs):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", ResourceWarning)
                test_func(self, *args, **kwargs)
        return do_test

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

    @ignore_warnings
    def setUp(self):
        empty_hash = "code hash: 0000000000000000000000000000000000000000000000000000000000000000"
        # start node
        reset()

        # create wallet
        create_wallet()

        # create eosio account
        create_master_account("master")
        self.eosio_acc = master
        # create issuer account
        create_account("issuer_acc", master, self.issuer_acc_name)
        self.issuer_acc = issuer_acc

        # create MINTDEST accounts
        for x in range(self.mintcnt):
            dest_acc_name = self.cfg["MINTDEST" + str(x)]
            if dest_acc_name not in manager.account_map():
                dest = create_account("mintdest_acc{}".format(x), master, dest_acc_name)
                #self.wallet.import_key(dest)

        # create system token deployer account
        create_account("eosio_token", self.eosio_acc, "eosio.token")
        self.system_token_deployer_acc = eosio_token


        # create token deployer account
        create_account("token_deployer_acc", self.eosio_acc, self.token_deployer_acc_name)
        self.token_deployer_acc = token_deployer_acc

        # create crowdsale deployer account
        create_account("crowdsale_deployer", self.eosio_acc, "ico.deployer")
        self.crowdsale_deployer_acc = crowdsale_deployer


        # # deploy eosio.bios contract
        # self.eosio_bios_contract = eosf.Contract(self.eosio_acc, "eosio.bios")
        # assert (not self.eosio_bios_contract.error)
        # deployment_bios = self.eosio_bios_contract.deploy()
        # assert (not deployment_bios.error)

        # deploy system token contract
        self.system_token_contract = Contract(
            self.system_token_deployer_acc,
            "eosio.token",
            abi_file="eosio.token.abi",
            wasm_file="eosio.token.wasm"
        )
        #self.system_token_contract.build()
        self.system_token_contract.deploy()
        #deployment_system_token_contract = self.system_token_contract.deploy()


        # deploy custom eosio.token contract
        self.token_contract = Contract(
            self.token_deployer_acc,
            "eosio-crowdsale/eosiotoken/eosio.token",
            abi_file='eosio.token.abi',
            wasm_file='eosio.token.wasm'
        )

        deployment_token = self.token_contract.deploy()

        # create system eos asset
        self.system_token_contract.push_action(
            "create",
            json.dumps({
                "issuer": str(self.system_token_deployer_acc),
                "maximum_supply": self.toAsset(460000000000000, 4, 'EOS')
            }),
            self.system_token_deployer_acc
        )

        # create custom token asset
        max_supply = self.hard_cap_tkn_cent
        for x in range(self.mintcnt):
            max_supply += int(self.cfg["MINTVAL" + str(x)])
        max_supply /= 10 ** self.decimals

        self.token_contract.push_action(
            "create",
            json.dumps({
                "issuer": str(self.crowdsale_deployer_acc),
                "maximum_supply": self.toAsset(max_supply, self.decimals, self.symbol),
                "lock": not self.transferable
            }),
            self.token_deployer_acc
        )

        # deploy crowdsale contract
        self.crowdsale_contract = Contract(
            self.crowdsale_deployer_acc,
            "eosio-crowdsale/crowdsale",
            abi_file='crowdsale.debug.abi',
            wasm_file='crowdsale.wasm'
        )

        deployment_crowdsale = self.crowdsale_contract.deploy()

        # set eosio.code permission
        self.addEosioCodePermission(self.crowdsale_deployer_acc)

    def addEosioCodePermission(self, account):
        self.eosio_acc.push_action(
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
        )

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
        #print(cap_tkn_cent)
        eos_to_transfer = cap_tkn_cent / 10 ** self.decimals / self.rate
        if self.max_contrib_eos > 0:
            eos_to_transfer = self.max_contrib_eos
            times = int(cap_tkn_cent / 10 ** self.decimals / self.rate / eos_to_transfer)

            #print(eos_to_transfer)
            #print(times)
            for x in range(times):
                self.system_token_contract.push_action(
                    "transfer",
                    json.dumps({
                        "from": str(buyer_acc),
                        "to": str(self.crowdsale_deployer_acc),
                        "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                        "memo": ""
                    }),
                    buyer_acc,
                    forceUnique=1
                )
                contributed += eos_to_transfer

            remain_eos_to_cap = (cap_tkn_cent - contributed * self.rate * 10 ** self.decimals) \
                                / 10 ** self.decimals / self.rate
            if remain_eos_to_cap > 0:
                if remain_eos_to_cap > self.min_contrib_eos or self.min_contrib_eos == 0:
                    if int((contributed + eos_to_transfer) * self.rate * 10 ** self.decimals) > cap_tkn_cent:
                        remain_eos_to_cap -= 0.0001
                    self.system_token_contract.push_action(
                        "transfer",
                        json.dumps({
                            "from": str(buyer_acc),
                            "to": str(self.crowdsale_deployer_acc),
                            "quantity": self.toAsset(remain_eos_to_cap, 4, "EOS"),
                            "memo": ""
                        }),
                        buyer_acc
                    )
                    contributed += eos_to_transfer
        else:
            will_be = int(int((contributed + eos_to_transfer) * 10 ** 4) / 10 ** 4 * self.rate * 10 ** self.decimals)
            if will_be > cap_tkn_cent:
                eos_to_transfer -= 0.0001
            self.system_token_contract.push_action(
                "transfer",
                json.dumps({
                    "from": str(buyer_acc),
                    "to": str(self.crowdsale_deployer_acc),
                    "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                    "memo": ""
                }),
                buyer_acc
            )
            contributed += eos_to_transfer

    def create_buyers_accounts(self, owner, amount):
        buyers_accs = []
        for x in range(amount):
            buyer_name = "tokenbuyer1{}".format(x+1)
            create_account(buyer_name, owner, buyer_name)
            buyers_accs.append(buyer_name)
        return buyers_accs

    def tearDown(self):
        stop()

    def test_01(self):
        cprint(".1. Check premint", 'green')

        # check that destination accounts has no tokens before initialize
        for x in range(self.mintcnt):
            assert (len(self.token_contract.table("accounts", self.cfg["MINTDEST" + str(x)]).json["rows"]) == 0)

        # execute 'init'
        self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc
        )

        # check that destination addresses received their tokens after 'init'
        for x in range(self.mintcnt):
            expected_value = int(self.cfg["MINTVAL" + str(x)]) / 10 ** self.decimals
            real_value_with_symbol = self.token_contract \
                .table("accounts", self.cfg["MINTDEST" + str(x)]) \
                .json["rows"][0]["balance"]
            real_value = float(real_value_with_symbol[:-(len(self.symbol) + 1)])
            assert (expected_value == real_value)

        # check that you cannot execute 'init' second time
        with self.assertRaises(errors.Error):
            self.crowdsale_contract.push_action(
                "init",
                json.dumps({
                    "start": self.start_date,
                    "finish": self.finish_date
                   }),
                self.crowdsale_deployer_acc,
                forceUnique=1,
               )

    def test_02(self):
        cprint("2. Check buy tokens", 'green')

        # check that destination accounts has no tokens before initialize
        for x in range(self.mintcnt):
            assert (len(self.token_contract.table("accounts", self.cfg["MINTDEST" + str(x)]).json["rows"]) == 0)

        # execute 'init'
        self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc
        )

        # rewind time to start
        self.crowdsale_contract.push_action(
            "settime",
            json.dumps({
                "time": self.start_date
            }),
            self.crowdsale_deployer_acc
        )

        # create account for buyer
        create_account("buyer_acc", self.eosio_acc)

        # calculate how much EOS to send
        eos_to_transfer = self.soft_cap_eos
        if eos_to_transfer < self.min_contrib_eos:
            eos_to_transfer = self.min_contrib_eos
        elif eos_to_transfer > self.max_contrib_eos != 0:
            eos_to_transfer = self.max_contrib_eos

        # issue tokens to buyer
        eos_to_issue = eos_to_transfer + 50
        self.system_token_contract.push_action(
            "issue",
            json.dumps({
                "to": buyer_acc.name,
                "quantity": self.toAsset(eos_to_issue, 4, "EOS"),
                "memo": ""
            }),
            self.system_token_deployer_acc
        )
        #print(self.system_token_contract.table("accounts", buyer_acc))
        assert (eos_to_issue == self.fromAsset(self.system_token_contract.table("accounts", buyer_acc)
                                               .json["rows"][0]["balance"])["amount"])

        if self.whitelist:
            # check that not whitelisted user cannot send EOS to contract
            with self.assertRaises(errors.Error):
                self.system_token_contract.push_action(
                    "transfer",
                    json.dumps({
                        "from": buyer_acc.name,
                        "to": str(self.crowdsale_deployer_acc),
                        "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                        "memo": ""
                    }),
                    buyer_acc

                )

            # whitelist account if needed
            self.crowdsale_contract.push_action(
                "white",
                json.dumps({
                    "account": buyer_acc.name
                }),
                self.issuer_acc
            )

        # transfer EOS to crowdsale contract
        self.system_token_contract.push_action(
            "transfer",
            json.dumps({
                "from": buyer_acc.name,
                "to": str(self.crowdsale_deployer_acc),
                "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                "memo": ""
            }),
            buyer_acc
        )

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
        assert (expected_tokens == int(self.fromAsset(self.token_contract.table("accounts", buyer_acc.name)
                                                      .json["rows"][0]["balance"])["amount"] * 10 ** self.decimals))


    def test_03(self):
        cprint("3. Check buy from several accounts", "green")

        # execute 'init'
        self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc
        )

        # rewind time to start
        self.crowdsale_contract.push_action(
            "settime",
            json.dumps({
                "time": self.start_date
            }),
            self.crowdsale_deployer_acc
        )

        # # create accounts for buyers
        # buyers_accs = []
        # for x in range(4):
        #     buyers_accs.append(eosf.account(self.eosio_acc, "buyer" + str(x + 1)))
        #     self.wallet.import_key(buyers_accs[x])


        # create accounts for buyers
        buyers_accs = self.create_buyers_accounts(self.eosio_acc, 4)

        # calculate how much EOS to send
        eos_to_transfer = self.soft_cap_eos
        if eos_to_transfer < self.min_contrib_eos:
            eos_to_transfer = self.min_contrib_eos
        elif eos_to_transfer > self.max_contrib_eos != 0:
            eos_to_transfer = self.max_contrib_eos

        # issue tokens to buyers
        eos_to_issue = eos_to_transfer + 1
        for buyer in buyers_accs:
            self.system_token_contract.push_action(
                "issue",
                json.dumps({
                    "to": str(buyer),
                    "quantity": self.toAsset(eos_to_issue, 4, "EOS"),
                    "memo": ""
                }),
                self.system_token_deployer_acc
            )

            assert (eos_to_issue == self.fromAsset(self.system_token_contract.table("accounts", buyer)
                                                   .json["rows"][0]["balance"])["amount"])

        # whitelist accounts if needed
        if self.whitelist:
            for buyer in buyers_accs:
                self.crowdsale_contract.push_action(
                    "white",
                    json.dumps({
                        "account": str(buyer)
                    }),
                    self.issuer_acc
                )

        # calculate how much tokens each buyer will receive
        expected_tokens_per_buyer = int(eos_to_transfer * self.rate * 10 ** self.decimals)
        expected_all_tokens = 0
        expected_all_eos = 0

        # transfer EOS to crowdsale contract
        for buyer in buyers_accs:
            if (expected_all_tokens + expected_tokens_per_buyer) <= self.hard_cap_tkn_cent:
                self.system_token_contract.push_action(
                    "transfer",
                    json.dumps({
                        "from": str(buyer),
                        "to": str(self.crowdsale_deployer_acc),
                        "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                        "memo": ""
                    }),
                    buyer
                )
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
            self.crowdsale_contract.push_action(
                "init",
                json.dumps({
                    "start": self.start_date,
                    "finish": self.finish_date
                }),
                self.crowdsale_deployer_acc
            )

            # rewind time to start
            self.crowdsale_contract.push_action(
                "settime",
                json.dumps({
                    "time": self.start_date
                }),
                self.crowdsale_deployer_acc
            )

            # create accounts for buyers
            buyers_accs = self.create_buyers_accounts(self.eosio_acc, 4)

            # whitelist all buyers
            for buyer in buyers_accs:
                self.crowdsale_contract.push_action(
                    "white",
                    json.dumps({
                        "account": str(buyer)
                    }),
                    self.issuer_acc
                )

            # check that all buyers successfully whitelisted
            #buyers_names = list(map(lambda buyer: buyer.name, buyers_accs))
            whitelisted_names = list(map(lambda row: row["account"], self.crowdsale_contract
                                         .table("whitelist", self.crowdsale_deployer_acc).json["rows"]))
            assert (buyers_accs == whitelisted_names)

            # unwhite all buyers
            for buyer in buyers_accs:
                self.crowdsale_contract.push_action(
                    "unwhite",
                    json.dumps({
                        "account": str(buyer)
                    }),
                    self.issuer_acc
                )
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
                self.system_token_contract.push_action(
                    "issue",
                    json.dumps({
                        "to": str(buyer),
                        "quantity": self.toAsset(eos_to_issue, 4, "EOS"),
                        "memo": ""
                    }),
                    self.system_token_deployer_acc
                )

            # check that unwhited users cannot send EOS to crowdsale
            for buyer in buyers_accs:
                with self.assertRaises(errors.Error):
                    self.system_token_contract.push_action(
                        "transfer",
                        json.dumps({
                            "from": str(buyer),
                            "to": str(self.crowdsale_deployer_acc),
                            "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                            "memo": ""
                        }),
                        buyer
                    )

    def test_05(self):
        cprint("5. Check whitemany & unwhitemany", 'green')

        if self.whitelist:
            # execute 'init'
            self.crowdsale_contract.push_action(
                "init",
                json.dumps({
                    "start": self.start_date,
                    "finish": self.finish_date
                }),
                self.crowdsale_deployer_acc
            )

            # rewind time to start
            self.crowdsale_contract.push_action(
                "settime",
                json.dumps({
                    "time": self.start_date
                }),
                self.crowdsale_deployer_acc
            )

            # create accounts
            buyers_accs = self.create_buyers_accounts(self.eosio_acc, 4)

            # whitelist all buyers
            self.crowdsale_contract.push_action(
                "whitemany",
                json.dumps({
                    "accounts": buyers_accs
                }),
                self.issuer_acc
            )

            # check that all buyers successfully whitelisted
            # buyers_names = list(map(lambda buyer: buyer.name, buyers_accs))
            whitelisted_names = list(map(lambda row: row["account"], self.crowdsale_contract
                                         .table("whitelist", self.crowdsale_deployer_acc).json["rows"]))
            assert (buyers_accs == whitelisted_names)

            # unwhite all buyers
            self.crowdsale_contract.push_action(
                "unwhitemany",
                json.dumps({
                    "accounts": buyers_accs
                }),
                self.issuer_acc
            )
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
                self.system_token_contract.push_action(
                    "issue",
                    json.dumps({
                        "to": str(buyer),
                        "quantity": self.toAsset(eos_to_issue, 4, "EOS"),
                        "memo": ""
                    }),
                    self.system_token_deployer_acc
                )

            # check that unwhited users cannot send EOS to crowdsale
            for buyer in buyers_accs:
                with self.assertRaises(errors.Error):
                    self.system_token_contract.push_action(
                        "transfer",
                        json.dumps({
                            "from": str(buyer),
                            "to": str(self.crowdsale_deployer_acc),
                            "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                            "memo": ""
                        }),
                        buyer
                    )

    def test_06(self):
        cprint("6. Check min and max restrictions", 'green')

        # execute 'init'
        self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc
        )

        # rewind time to start
        self.crowdsale_contract.push_action(
            "settime",
            json.dumps({
                "time": self.start_date
            }),
            self.crowdsale_deployer_acc
        )

        # create account for buyer
        create_account("buyer_acc", self.eosio_acc)
        #self.wallet.import_key(buyer_acc)

        if self.min_contrib_eos_cent != 0 and self.min_contrib_eos_cent > 1 \
                or self.max_contrib_eos_cent != 0 and self.max_contrib_eos_cent < self.hard_cap_eos_cent:
            if self.whitelist:
                # whitelist account if needed
                self.crowdsale_contract.push_action(
                    "white",
                    json.dumps({
                        "account": buyer_acc.name
                    }),
                    self.issuer_acc
                )

            def issueAndTransfer(eos_to_transfer):
                # issue tokens to buyer
                self.system_token_contract.push_action(
                    "issue",
                    json.dumps({
                        "to": buyer_acc.name,
                        "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                        "memo": ""
                    }),
                    self.system_token_deployer_acc
                )

                # transfer EOS to crowdsale contract
                with self.assertRaises(errors.Error):
                    self.system_token_contract.push_action(
                        "transfer",
                        json.dumps({
                            "from": buyer_acc.name,
                            "to": str(self.crowdsale_deployer_acc),
                            "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                            "memo": ""
                        }),
                        buyer_acc
                    )

            # check that cannot send less than min
            if self.min_contrib_eos_cent != 0 and self.min_contrib_eos_cent > 1:
                issueAndTransfer(self.min_contrib_eos / 2)

            # check that cannot send more than max
            if self.max_contrib_eos_cent != 0 and self.max_contrib_eos_cent < self.hard_cap_eos_cent:
                issueAndTransfer(self.max_contrib_eos + 0.0001)

    def test_07(self):
        cprint("7. Check cannot buy before start and after finish", 'green')

        # execute 'init'
        self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc
        )

        # create account for buyer
        create_account("buyer_acc", self.eosio_acc)

        # whitelist account if needed
        if self.whitelist:
            self.crowdsale_contract.push_action(
                "white",
                json.dumps({
                    "account": buyer_acc.name
                }),
                self.issuer_acc
            )

        # calculate how much EOS to send
        eos_to_transfer = self.soft_cap_eos
        if eos_to_transfer < self.min_contrib_eos:
            eos_to_transfer = self.min_contrib_eos
        elif eos_to_transfer > self.max_contrib_eos != 0:
            eos_to_transfer = self.max_contrib_eos

        # issue tokens to buyer
        eos_to_issue = eos_to_transfer + 50
        self.system_token_contract.push_action(
            "issue",
            json.dumps({
                "to": buyer_acc.name,
                "quantity": self.toAsset(eos_to_issue, 4, "EOS"),
                "memo": ""
            }),
            self.system_token_deployer_acc
        )
        assert (eos_to_issue == self.fromAsset(self.system_token_contract.table("accounts", buyer_acc)
                                               .json["rows"][0]["balance"])["amount"])

        # function setting time and sending EOS
        def set_time_and_transfer(timestamp):
            self.crowdsale_contract.push_action(
                "settime",
                json.dumps({
                    "time": timestamp
                }),
                self.crowdsale_deployer_acc
            )

            # transfer EOS to crowdsale contract
            with self.assertRaises(errors.Error):
                self.system_token_contract.push_action(
                    "transfer",
                    json.dumps({
                        "from": buyer_acc.name,
                        "to": str(self.crowdsale_deployer_acc),
                        "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                        "memo": ""
                    }),
                    buyer_acc
                )

        # check that you cannot send EOS before CS start
        set_time_and_transfer(self.start_date - 10)

        # check that you cannot send EOS after CS end
        set_time_and_transfer(self.finish_date + 10)

    def test_08(self):
        cprint("8. Check finalization after reaching hard cap", 'green')

        # execute 'init'
        self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc
        )

        # rewind time to start
        self.crowdsale_contract.push_action(
            "settime",
            json.dumps({
                "time": self.start_date
            }),
            self.crowdsale_deployer_acc
        )

        # create account for buyer
        create_account("buyer_acc", self.eosio_acc)
        #self.wallet.import_key(buyer_acc)

        # issue tokens to buyer
        self.system_token_contract.push_action(
            "issue",
            json.dumps({
                "to": buyer_acc.name,
                "quantity": self.toAsset(self.hard_cap_eos, 4, "EOS"),
                "memo": ""
            }),
            self.system_token_deployer_acc
        )

        # whitelist account if needed
        if self.whitelist:
            self.crowdsale_contract.push_action(
                "white",
                json.dumps({
                    "account": buyer_acc.name
                }),
                self.issuer_acc
            )

        # reach hard cap
        self.reach_cap(self.hard_cap_tkn_cent, buyer_acc)

        # finalize and withdraw EOS
        eos_at_crowdsale = self.system_token_contract.table("accounts", self.crowdsale_deployer_acc).json["rows"][0]
        if not self.transferable:
            self.crowdsale_contract.push_action(
                "finalize",
                json.dumps({}),
                self.issuer_acc
            )

        self.crowdsale_contract.push_action(
            "withdraw",
            json.dumps({}),
            self.issuer_acc
        )

        # check balance afer withdraw
        eos_at_issuer_acc = self.system_token_contract.table("accounts", self.issuer_acc).json["rows"][0]
        assert (eos_at_crowdsale == eos_at_issuer_acc)

    def test_09(self):
        cprint('9. Check refund from multiple accounts', 'green')

        if self.soft_cap_eos > 0:
            # execute 'init'
            self.crowdsale_contract.push_action(
                "init",
                json.dumps({
                    "start": self.start_date,
                    "finish": self.finish_date
                }),
                self.crowdsale_deployer_acc
            )

            # rewind time to start
            self.crowdsale_contract.push_action(
                "settime",
                json.dumps({
                    "time": self.start_date
                }),
                self.crowdsale_deployer_acc
            )

            buyers_accs = []
            for x in range(2):
                # create account for buyers
                buyer_name = "tokenbuyer1{}".format(x+1)
                create_account(buyer_name, self.eosio_acc, buyer_name)
                buyers_accs.append(buyer_name)


                # issue tokens to buyers
                self.system_token_contract.push_action(
                    "issue",
                    json.dumps({
                        "to": str(buyers_accs[x]),
                        "quantity": self.toAsset(self.soft_cap_eos, 4, "EOS"),
                        "memo": ""
                    }),
                    self.system_token_deployer_acc
                )

                # whitelist account if needed
                if self.whitelist:
                    self.crowdsale_contract.push_action(
                        "white",
                        json.dumps({
                            "account": str(buyers_accs[x])
                        }),
                        self.issuer_acc
                    )

            for buyer in buyers_accs:
                # reach quarter of soft cap
                self.reach_cap(self.soft_cap_tkn_cent / 4, buyer)

            # rewind time to finish
            self.crowdsale_contract.push_action(
                "settime",
                json.dumps({
                    "time": self.finish_date + 1
                }),
                self.crowdsale_deployer_acc
            )

            # refund
            for buyer in buyers_accs:
                self.crowdsale_contract.push_action(
                    "refund",
                    json.dumps({
                        "investor": str(buyer)
                    }),
                    buyer
                )

                assert (self.toAsset(self.soft_cap_eos, 4, "EOS") == self.system_token_contract
                        .table("accounts", buyer).json["rows"][0]["balance"])

    def test_10(self):
        cprint('10. Cannot refund after reaching hard cap', 'green')

        if self.soft_cap_eos + self.min_contrib_eos <= self.hard_cap_eos:
            # execute 'init'
            self.crowdsale_contract.push_action(
                "init",
                json.dumps({
                    "start": self.start_date,
                    "finish": self.finish_date
                }),
                self.crowdsale_deployer_acc
            )

            # rewind time to start
            self.crowdsale_contract.push_action(
                "settime",
                json.dumps({
                    "time": self.start_date
                }),
                self.crowdsale_deployer_acc
            )

            # create account for buyer
            create_account("buyer_acc", self.eosio_acc)

            # issue tokens to buyer
            self.system_token_contract.push_action(
                "issue",
                json.dumps({
                    "to": buyer_acc.name,
                    "quantity": self.toAsset(self.hard_cap_eos, 4, "EOS"),
                    "memo": ""
                }),
                self.system_token_deployer_acc
            )

            # whitelist account if needed
            if self.whitelist:
                self.crowdsale_contract.push_action(
                    "white",
                    json.dumps({
                        "account": buyer_acc.name
                    }),
                    self.issuer_acc
                )

            # reach soft cap
            self.reach_cap((self.hard_cap_tkn_cent + self.soft_cap_tkn_cent) / 2, buyer_acc)

            # rewind time to finish
            self.crowdsale_contract.push_action(
                "settime",
                json.dumps({
                    "time": self.finish_date + 1
                }),
                self.issuer_acc
            )

            with self.assertRaises(errors.Error):
                self.crowdsale_contract.push_action(
                    "refund",
                    json.dumps({
                        "investor": buyer_acc.name
                    }),
                    buyer_acc
                )

    def test_11(self):
        cprint('11. Check changing finish date', 'green')

        # execute 'init'
        self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc
        )

        # rewind time to start
        self.crowdsale_contract.push_action(
            "settime",
            json.dumps({
                "time": self.start_date
            }),
            self.crowdsale_deployer_acc
        )

        # change finish date
        self.crowdsale_contract.push_action(
            "setfinish",
            json.dumps({
                "finish": self.finish_date + 10
            }),
            self.issuer_acc
        )
        assert (self.finish_date + 10 == self.crowdsale_contract
                .table("state", self.crowdsale_deployer_acc).json["rows"][0]["finish"])

        # change finish date back
        self.crowdsale_contract.push_action(
            "setfinish",
            json.dumps({
                "finish": self.finish_date
            }),
            self.issuer_acc
        )
        assert (self.finish_date == self.crowdsale_contract
                .table("state", self.crowdsale_deployer_acc).json["rows"][0]["finish"])

        # try to change finish date after CS finished
        self.crowdsale_contract.push_action(
            "settime",
            json.dumps({
                "time": self.finish_date + 1
            }),
            self.issuer_acc
        )
        with self.assertRaises(errors.Error):
            self.crowdsale_contract.push_action(
                "setfinish",
                json.dumps({
                    "finish": self.finish_date
                }),
                self.issuer_acc,
                forceUnique=1
            )

    def test_12(self):
        cprint('12. Check changing start date', 'green')

        # execute 'init'
        self.crowdsale_contract.push_action(
            "init",
            json.dumps({
                "start": self.start_date,
                "finish": self.finish_date
            }),
            self.crowdsale_deployer_acc
        )

        # rewind time to before start
        self.crowdsale_contract.push_action(
            "settime",
            json.dumps({
                "time": self.start_date - 10
            }),
            self.issuer_acc
        )

        self.crowdsale_contract.push_action(
            "setstart",
            json.dumps({
                "start": self.start_date + 10
            }),
            self.issuer_acc
        )

        assert (self.start_date + 10 == self.crowdsale_contract
                .table("state", self.crowdsale_deployer_acc).json["rows"][0]["start"])

        # change finish date back
        self.crowdsale_contract.push_action(
            "setstart",
            json.dumps({
                "start": self.start_date
            }),
            self.issuer_acc
        )
        assert (self.start_date == self.crowdsale_contract
                .table("state", self.crowdsale_deployer_acc).json["rows"][0]["start"])

        # try to change finish date after CS finished
        self.crowdsale_contract.push_action(
            "settime",
            json.dumps({
                "time": self.start_date + 1
            }),
            self.issuer_acc
        )
        with self.assertRaises(errors.Error):
            self.crowdsale_contract.push_action(
                "setstart",
                json.dumps({
                    "start": self.start_date
                }),
                self.issuer_acc,
                forceUnique=1
            )

if __name__ == "__main__":
    verbosity([])  # disable logs

    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", help="increase output verbosity",
                        action="store_true")
    args = parser.parse_args()
    if args.verbose:
        verbosity([Verbosity.INFO, Verbosity.OUT, Verbosity.TRACE, Verbosity.DEBUG])
        print("verbosity turned on")
    unittest.main()

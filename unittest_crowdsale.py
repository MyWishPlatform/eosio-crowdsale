import setup
import json
import eosf
from termcolor import cprint
import node
import unittest
import re
from decimal import Decimal

setup.set_verbose(False)
setup.set_json(False)
setup.use_keosd(False)


class CrowdsaleTests(unittest.TestCase):
    @classmethod
    def parseConfig(cls):
        global cfg
        cfg = {}
        with open('config.h', 'r') as cfg_file:
            for line in cfg_file.readlines():
                match = re.search('#define (\w+) ([\w.]+)', line)
                if match:
                    cfg[match.group(1)] = match.group(2)

    @classmethod
    def setUpClass(cls):
        cls.parseConfig()

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

        # create MINTDEST accounts
        for x in range(int(cfg["MINTCNT"])):
            self.wallet.import_key(eosf.account(self.eosio_acc, cfg["MINTDEST" + str(x)]))

        # create system token deployer account
        self.system_token_deployer_acc = eosf.account(self.eosio_acc, "eosio.token")
        self.wallet.import_key(self.system_token_deployer_acc)

        # create token deployer account
        self.token_deployer_acc = eosf.account(self.eosio_acc, cfg["CONTRACT"])
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
                "maximum_supply": "1009410066.0000 EOS"
            }),
            self.system_token_deployer_acc
        ).error)

        # create custom token asset
        max_supply = int(cfg["HARD_CAP_TKN"])
        for x in range(int(cfg["MINTCNT"])):
            max_supply += int(cfg["MINTVAL" + str(x)])
        max_supply /= 10 ** int(cfg["DECIMALS"])
        assert (not self.token_contract.push_action(
            "create",
            json.dumps({
                "issuer": str(self.crowdsale_deployer_acc),
                "maximum_supply": str(max_supply) + " " + cfg["SYMBOL"]
            }),
            self.token_deployer_acc
        ).error)

        # deploy crowdsale contract
        self.crowdsale_contract = eosf.Contract(
            self.crowdsale_deployer_acc,
            "eosio-crowdsale/crowdsale",
            wast_file='crowdsale.wast',
            abi_file='crowdsale.abi'
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
        return str(Decimal(amount).quantize(Decimal('1.' + '0' * int(decimals)))) + " " + symbol

    def fromAsset(self, asset):
        dictionary = {}
        split = asset.split(" ")
        dictionary["amount"] = float(split[0])
        dictionary["symbol"] = split[1]
        dictionary["decimals"] = len(split[0].split(".")[1])
        return dictionary

    def tearDown(self):
        node.stop()

    def test_01(self):
        cprint(".1. Check premint", 'green')

        # check that destination accounts has no tokens before initialize
        for x in range(int(cfg["MINTCNT"])):
            assert (len(self.token_contract.table("accounts", cfg["MINTDEST" + str(x)]).json["rows"]) == 0)

        # execute 'init'
        assert (not self.crowdsale_contract.push_action(
            "init",
            json.dumps({}),
            self.crowdsale_deployer_acc
        ).error)

        # check that destination addresses received their tokens after 'init'
        for x in range(int(cfg["MINTCNT"])):
            expected_value = int(cfg["MINTVAL" + str(x)]) / 10 ** int(cfg["DECIMALS"])
            real_value_with_symbol = self.token_contract \
                .table("accounts", cfg["MINTDEST" + str(x)]) \
                .json["rows"][0]["balance"]
            real_value = float(real_value_with_symbol[:-(len(cfg['SYMBOL']) + 1)])
            assert (expected_value == real_value)

        # check that you cannot execute 'init' second time
        assert (self.crowdsale_contract.push_action(
            "init",
            '{}',
            self.crowdsale_deployer_acc,
            forceUnique=1,
        ).error)

    def test_02(self):
        cprint("2. Check buy tokens", 'green')

        # check that destination accounts has no tokens before initialize
        for x in range(int(cfg["MINTCNT"])):
            assert (len(self.token_contract.table("accounts", cfg["MINTDEST" + str(x)]).json["rows"]) == 0)

        # execute 'init'
        assert (not self.crowdsale_contract.push_action(
            "init",
            json.dumps({}),
            self.crowdsale_deployer_acc
        ).error)

        # create account for buyer
        buyer_acc = eosf.account(self.eosio_acc, "buyer")
        self.wallet.import_key(buyer_acc)

        # calculate how much EOS to send
        min_contrib = int(cfg["MIN_CONTRIB"]) / 10 ** 4
        max_contrib = int(cfg["MAX_CONTRIB"]) / 10 ** 4
        eos_to_transfer = 10
        if eos_to_transfer < min_contrib:
            eos_to_transfer = min_contrib
        elif eos_to_transfer > max_contrib:
            eos_to_transfer = max_contrib

        # issue tokens to buyer
        eos_to_issue = eos_to_transfer + 50
        assert (not self.system_token_contract.push_action(
            "issue",
            json.dumps({
                "to": str(buyer_acc),
                "quantity": self.toAsset(eos_to_issue, 4, "EOS"),
                "memo": "memo"
            }),
            self.system_token_deployer_acc
        ).error)
        assert (eos_to_issue == int(self.fromAsset(self.system_token_contract.table("accounts", buyer_acc)
                                                   .json["rows"][0]["balance"])["amount"]))

        if bool(cfg["WHITELIST"]):
            # check that not whitelisted user cannot send EOS to contract
            assert (self.system_token_contract.push_action(
                "transfer",
                json.dumps({
                    "from": str(buyer_acc),
                    "to": str(self.crowdsale_deployer_acc),
                    "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                    "memo": "memo"
                }),
                buyer_acc
            ).error)

            # whitelist account if needed
            assert (not self.crowdsale_contract.push_action(
                "white",
                json.dumps({
                    "account": str(buyer_acc)
                }),
                self.crowdsale_deployer_acc
            ).error)

        # transfer EOS to crowdsale contract
        assert (not self.system_token_contract.push_action(
            "transfer",
            json.dumps({
                "from": str(buyer_acc),
                "to": str(self.crowdsale_deployer_acc),
                "quantity": self.toAsset(eos_to_transfer, 4, "EOS"),
                "memo": "memo"
            }),
            buyer_acc
        ).error)

        # check EOS balances
        assert (eos_to_transfer == int(self.fromAsset(self.system_token_contract
                                                      .table("accounts", self.crowdsale_deployer_acc)
                                                      .json["rows"][0]["balance"])["amount"]))
        assert ((eos_to_issue - eos_to_transfer) == int(self.fromAsset(self.system_token_contract
                                                                       .table("accounts", buyer_acc)
                                                                       .json["rows"][0]["balance"])["amount"]))

        # check state in crowdsale
        deposit = self.crowdsale_contract.table("deposit", self.crowdsale_deployer_acc).json["rows"][0]
        expected_tokens = int(eos_to_transfer * int(cfg["RATE"]) / int(cfg["RATE_DENOM"]) * 10 ** int(cfg["DECIMALS"]))
        assert (deposit["account"] == buyer_acc.name)
        assert (deposit["amount"] == eos_to_transfer * 10 ** 4)
        assert (deposit["tokens"] == expected_tokens)
        if bool(cfg["WHITELIST"]):
            assert (buyer_acc.name == self.crowdsale_contract.table("whitelist", self.crowdsale_deployer_acc)
                    .json["rows"][0]["account"])  # if whitelist is enabled
        assert (expected_tokens == self.crowdsale_contract
                .table("state", self.crowdsale_deployer_acc).json["rows"][0]["total_tokens"])


if __name__ == "__main__":
    unittest.main()

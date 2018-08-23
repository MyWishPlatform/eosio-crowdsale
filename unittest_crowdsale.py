import setup
import json
import cleos
import eosf
from termcolor import cprint
import node
import sess
import unittest
import re

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
        self.wallet = eosf.Wallet()

        # create eosio account
        self.eosio_acc = eosf.AccountMaster()
        self.wallet.import_key(self.eosio_acc)

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
        assert (not self.token_contract.push_action(
            "create",
            json.dumps({
                "issuer": str(self.crowdsale_deployer_acc),
                "maximum_supply": "10000019375.00 WISH"
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

    def tearDown(self):
        node.stop()

    def test_01(self):
        print("1. Check premint")

        assert (not self.crowdsale_contract.push_action(
            "init",
            json.dumps({}),
            self.crowdsale_deployer_acc,
            output=True
        ).error)

        for x in range(int(cfg["MINTCNT"])):
            expected_value = int(cfg["MINTVAL" + str(x)]) / 10 ** int(cfg["DECIMALS"])
            real_value_with_symbol = self.token_contract \
                .table("accounts", cfg["MINTDEST" + str(x)]) \
                .json["rows"][0]["balance"]
            real_value = float(real_value_with_symbol[:-(len(cfg['SYMBOL']) + 1)])
            assert (expected_value == real_value)


if __name__ == "__main__":
    unittest.main()

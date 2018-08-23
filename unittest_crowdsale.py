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
    def run(self, result=None):
        """ Stop after first error """
        if not result.failures:
            super().run(result)

    @classmethod
    def setUpClass(cls):
        global cfg
        cfg = {}
        with open('config.h', 'r') as cfg_file:
            for line in cfg_file.readlines():
                match = re.search('#define (\w+) ([\w.]+)', line)
                if match:
                    cfg[match.group(1)] = match.group(2)

        assert (not node.reset().error)
        global wallet
        global eosio
        global mywishtoken5
        global token_deployer
        global crowdsale_deployer

        wallet = eosf.Wallet()

        eosio = eosf.AccountMaster()
        wallet.import_key(eosio)

        for x in range(int(cfg["MINTCNT"])):
            wallet.import_key(eosf.account(eosio, cfg["MINTDEST" + str(x)]))

        token_deployer = eosf.account(eosio, cfg["CONTRACT"])
        wallet.import_key(token_deployer)

        crowdsale_deployer = eosf.account(eosio, "ico.deployer")
        wallet.import_key(crowdsale_deployer)

        global contract_eosio_bios
        contract_eosio_bios = eosf.Contract(eosio, "eosio.bios")
        assert (not contract_eosio_bios.error)
        deployment_bios = contract_eosio_bios.deploy()
        assert (not deployment_bios.error)

        global contract_token
        contract_token = eosf.Contract(token_deployer, "eosio.token")
        assert (not contract_token.error)
        deployment_token = contract_token.deploy()
        assert (not deployment_token.error)
        assert (not token_deployer.code().error)

        assert (not contract_token.push_action(
            "create",
            json.dumps({
                "issuer": str(crowdsale_deployer),
                "maximum_supply": "10000019375.00 WISH"
            }),
            token_deployer
        ).error)

        global contract_crowdsale
        contract_crowdsale = eosf.Contract(
            crowdsale_deployer,
            "eosio-crowdsale/crowdsale",
            wast_file='crowdsale.wast',
            abi_file='crowdsale.abi'
        )

        assert (not contract_crowdsale.error)

        deployment_crowdsale = contract_crowdsale.deploy()
        assert (not deployment_crowdsale.error)
        assert (not crowdsale_deployer.code().error)

        assert (not contract_eosio_bios.push_action(
            "updateauth",
            json.dumps({
                "account": str(crowdsale_deployer),
                "permission": "active",
                "parent": "owner",
                "auth": {
                    "threshold": 1,
                    "keys": [
                        {
                            "key": str(crowdsale_deployer.json["permissions"][1]["required_auth"]["keys"][0]["key"]),
                            "weight": 1
                        }
                    ],
                    "accounts": [
                        {
                            "permission": {
                                "actor": str(crowdsale_deployer),
                                "permission": "eosio.code"
                            },
                            "weight": 1
                        }
                    ],
                    "waits": []
                }
            }),
            crowdsale_deployer
        ).error)

        assert (not contract_crowdsale.push_action(
            "init",
            json.dumps({}),
            crowdsale_deployer,
            output=True
        ).error)

    @classmethod
    def tearDownClass(cls):
        node.stop()

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_01(self):
        print("1. Check premint")
        for x in range(int(cfg["MINTCNT"])):
            expected_value = int(cfg["MINTVAL" + str(x)]) / 10 ** int(cfg["DECIMALS"])
            real_value_with_symbol = contract_token\
                .table("accounts", cfg["MINTDEST" + str(x)])\
                .json["rows"][0]["balance"]
            real_value = float(real_value_with_symbol[:-(len(cfg['SYMBOL']) + 1)])
            assert (expected_value == real_value)


if __name__ == "__main__":
    unittest.main()

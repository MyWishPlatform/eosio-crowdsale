import setup
import json
import cleos
import eosf
from termcolor import cprint
import node
import sess
import unittest
from configparser import ConfigParser

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
        config = ConfigParser()
        config.read('test/config.ini')
        global cfg
        cfg = config['DEFAULT']

        assert (not node.reset().error)
        global wallet
        global eosio
        global token_deployer
        global crowdsale_deployer

        wallet = eosf.Wallet()

        eosio = eosf.AccountMaster()
        wallet.import_key(eosio)

        token_deployer = eosf.account(eosio, "tkn.deployer")
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
            "eosio-crowdsale",
            wast_file='/build/crowdsale.wast',
            abi_file='/build/crowdsale.abi'
        )

        assert (not contract_crowdsale.error)

        deployment_crowdsale = contract_crowdsale.deploy()
        assert (not deployment_crowdsale.error)
        assert (not crowdsale_deployer.code().error)




        crowdsale_deployer_pubkey = crowdsale_deployer.json["permissions"][1]["required_auth"]["keys"][0]["key"]
        permissionActionJSON = {
            "account": str(crowdsale_deployer),
            "permission": "active",
            "parent": "owner",
            "auth": {
                "threshold": 1,
                "keys": [
                    {
                        "key": str(crowdsale_deployer_pubkey),
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
        }
        setPermissionAction = json.dumps(permissionActionJSON)
        assert (not contract_eosio_bios.push_action("updateauth", setPermissionAction, crowdsale_deployer).error)




        # assert (not contract_crowdsale.push_action(
        #     "init",
        #     '{}',
        #     crowdsale_deployer,
        #     output=True
        # ).error)

    @classmethod
    def tearDownClass(cls):
        node.stop()

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_01(self):
        contract_crowdsale.push_action(
            "test",
            json.dumps({
                "acc": str(crowdsale_deployer)
            }),
            crowdsale_deployer
        )
        # print(contract_crowdsale.table("stat", "WISH"))
        # print(contract_token.table("stat", "WISH"))
        # print(contract_token.table("accounts", "WISH"))

        # cprint(contract_crowdsale.table('deposits', 'mywishio'), 'red')
        # cprint(contract_crowdsale.table('whitelist', 'mywishio'), 'red')


if __name__ == "__main__":
    unittest.main()

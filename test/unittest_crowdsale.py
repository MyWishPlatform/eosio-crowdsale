import setup
import eosf
import node
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

        testnet = node.reset()
        assert (not testnet.error)

        global wallet
        wallet = eosf.Wallet()
        assert (not wallet.error)

        global account_master
        account_master = eosf.AccountMaster()
        wallet.import_key(account_master)
        assert (not account_master.error)

        global account_issuer
        account_issuer = eosf.account(account_master)
        wallet.import_key(account_issuer)
        assert (not account_issuer.error)

        global account_deploy_crowdsale
        account_deploy_crowdsale = eosf.account(account_master)
        wallet.import_key(account_deploy_crowdsale)
        assert (not account_deploy_crowdsale.error)

        global account_deploy_token
        account_deploy_token = eosf.account(account_master)
        wallet.import_key(account_deploy_token)
        assert (not account_deploy_token.error)

        global contract_eosio_bios
        contract_eosio_bios = eosf.Contract(account_master, "eosio.bios")
        assert (not contract_eosio_bios.error)
        deployment_bios = contract_eosio_bios.deploy()
        assert (not deployment_bios.error)

        global contract_token
        contract_token = eosf.Contract(account_deploy_token, "eosio.token")
        assert (not contract_token.error)
        deployment_token = contract_token.deploy()
        assert (not deployment_token.error)
        assert (not account_deploy_token.code().error)

        global contract_crowdsale
        contract_crowdsale = eosf.Contract(
            account_deploy_crowdsale,
            "eosio-crowdsale",
            wast_file='/build/crowdsale.wast',
            abi_file='/build/crowdsale.abi'
        )
        assert (not contract_crowdsale.error)

        deployment_crowdsale = contract_crowdsale.deploy()
        assert (not deployment_crowdsale.error)
        assert (not account_deploy_crowdsale.code().error)

    @classmethod
    def tearDownClass(cls):
        node.stop()

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_01(self):
        pass


if __name__ == "__main__":
    unittest.main()
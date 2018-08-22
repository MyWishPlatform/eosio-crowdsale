import setup
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
        sess.init()

        global contract_crowdsale
        contract_crowdsale = eosf.Contract(
            sess.alice,
            "eosio-crowdsale",
            wast_file='/build/crowdsale.wast',
            abi_file='/build/crowdsale.abi'
        )
        assert (not contract_crowdsale.error)

        deployment_crowdsale = contract_crowdsale.deploy()
        assert (not deployment_crowdsale.error)
        assert (not sess.alice.code().error)

    @classmethod
    def tearDownClass(cls):
        node.stop()

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_01(self):
        # cprint(contract_crowdsale.table('deposits', 'mywishio'), 'red')
        # cprint(contract_crowdsale.table('whitelist', 'mywishio'), 'red')

        token_contract = eosf.Contract(sess.alice, "eosio.token")
        cprint(token_contract.table('accounts', 'mywishio'), 'green')

if __name__ == "__main__":
    unittest.main()

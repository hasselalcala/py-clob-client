from py_near.account import Account
import os
import base64
import json
from py_clob_client.MPCHelpers import validate_mpc_signature, reconstruct_signature
from py_order_utils.utils import prepend_zx

class MPCSigner:
    def __init__(self, account_id: str, private_key: str, network: str, ota_account: str, chain_id: int, path: str):

        self.account_id = account_id
        self.private_key = private_key
        self.network = "https://near.drpc.org" if network == "mainnet" else "https://test.rpc.fastnear.com"
        self.ota_account = ota_account
        self.signer_account = Account(self.account_id, self.private_key, self.network)
        self.chain_id = chain_id
        self.path = path

    async def startup(self):
        """Initialize the account connection"""
        await self.signer_account.startup()
        self.logger.info(f"Near MPC Signer initialized for account: {self.account_id}")
    
    async def sign(self, message_hash):
        
        """
        Signs a message hash
        """
        result = await self.signer_account.function_call(
            'polymarket_agent.testnet',
            "sign_hash",
            {"hash": message_hash, "path": self.path},
            gas=300000000000000,
            amount=1,
        )
        
        mpc_signature = self._extract_signature_from_result(result)

        print("mpc_signature from signer: ", mpc_signature)

        # Validate the signature using original MPC values
        self.ota_account = validate_mpc_signature(message_hash, mpc_signature, self.ota_account)

        signature = reconstruct_signature(mpc_signature)
        
        prepend_signature = prepend_zx(signature)
        
        return prepend_signature

    def _extract_signature_from_result(self, result):
        """Extract the signature from the transaction result"""
        
        if hasattr(result, 'status'):
            
            if isinstance(result.status, dict) and 'SuccessValue' in result.status:
                success_value = result.status['SuccessValue']
                decoded_bytes = base64.b64decode(success_value)
                decoded_json = json.loads(decoded_bytes.decode('utf-8'))
                return decoded_json
            else:
                print(f"Debug - result.status keys: {result.status.keys() if hasattr(result.status, 'keys') else 'No keys'}")
                raise Exception(f"Unexpected result structure: {result.status}")
        else:
            print(f"Debug - result has no status attribute")
            return None
            
    def get_chain_id(self):
        return self.chain_id
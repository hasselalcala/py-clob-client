from .model import ClobAuth
from poly_eip712_structs import make_domain
from py_clob_client.MPCSigner import MPCSigner
from py_order_utils.utils import prepend_zx
from eth_utils import keccak
from py_clob_client.MPCHelpers import validate_mpc_signature, reconstruct_signature

CLOB_DOMAIN_NAME = "ClobAuthDomain"
CLOB_VERSION = "1"
MSG_TO_SIGN = "This message attests that I control the given wallet"


def get_clob_auth_domain(chain_id: int):
    return make_domain(name=CLOB_DOMAIN_NAME, version=CLOB_VERSION, chainId=chain_id)

async def sign_clob_auth_message(signer: MPCSigner, timestamp: int, nonce: int) -> str:

    clob_auth_msg = ClobAuth(
        address=signer.ota_account,
        timestamp=str(timestamp),
        nonce=nonce,
        message=MSG_TO_SIGN,
    )
    chain_id = signer.chain_id
    
    # Remove the local signer and add the MPCSigner instance.
    # take the hash to send it to the MPCSigner
    hash_to_sign = keccak(clob_auth_msg.signable_bytes(get_clob_auth_domain(chain_id))).hex()

    # Send the hash to the MPCSigner and the signature is returned 
    mpc_signature = await signer.sign(hash_to_sign)

    return mpc_signature
from .model import ClobAuth
from poly_eip712_structs import make_domain
from py_clob_client.MPCSigner import MPCSigner
from py_order_utils.utils import prepend_zx
from eth_utils import keccak

CLOB_DOMAIN_NAME = "ClobAuthDomain"
CLOB_VERSION = "1"
MSG_TO_SIGN = "This message attests that I control the given wallet"


def get_clob_auth_domain(chain_id: int):
    return make_domain(name=CLOB_DOMAIN_NAME, version=CLOB_VERSION, chainId=chain_id)

async def sign_clob_auth_message(signer: MPCSigner, timestamp: int, nonce: int) -> str:
    print("method: sign_clob_auth_message")
    clob_auth_msg = ClobAuth(
        address=signer.ota_account,
        timestamp=str(timestamp),
        nonce=nonce,
        message=MSG_TO_SIGN,
    )
    chain_id = signer.chain_id
    print("chain_id: ", chain_id)

    # Remove the local signer and add the MPCSigner instance.
    # take the hash to send it to the MPCSigner
    hash_to_sign = keccak(clob_auth_msg.signable_bytes(get_clob_auth_domain(chain_id))).hex()
    print("Hash to send to MPC: ", hash_to_sign)

    # Send the hash to the MPCSigner and the signature is returned in format r, s y v
    mpc_signature = await signer.sign(hash_to_sign)
    print("mpc_signature: ", mpc_signature)

    # Convert the signature to the format expected by CLOB using the r, s and v values
    signature = reconstruct_signature(mpc_signature)
    print("Reconstructed signature: ", signature)

    prepend_signature = prepend_zx(signature)
    print("Prepended signature: ", prepend_signature)
    return prepend_signature

#TODO: Analize if this is the correct way to reconstruct the signature and if this the best place to do it
# I think this should be a helper function to be used in the MPCSigner class or something like that
def reconstruct_signature(signature):
    """
    Reconstruct the signature from the r, s and v values returned by MPC
    Returns the signature in the format expected by Ethereum/CLOB
    """
    r_point = signature["big_r"]["affine_point"]
    s_scalar = signature["s"]["scalar"]
    recovery_id = signature["recovery_id"]

    # Convert recovery_id to v (Ethereum format)
    # recovery_id is typically 0 or 1, but Ethereum uses 27 + recovery_id
    v = 27 + recovery_id
    
    # Ensure r and s are properly formatted as 64-character hex strings
    # Remove 0x prefix if present and pad to 64 characters
    r_hex = r_point.replace('0x', '').zfill(64).lower()
    s_hex = s_scalar.replace('0x', '').zfill(64).lower()
    
    # Convert v to 2-character hex
    v_hex = hex(v)[2:].zfill(2).lower()
    
    # Concatenate r + s + v to form the complete signature
    complete_signature = r_hex + s_hex + v_hex
    
    return complete_signature
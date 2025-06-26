from datetime import datetime
from py_clob_client.MPCSigner import MPCSigner
from py_clob_client.signing.MPCeip712 import sign_clob_auth_message
from py_clob_client.clob_types import ApiCreds, RequestArgs
from py_clob_client.signing.hmac import build_hmac_signature

POLY_ADDRESS = "POLY_ADDRESS"
POLY_SIGNATURE = "POLY_SIGNATURE"
POLY_TIMESTAMP = "POLY_TIMESTAMP"
POLY_NONCE = "POLY_NONCE"
POLY_API_KEY = "POLY_API_KEY"
POLY_PASSPHRASE = "POLY_PASSPHRASE"


async def create_level_1_headers(signer: MPCSigner, nonce: int = None):
    """
    Creates Level 1 Poly headers for a request
    """
    print("method: create_level_1_headers")
    timestamp = int(datetime.now().timestamp())

    n = 0
    if nonce is not None:
        n = nonce

    actual_address = signer.ota_account
    signature = await sign_clob_auth_message(signer, timestamp, n)
    headers = {
        POLY_ADDRESS: actual_address, # MPCSigner instance
        POLY_SIGNATURE: signature, # signature comes from the MPC signature 
        POLY_TIMESTAMP: str(timestamp),
        POLY_NONCE: str(n),
    }
    
    return headers

def create_level_2_headers(signer: str, creds: ApiCreds, request_args: RequestArgs):
    """
    Creates Level 2 Poly headers for a request
    """
    timestamp = int(datetime.now().timestamp())

    hmac_sig = build_hmac_signature(
        creds.api_secret,
        timestamp,
        request_args.method,
        request_args.request_path,
        request_args.body,
    )

    return {
        POLY_ADDRESS: signer,
        POLY_SIGNATURE: hmac_sig,
        POLY_TIMESTAMP: str(timestamp),
        POLY_API_KEY: creds.api_key,
        POLY_PASSPHRASE: creds.api_passphrase,
    }

from datetime import datetime
from py_clob_client.MPCSigner import MPCSigner
from py_clob_client.signing.MPCeip712 import sign_clob_auth_message

POLY_ADDRESS = "POLY_ADDRESS"
POLY_SIGNATURE = "POLY_SIGNATURE"
POLY_TIMESTAMP = "POLY_TIMESTAMP"
POLY_NONCE = "POLY_NONCE"

async def create_level_1_headers(signer: MPCSigner, nonce: int = None):
    """
    Creates Level 1 Poly headers for a request
    """
    print("method: create_level_1_headers")
    timestamp = int(datetime.now().timestamp())

    n = 0
    if nonce is not None:
        n = nonce

    signature = await sign_clob_auth_message(signer, timestamp, n)
    headers = {
        POLY_ADDRESS: signer.ota_account, # <--- HERE the ota_account is the MPCSigner instance
        POLY_SIGNATURE: signature, # signature comes from the MPC signature 
        POLY_TIMESTAMP: str(timestamp),
        POLY_NONCE: str(n),
    }
    
    # Debug headers
    print("Debug - Headers being sent in MPC signer:")
    print(f"POLY_ADDRESS: {headers[POLY_ADDRESS]}")
    print(f"POLY_SIGNATURE: {headers[POLY_SIGNATURE]}")
    print(f"POLY_TIMESTAMP: {headers[POLY_TIMESTAMP]}")
    print(f"POLY_NONCE: {headers[POLY_NONCE]}")
    
    return headers
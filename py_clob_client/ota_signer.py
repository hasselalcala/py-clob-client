from eth_keys import keys
from eth_utils import to_checksum_address


class OTASigner:
    def __init__(self, scalar: str, chain_id: int):
        assert scalar.startswith("0x") or scalar.isalnum(), "Scalar must be hex string"
        scalar_hex = scalar[2:] if scalar.startswith("0x") else scalar
        self.private_key = bytes.fromhex(scalar_hex)
        self.account = keys.PrivateKey(self.private_key)
        self.chain_id = chain_id

    def address(self):
        return to_checksum_address(self.account.public_key.to_address())

    def get_chain_id(self):
        return self.chain_id

    def sign(self, message_hash: bytes):
        """
        Signs a message hash (32 bytes) using the OTA private key.
        Returns a hex-encoded signature string (r + s + v).
        """
        sig = self.account.sign_msg_hash(message_hash)
        return sig.to_hex()

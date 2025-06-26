def validate_mpc_signature(hash_hex: str, mpc_signature: dict, expected_address: str) -> bool:
    """
    Validate that the MPC signature was created by the expected address
    Using original MPC values before reconstruction
    """
    from eth_keys import keys
    from eth_utils import keccak
    
    # Extract values from MPC signature
    r_point = mpc_signature["big_r"]["affine_point"]
    s_scalar = mpc_signature["s"]["scalar"]
    recovery_id = mpc_signature["recovery_id"]
    
    # Extract x coordinate from affine_point (remove 02/03 prefix)
    if r_point.startswith('02') or r_point.startswith('03'):
        r_x = r_point[2:]  # Remove 02/03 prefix
    else:
        r_x = r_point
    
    # Convert hex strings to int
    r_int = int(r_x, 16)
    s_int = int(s_scalar, 16)
    
    # Recover the public key
    signature_obj = keys.Signature(vrs=(recovery_id, r_int, s_int))
    public_key = signature_obj.recover_public_key_from_msg_hash(bytes.fromhex(hash_hex))
    
    # Get the address
    recovered_address = public_key.to_checksum_address()
    
    is_valid = expected_address.lower() == recovered_address.lower()
    print(f"signature is_valid?: {is_valid}")
    return recovered_address

def reconstruct_signature(signature):
    """
    Reconstruct the signature from the r, s and v values returned by MPC
    Returns the signature in the format expected by Ethereum/CLOB
    """
    r_point = signature["big_r"]["affine_point"]
    s_scalar = signature["s"]["scalar"]
    recovery_id = signature["recovery_id"]

    # Convert recovery_id to v (Ethereum format)
    v = 27 + recovery_id
    
    # Extract ONLY the x coordinate from affine_point (remove 02/03 prefix)
    if r_point.startswith('02') or r_point.startswith('03'):
        r_x = r_point[2:]  # Remove 02/03 prefix
    else:
        r_x = r_point
    
    # Ensure r and s are properly formatted as 64-character hex strings
    r_hex = r_x.replace('0x', '').zfill(64).lower()
    s_hex = s_scalar.replace('0x', '').zfill(64).lower()
    
    # Convert v to 2-character hex
    v_hex = hex(v)[2:].zfill(2).lower()
    
    # Concatenate r + s + v to form the complete signature
    complete_signature = r_hex + s_hex + v_hex
    
    return complete_signature
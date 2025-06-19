# py_clob_client/raw_builder.py

from py_clob_client.order_builder.builder import UtilsOrderBuilder, OrderData, UtilsSigner, get_contract_config

def get_order_and_hash(order_data: OrderData, private_key: str, chain_id: int):
    config = get_contract_config(chain_id, False)
    builder = UtilsOrderBuilder(
        config.exchange,
        chain_id,
        UtilsSigner(private_key)
    )
    order = builder.build_order(order_data)
    order_hash = builder._create_struct_hash(order)
    return order, order_hash

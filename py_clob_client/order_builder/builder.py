from py_order_utils.builders import OrderBuilder as UtilsOrderBuilder
from py_order_utils.signer import Signer as UtilsSigner
from py_order_utils.model import (
    EOA,
    OrderData,
    SignedOrder,
    BUY as UtilsBuy,
    SELL as UtilsSell,
)
from py_order_utils.model.sides import BUY, SELL
from py_order_utils.model.signatures import EOA, POLY_GNOSIS_SAFE, POLY_PROXY
from py_order_utils.utils import normalize_address
from py_order_utils.builders.exception import ValidationException
from py_order_utils.model.order import Order

from .helpers import (
    to_token_decimals,
    round_down,
    round_normal,
    decimal_places,
    round_up,
)
from .constants import BUY, SELL
from ..config import get_contract_config
from ..signer import Signer
from ..clob_types import (
    OrderArgs,
    CreateOrderOptions,
    TickSize,
    RoundConfig,
    MarketOrderArgs,
    OrderSummary,
    OrderType,
)

ROUNDING_CONFIG: dict[TickSize, RoundConfig] = {
    "0.1": RoundConfig(price=1, size=2, amount=3),
    "0.01": RoundConfig(price=2, size=2, amount=4),
    "0.001": RoundConfig(price=3, size=2, amount=5),
    "0.0001": RoundConfig(price=4, size=2, amount=6),
}


class OrderBuilder:
    def __init__(self, signer: Signer, sig_type=None, funder=None):
        self.signer = signer

        # Signature type used sign orders, defaults to EOA type
        self.sig_type = sig_type if sig_type is not None else EOA

        # Address which holds funds to be used.
        # Used for Polymarket proxy wallets and other smart contract wallets
        # Defaults to the address of the signer
        self.funder = funder if funder is not None else self.signer.address()

    def get_order_amounts(
        self, side: str, size: float, price: float, round_config: RoundConfig
    ):
        raw_price = round_normal(price, round_config.price)

        if side == BUY:
            raw_taker_amt = round_down(size, round_config.size)

            raw_maker_amt = raw_taker_amt * raw_price
            if decimal_places(raw_maker_amt) > round_config.amount:
                raw_maker_amt = round_up(raw_maker_amt, round_config.amount + 4)
                if decimal_places(raw_maker_amt) > round_config.amount:
                    raw_maker_amt = round_down(raw_maker_amt, round_config.amount)

            maker_amount = to_token_decimals(raw_maker_amt)
            taker_amount = to_token_decimals(raw_taker_amt)

            return UtilsBuy, maker_amount, taker_amount
        elif side == SELL:
            raw_maker_amt = round_down(size, round_config.size)

            raw_taker_amt = raw_maker_amt * raw_price
            if decimal_places(raw_taker_amt) > round_config.amount:
                raw_taker_amt = round_up(raw_taker_amt, round_config.amount + 4)
                if decimal_places(raw_taker_amt) > round_config.amount:
                    raw_taker_amt = round_down(raw_taker_amt, round_config.amount)

            maker_amount = to_token_decimals(raw_maker_amt)
            taker_amount = to_token_decimals(raw_taker_amt)

            return UtilsSell, maker_amount, taker_amount
        else:
            raise ValueError(f"order_args.side must be '{BUY}' or '{SELL}'")

    def get_market_order_amounts(
        self, side: str, amount: float, price: float, round_config: RoundConfig
    ):
        raw_price = round_normal(price, round_config.price)

        if side == BUY:
            raw_maker_amt = round_down(amount, round_config.size)
            raw_taker_amt = raw_maker_amt / raw_price
            if decimal_places(raw_taker_amt) > round_config.amount:
                raw_taker_amt = round_up(raw_taker_amt, round_config.amount + 4)
                if decimal_places(raw_taker_amt) > round_config.amount:
                    raw_taker_amt = round_down(raw_taker_amt, round_config.amount)

            maker_amount = to_token_decimals(raw_maker_amt)
            taker_amount = to_token_decimals(raw_taker_amt)

            return UtilsBuy, maker_amount, taker_amount

        elif side == SELL:
            raw_maker_amt = round_down(amount, round_config.size)

            raw_taker_amt = raw_maker_amt * raw_price
            if decimal_places(raw_taker_amt) > round_config.amount:
                raw_taker_amt = round_up(raw_taker_amt, round_config.amount + 4)
                if decimal_places(raw_taker_amt) > round_config.amount:
                    raw_taker_amt = round_down(raw_taker_amt, round_config.amount)

            maker_amount = to_token_decimals(raw_maker_amt)
            taker_amount = to_token_decimals(raw_taker_amt)

            return UtilsSell, maker_amount, taker_amount
        else:
            raise ValueError(f"order_args.side must be '{BUY}' or '{SELL}'")

    def create_order(
        self, order_args: OrderArgs, options: CreateOrderOptions
    ) -> SignedOrder:
        """
        Creates and signs an order
        """
        side, maker_amount, taker_amount = self.get_order_amounts(
            order_args.side,
            order_args.size,
            order_args.price,
            ROUNDING_CONFIG[options.tick_size],
        )

        data = OrderData(
            maker=self.funder,
            taker=order_args.taker,
            tokenId=order_args.token_id,
            makerAmount=str(maker_amount),
            takerAmount=str(taker_amount),
            side=side,
            feeRateBps=str(order_args.fee_rate_bps),
            nonce=str(order_args.nonce),
            signer=self.signer.address(),
            expiration=str(order_args.expiration),
            signatureType=self.sig_type,
        )

        contract_config = get_contract_config(
            self.signer.get_chain_id(), options.neg_risk
        )

        order_builder = UtilsOrderBuilder(
            contract_config.exchange,
            self.signer.get_chain_id(),
            UtilsSigner(key=self.signer.private_key),
        )

        return order_builder.build_signed_order(data)

    def create_market_order(
        self, order_args: MarketOrderArgs, options: CreateOrderOptions
    ) -> SignedOrder:
        """
        Creates and signs a market order
        """
        side, maker_amount, taker_amount = self.get_market_order_amounts(
            order_args.side,
            order_args.amount,
            order_args.price,
            ROUNDING_CONFIG[options.tick_size],
        )

        data = OrderData(
            maker=self.funder,
            taker=order_args.taker,
            tokenId=order_args.token_id,
            makerAmount=str(maker_amount),
            takerAmount=str(taker_amount),
            side=side,
            feeRateBps=str(order_args.fee_rate_bps),
            nonce=str(order_args.nonce),
            signer=self.signer.address(),
            expiration="0",
            signatureType=self.sig_type,
        )

        contract_config = get_contract_config(
            self.signer.get_chain_id(), options.neg_risk
        )

        order_builder = UtilsOrderBuilder(
            contract_config.exchange,
            self.signer.get_chain_id(),
            UtilsSigner(key=self.signer.private_key),
        )

        return order_builder.build_signed_order(data)

    def calculate_buy_market_price(
        self,
        positions: list[OrderSummary],
        amount_to_match: float,
        order_type: OrderType,
    ) -> float:
        if not positions:
            raise Exception("no match")

        sum = 0
        for p in reversed(positions):
            sum += float(p.size) * float(p.price)
            if sum >= amount_to_match:
                return float(p.price)

        if order_type == OrderType.FOK:
            raise Exception("no match")

        return float(positions[0].price)

    def calculate_sell_market_price(
        self,
        positions: list[OrderSummary],
        amount_to_match: float,
        order_type: OrderType,
    ) -> float:
        if not positions:
            raise Exception("no match")

        sum = 0
        for p in reversed(positions):
            sum += float(p.size)
            if sum >= amount_to_match:
                return float(p.price)

        if order_type == OrderType.FOK:
            raise Exception("no match")

        return float(positions[0].price)


    def create_market_order_data(
        self, order_args: MarketOrderArgs, options: CreateOrderOptions
    ) -> OrderData:
        """
        Creates order data without signing (for MPC integration)
        """
        side, maker_amount, taker_amount = self.get_market_order_amounts(
            order_args.side,
            order_args.amount,
            order_args.price,
            ROUNDING_CONFIG[options.tick_size],
        )

        data = OrderData(
            maker=self.funder,
            taker=order_args.taker,
            tokenId=order_args.token_id,
            makerAmount=str(maker_amount),
            takerAmount=str(taker_amount),
            side=side,
            feeRateBps=str(order_args.fee_rate_bps),
            nonce=str(order_args.nonce),
            signer=self.signer.address(),
            expiration="0",
            signatureType=self.sig_type,
        )
        
        return data

    def create_market_order_hash(
        self, order_args: MarketOrderArgs, options: CreateOrderOptions
    ) -> tuple[OrderData, str]:
        """
        Creates order data and hash without signing (for MPC integration)
        Returns (OrderData, order_hash)
        """
        data = self.create_market_order_data(order_args, options)
        
        contract_config = get_contract_config(
            self.signer.get_chain_id(), options.neg_risk
        )

        # Use the real signer for hash generation (but we won't sign)
        order_builder = UtilsOrderBuilder(
            contract_config.exchange,
            self.signer.get_chain_id(),
            UtilsSigner(key=self.signer.private_key),  # Use real signer
        )

        order = order_builder.build_order(data)
        order_hash = order_builder._create_struct_hash(order)
        
        return data, order_hash

    def create_market_order_data_with_custom_signer(
        self, order_args: MarketOrderArgs, options: CreateOrderOptions, custom_signer: str
    ) -> OrderData:
        """
        Creates order data with a custom signer (for NEAR Chain Signatures integration)
        """
        side_enum, maker_amount, taker_amount = self.get_market_order_amounts(
            order_args.side,
            order_args.amount,
            order_args.price,
            ROUNDING_CONFIG[options.tick_size],
        )
        side = str(side_enum)

        print(f"\n[DEBUG] Valores antes de crear OrderData:")
        print(f"order_args.token_id: {order_args.token_id} (type: {type(order_args.token_id)})")
        print(f"order_args.fee_rate_bps: {order_args.fee_rate_bps} (type: {type(order_args.fee_rate_bps)})")
        print(f"order_args.nonce: {order_args.nonce} (type: {type(order_args.nonce)})")
        print(f"maker_amount: {maker_amount} (type: {type(maker_amount)})")
        print(f"taker_amount: {taker_amount} (type: {type(taker_amount)})")
        print(f"side: {side} (type: {type(side)})")
        print(f"self.sig_type: {self.sig_type} (type: {type(self.sig_type)})")
        print(f"[DEBUG] self.sig_type: {self.sig_type} == EOA? {self.sig_type == EOA}")
        print(f"[DEBUG] EOA value: {EOA}, Type: {type(EOA)}")

        data = OrderData(
            maker=self.funder,
            taker=order_args.taker,
            tokenId=order_args.token_id,
            makerAmount=str(maker_amount),
            takerAmount=str(taker_amount),
            side=side,
            feeRateBps=str(order_args.fee_rate_bps),
            nonce=str(order_args.nonce),
            signer=custom_signer,
            expiration="0",
            signatureType=self.sig_type,
        )
        
        return data

    def create_market_order_hash_with_custom_signer(
        self, order_args: MarketOrderArgs, options: CreateOrderOptions, custom_signer: str
    ) -> tuple[OrderData, str]:
        """
        Creates order data and hash with a custom signer (for NEAR Chain Signatures integration)
        Returns (OrderData, order_hash)
        """
        data = self.create_market_order_data_with_custom_signer(order_args, options, custom_signer)
        
        contract_config = get_contract_config(
            137, options.neg_risk
        )

        # Create a custom OrderBuilder that bypasses signer validation
        class CustomOrderBuilder(UtilsOrderBuilder):
            def _validate_inputs(self, data: OrderData) -> bool:
                # Skip signer validation for MPC integration
                return not (
                    # ensure required values exist
                    data.maker is None
                    or data.tokenId is None
                    or data.makerAmount is None
                    or data.takerAmount is None
                    or data.side is None
                    or data.side not in [BUY, SELL]
                    or not data.feeRateBps.isnumeric()
                    or int(data.feeRateBps) < 0
                    or not data.nonce.isnumeric()
                    or int(data.nonce) < 0
                    or not data.expiration.isnumeric()
                    or int(data.expiration) < 0
                    or data.signatureType is None
                    or data.signatureType not in [EOA, POLY_GNOSIS_SAFE, POLY_PROXY]
                )
            
            def build_order(self, data: OrderData) -> Order:
                """
                Builds an order without signer validation
                """
                if not self._validate_inputs(data):
                    raise ValidationException("Invalid order inputs")

                if data.signer is None:
                    data.signer = data.maker

                # Skip signer validation for MPC integration
                # if data.signer != self.signer.address():
                #     raise ValidationException("Signer does not match")

                if data.expiration is None:
                    data.expiration = "0"

                if data.signatureType is None:
                    data.signatureType = EOA

                return Order(
                    salt=int(self.salt_generator()),
                    maker=normalize_address(data.maker),
                    signer=normalize_address(data.signer),
                    taker=normalize_address(data.taker),
                    tokenId=int(data.tokenId),
                    makerAmount=int(data.makerAmount),
                    takerAmount=int(data.takerAmount),
                    expiration=int(data.expiration),
                    nonce=int(data.nonce),
                    feeRateBps=int(data.feeRateBps),
                    side=int(data.side),
                    signatureType=int(data.signatureType),
                )

        # Use the custom order builder
        order_builder = CustomOrderBuilder(
            contract_config.exchange,
            self.signer.get_chain_id(),
            UtilsSigner(key=self.signer.private_key),
        )

        print(f"\n[DEBUG] OrderData antes de build_order:")
        print(f"maker: {data.maker}")
        print(f"taker: {data.taker}")
        print(f"tokenId: {data.tokenId}")
        print(f"makerAmount: {data.makerAmount}")
        print(f"takerAmount: {data.takerAmount}")
        print(f"side: {data.side}")
        print(f"feeRateBps: {data.feeRateBps}")
        print(f"nonce: {data.nonce}")
        print(f"signer: {data.signer}")
        print(f"expiration: {data.expiration}")
        print(f"signatureType: {data.signatureType}")

        print(f"[VAL] feeRateBps valid? {data.feeRateBps.isnumeric()}")
        print(f"[VAL] nonce valid? {data.nonce.isnumeric()}")
        print(f"[VAL] expiration valid? {data.expiration.isnumeric()}")
        print(f"[VAL] signatureType valid? {data.signatureType} in {[EOA, POLY_GNOSIS_SAFE, POLY_PROXY]}")
        print(f"[VAL] side valid? {data.side} in {[BUY, SELL]}")
        order = order_builder.build_order(data)
        order_hash = order_builder._create_struct_hash(order)
        
        return data, order_hash

    def create_signed_order_from_signature(
        self, order_data: OrderData, signature: str, chain_id: int, neg_risk: bool = False
    ) -> SignedOrder:
        """
        Creates a SignedOrder from OrderData and signature (r, s, v)
        """
        contract_config = get_contract_config(chain_id, neg_risk)
        
        # Use the real signer to pass validation, but we won't use it for signing
        # since we already have the signature
        order_builder = UtilsOrderBuilder(
            contract_config.exchange,
            chain_id,
            UtilsSigner(key=self.signer.private_key),  # Use real signer for validation
        )

        order = order_builder.build_order(order_data)
        
        # Create SignedOrder manually with the provided signature
        from py_order_utils.model import SignedOrder
        return SignedOrder(order=order, signature=signature)

    def create_signed_order_from_signature_with_custom_signer(
        self, order_data: OrderData, signature: str, chain_id: int, neg_risk: bool = False
    ) -> SignedOrder:
        """
        Creates a SignedOrder from OrderData and signature with custom signer (for NEAR Chain Signatures)
        """
        contract_config = get_contract_config(chain_id, neg_risk)
        
        # Create a temporary signer that matches the custom signer address
        # This is needed to pass validation in the OrderBuilder
        temp_signer = UtilsSigner(key=self.signer.private_key)
        
        order_builder = UtilsOrderBuilder(
            contract_config.exchange,
            chain_id,
            temp_signer,
        )

        order = order_builder.build_order(order_data)
        
        # Create SignedOrder manually with the provided signature
        from py_order_utils.model import SignedOrder
        return SignedOrder(order=order, signature=signature)
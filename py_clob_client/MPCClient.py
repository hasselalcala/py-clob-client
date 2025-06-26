from .clob_types import ApiCreds, MarketOrderArgs, PartialCreateOrderOptions, CreateOrderOptions, OrderType, TickSize, OrderBookSummary, RequestArgs
from .MPCSigner import MPCSigner
from .order_builder.MPCBuilder import MPCOrderBuilder
from .constants import L0, L1, L2, L1_AUTH_UNAVAILABLE, L2_AUTH_UNAVAILABLE
import logging
from .headers.MPCheaders import create_level_1_headers, create_level_2_headers
from .endpoints import CREATE_API_KEY, DERIVE_API_KEY, GET_NEG_RISK, GET_TICK_SIZE, GET_ORDER_BOOK, POST_ORDER
from .http_helpers.helpers import post, get
from .exceptions import PolyException
from typing import Optional
from .utilities import price_valid, is_tick_size_smaller, parse_raw_orderbook_summary, order_to_json

class MPCClobClient:
    def __init__(
        self,
        host,
        chain_id: int = None,
        signature_type: int = None, # Search in the code how to define this data because it will always be EOA and the credentials will not be sent because they must always be calculated
        funder: str = None, # define the funder as the OTA account
        agent_account: str = None,
        agent_private_key: str = None,
        agent_near_network: str = None,
        path: str = None,
    ):
        """
        Initializes the clob client
        The client can be started in 3 modes:
        1) Level 0: Requires only the clob host url
                    Allows access to open CLOB endpoints

        2) Level 1: Requires the host, chain_id and a private key.
                    Allows access to L1 authenticated endpoints + all unauthenticated endpoints

        3) Level 2: Requires the host, chain_id, a private key, and Credentials.
                    Allows access to all endpoints
        """
        self.host = host[0:-1] if host.endswith("/") else host
        self.chain_id = chain_id
        self.creds = None
        
        # Debug
        # print(f"Debug - agent_account: {agent_account}")
        # print(f"Debug - agent_private_key: {'SET' if agent_private_key else 'NOT SET'}")
        # print(f"Debug - agent_near_network: {agent_near_network}")
        # print(f"Debug - path: {path}")
        
        self.mpc_signer = MPCSigner(
            agent_account, 
            agent_private_key, 
            agent_near_network, 
            funder,  # ota_account
            chain_id,  # add chain_id
            path  # add path
        ) if agent_account and agent_private_key and agent_near_network and path else None
        # print(f"Debug - mpc_signer created: {self.mpc_signer is not None}")
        
        self.mode = self._get_client_mode()
        # print(f"Debug - mode: {self.mode}")

        if self.mpc_signer:
            self.builder = MPCOrderBuilder(
                self.mpc_signer, sig_type=signature_type, funder=funder
            )

        # local cache
        self.__tick_sizes = {}
        self.__neg_risk = {}

        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_client_mode(self):
        if self.mpc_signer is not None and self.creds is not None:
            return L2
        if self.mpc_signer is not None:
            return L1
        return L0
    
    async def create_or_derive_api_creds(self, nonce: int = None) -> ApiCreds:
        """
        Creates API creds if not already created for nonce, otherwise derives them
        """
        try:
            return await self.create_api_key(nonce)
        except:
            return await self.derive_api_key(nonce)
    
    async def create_api_key(self, nonce: int = None) -> ApiCreds:
        """
        Creates a new CLOB API key for the given
        """
        self.assert_level_1_auth()

        endpoint = "{}{}".format(self.host, CREATE_API_KEY)
        headers = await create_level_1_headers(self.mpc_signer, nonce)
        #print("\nDebug - Headers created successfully creating a key")

        creds_raw = post(endpoint, headers=headers)
        #print("\nDebug - Creds raw when creating a key: ", creds_raw)
        try:
            creds = ApiCreds(
                api_key=creds_raw["apiKey"],
                api_secret=creds_raw["secret"],
                api_passphrase=creds_raw["passphrase"],
            )
        except:
            self.logger.error("Couldn't parse created CLOB creds")
            return None
        return creds
    
    def assert_level_1_auth(self):
        """
        Level 1 Poly Auth
        """

        if self.mode < L1:
            raise PolyException(L1_AUTH_UNAVAILABLE)
        
    async def derive_api_key(self, nonce: int = None) -> ApiCreds:
        """
        Derives an already existing CLOB API key for the given address and nonce
        """
        self.assert_level_1_auth()

        endpoint = "{}{}".format(self.host, DERIVE_API_KEY)
        headers = await create_level_1_headers(self.mpc_signer, nonce)
        #print("\nDebug - Headers created successfully deriving a key")

        creds_raw = get(endpoint, headers=headers)
        #print("\nDebug - Creds raw when deriving a key: ", creds_raw)
        try:
            creds = ApiCreds(
                api_key=creds_raw["apiKey"],
                api_secret=creds_raw["secret"],
                api_passphrase=creds_raw["passphrase"],
            )
        except:
            self.logger.error("Couldn't parse derived CLOB creds")
            return None
        return creds
    
    def set_api_creds(self, creds: ApiCreds):
        """
        Sets client api creds
        """
        self.creds = creds
        self.mode = self._get_client_mode()

    async def create_market_order(
        self,
        order_args: MarketOrderArgs,
        options: Optional[PartialCreateOrderOptions] = None,
    ):
        """
        Creates and signs an order
        Level 1 Auth required
        """
        self.assert_level_1_auth()

        # add resolve_order_options, or similar
        tick_size = self.__resolve_tick_size(
            order_args.token_id,
            options.tick_size if options else None,
        )

        if order_args.price is None or order_args.price <= 0:
            order_args.price = self.calculate_market_price(
                order_args.token_id,
                order_args.side,
                order_args.amount,
                order_args.order_type,
            )

        if not price_valid(order_args.price, tick_size):
            raise Exception(
                "price ("
                + str(order_args.price)
                + "), min: "
                + str(tick_size)
                + " - max: "
                + str(1 - float(tick_size))
            )

        neg_risk = (
            options.neg_risk
            if options and options.neg_risk
            else self.get_neg_risk(order_args.token_id)
        )
        
        return await self.builder.create_market_order(
            order_args,
            CreateOrderOptions(
                tick_size=tick_size,
                neg_risk=neg_risk,
            ),
        )

    def __resolve_tick_size(
        self, token_id: str, tick_size: TickSize = None
    ) -> TickSize:
        min_tick_size = self.get_tick_size(token_id)
        if tick_size is not None:
            if is_tick_size_smaller(tick_size, min_tick_size):
                raise Exception(
                    "invalid tick size ("
                    + str(tick_size)
                    + "), minimum for the market is "
                    + str(min_tick_size),
                )
        else:
            tick_size = min_tick_size
        return tick_size    
    
    def calculate_market_price(
        self, token_id: str, side: str, amount: float, order_type: OrderType
    ) -> float:
        """
        Calculates the matching price considering an amount and the current orderbook
        """
        book = self.get_order_book(token_id)
        if book is None:
            raise Exception("no orderbook")
        if side == "BUY":
            if book.asks is None:
                raise Exception("no match")
            return self.builder.calculate_buy_market_price(
                book.asks, amount, order_type
            )
        else:
            if book.bids is None:
                raise Exception("no match")
            return self.builder.calculate_sell_market_price(
                book.bids, amount, order_type
            )
        

    def get_neg_risk(self, token_id: str) -> bool:
        if token_id in self.__neg_risk:
            return self.__neg_risk[token_id]

        result = get("{}{}?token_id={}".format(self.host, GET_NEG_RISK, token_id))
        self.__neg_risk[token_id] = result["neg_risk"]

        return result["neg_risk"] 

    def get_tick_size(self, token_id: str) -> TickSize:
        if token_id in self.__tick_sizes:
            return self.__tick_sizes[token_id]

        result = get("{}{}?token_id={}".format(self.host, GET_TICK_SIZE, token_id))
        self.__tick_sizes[token_id] = str(result["minimum_tick_size"])

        return self.__tick_sizes[token_id]
    
    def get_order_book(self, token_id) -> OrderBookSummary:
        """
        Fetches the orderbook for the token_id
        """
        raw_obs = get("{}{}?token_id={}".format(self.host, GET_ORDER_BOOK, token_id))
        return parse_raw_orderbook_summary(raw_obs)
    
    def post_order(self, order, orderType: OrderType = OrderType.GTC):
        """
        Posts the order
        """
        self.assert_level_2_auth()
        body = order_to_json(order, self.creds.api_key, orderType)
        headers = create_level_2_headers(
            self.mpc_signer.ota_account,
            self.creds,
            RequestArgs(method="POST", request_path=POST_ORDER, body=body),
        )
        return post("{}{}".format(self.host, POST_ORDER), headers=headers, data=body)

    def assert_level_2_auth(self):
        """
        Level 2 Poly Auth
        """
        if self.mode < L2:
            raise PolyException(L2_AUTH_UNAVAILABLE)
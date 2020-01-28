import asyncio
import logging
import os

from typing import (Any, Dict, List)

import aiohttp
import json
import jwt


log_format = '%(asctime)s.%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s'
Response = Dict[str, Any]


class OceanException(Exception):
    def __init__(self, msg):
        super().__init__(msg)


class OceanClient:
    '''
    Client based on asyncio.
    '''
    _logger = None

    @classmethod
    def logger(cls):
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, uid: str = None, private_key_file: str = None):
        self._api_base_url: str = os.environ.get('ocean_http_api_base_url',
                                                 'https://api.oceanex.pro/v1')
        self._session: aiohttp.ClientSession = None
        self._auth: Dict[str, Any] = None

        self._rate_limit_breaches: int = 0

        self._init_auth(uid, private_key_file)
        self.logger().debug(f"create client: api_base_url={self._api_base_url}")

    async def init(self):
        '''
        Must be awaited after creating instance to create aiohttp.ClientSession
        '''
        if self._session:
            return self._session
        self._session = aiohttp.ClientSession()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()

    async def __aenter__(self):
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_value, exc_traceback):
        self.close()

    def _init_auth(self, uid: str, private_key_file: str):
        if not uid and ('ocean_uid' in os.environ):
            uid = os.environ['ocean_uid']
        if not private_key_file and ('ocean_private_key_file' in os.environ):
            private_key_file = os.environ['ocean_private_key_file']

        if (not uid) or (not private_key_file):
            self.logger().warning("no authorization info for private apis")
            return
        self.logger().debug(f"uid={uid} "
                            f" private_key_file={private_key_file}")

        with open(private_key_file) as infile:
            private_key = infile.read()

        self._auth = {
            "uid": uid,
            "private_key": private_key
        }

    def _encode_request_body(self, body={}):
        if not self._auth:
            raise OceanException('no authorization info for private api')

        pay_load = {
            "uid": self._auth['uid'],
            "data": body
        }

        jwt_token: bytes = jwt.encode(pay_load, self._auth['private_key'],
                                      algorithm="RS256")
        # jwt.encode returns bytes in python3 instead of str as in python2
        jwt_token = jwt_token.decode('utf-8')
        encoded_body = {
            "user_jwt": jwt_token
        }
        return encoded_body

    def close(self):
        '''
        Must be called after use to close session.
        '''
        if self._session is not None:
            asyncio.ensure_future(self._session.close())

    def set_api_base_url(self, url: str):
        self._api_base_url = url
        self.logger().info(f"set api base url to {self._api_base_url}")

    def _create_api_url(self, path: str) -> str:
        url = self._api_base_url + f"/{path}"
        return url

    async def _get(self, url: str, params: Dict[str, Any] = None,
                   data = None) -> Response:
        self.logger().debug(f"get url={url} params = {params} data = {data}")
        async with self._session.get(url, params=params, data=data) as resp:
            if logging.DEBUG == self.logger().getEffectiveLevel():
                resp_text = await resp.text()
                self.logger().debug(f"response: status={resp.status}, {resp_text}")
            if resp.status != 200:
                await self._generate_request_error(url, resp)
            return await resp.json()

    async def _post_no_retry(self, url: str, params: Dict[str, Any] = None,
                             data = None) -> Response:
        self.logger().debug(f"post url={url} params = {params} data = {data}")
        async with self._session.post(url, params=params, data=data) as resp:
            if logging.DEBUG == self.logger().getEffectiveLevel():
                resp_text = await resp.text()
                self.logger().debug(f"response: status={resp.status}, {resp_text}")
            if resp.status != 200 and resp.status != 201:
                await self._generate_request_error(url, resp)
            return await resp.json()

    async def _post(self, url: str, params: Dict[str, Any] = None,
                    data = None) -> Response:
        '''
        Subsequent rate limit breaches cause longer wait times.
        '''
        max_attempts = 10
        attempts = 0
        wait = 2  # seconds
        rate_limit_breached = True
        while rate_limit_breached and attempts < max_attempts:
            resp = await self._post_no_retry(url, params, data)
            attempts += 1
            rate_limit_breached = self.get_rate_limit_breached(resp)
            if rate_limit_breached:
                self._rate_limit_breaches += 1
                msg = f"rate limit breached, wait {wait} seconds, "
                msg += f"url={url} , params = {params} , data = {data}"
                self.logger().warning(msg)
                await asyncio.sleep(wait)
                wait *= 2
            else:
                return resp

        if attempts >= max_attempts:
            msg = f"exhausted {max_attempts} attempts to overcome rate limit"
            msg += " , url={url} params={params} data={data}"
            raise OceanException(msg)

    @classmethod
    def get_rate_limit_breached(cls, resp: Dict[str, Any]):
        if -2 != resp['code']:
            return False
        try:
            msg = json.loads(resp['message'])
            if 'error' in msg:
                error = msg['error']
                if 2002 == error['code']:
                    reason = error['message']
                    # new order exceeded rate limit
                    if 'Exceeding request Limit' in reason:
                        return True
        except Exception as e:
            cls.logger().error(f"failed to decode: response = {resp} , exception = {repr(e)}")
            return False
        return False

    @classmethod
    async def _generate_request_error(cls, url, resp):
        msg = f"error fetching {url}, status={resp.status}, "
        try:
            body = await resp.json()
            msg += f"body = {body}"
        except Exception as e:
            msg += f"failed to decode body exception = {e}"
        raise OceanException(msg)

    async def get_markets(self) -> Response:
        '''
        Get available markets for trading.
        '''
        url = self._create_api_url('markets')
        resp = await self._get(url)
        return resp

    async def _get_markets_details(self) -> Response:
        '''
        For internal use.
        '''
        url = self._create_api_url('markets')
        params = {'show_details': 'true'}
        resp = await self._get(url, params)
        return resp

    async def get_tickers(self, symbol: str) -> Response:
        '''
        Get tickers for given symbol.
        '''
        url = self._create_api_url('tickers') + f"/{symbol}"
        resp = await self._get(url)
        return resp

    async def get_tickers_multi(self, symbols: List[str]) -> Response:
        '''
        Get tickers for given symbols.
        '''
        url = self._create_api_url('tickers_multi')
        data = {
            "markets[]": symbols
        }
        resp = await self._post(url, data=data)
        return resp

    async def get_all_tickers(self) -> Response:
        '''
        Get tickers for all symbols.
        '''
        url = self._create_api_url('tickers')
        resp = await self._get(url)
        return resp

    async def get_order_book(self, symbol: str, limit: int = 300) -> Response:
        '''
        Get book with limit levels. Default limit is 300.
        '''
        url = self._create_api_url('order_book')
        params = {
            'market': symbol,
            'limit': limit
        }
        resp = await self._get(url, params)
        return resp

    async def get_multiple_order_books(self, symbols: List[str],
                                       limit: int = 300) -> Response:
        '''
        Get books with limit levels. Default limit is 300.
        '''
        url = self._create_api_url('order_book/multi')
        body = {
            'markets[]': symbols,
            'limit': limit
        }
        resp = await self._post(url, data=body)
        return resp

    async def get_trades(self, **params):
        '''
        :param market: required
        :type market: str
        :param limit: number of trades, default 300
        :type limit: int
        :param start: trades created after are returned
        :type start: int

        :returns: API response
        '''
        self.logger().info('get trades')
        url = self._create_api_url('trades')
        resp = await self._get(url, params=params)
        return resp

    async def get_kline(self, **params):
        url = self._create_api_url('k')
        resp = await self._get(url, params=params)
        return resp

    async def get_trading_fees(self):
        url = self._create_api_url('fees/trading')
        resp = await self._get(url)
        return resp

    async def get_server_time(self):
        url = self._create_api_url('timestamp')
        resp = await self._get(url)
        return resp

    async def get_key(self):
        url = self._create_api_url('key')
        body = self._encode_request_body()
        resp = await self._get(url, data=body)
        return resp

    async def get_account_info(self):
        url = self._create_api_url('members/me')
        body = self._encode_request_body()
        resp = await self._get(url, data=body)
        return resp

    async def create_order(self, **params):
        url = self._create_api_url('orders')
        body = self._encode_request_body(params)
        resp = await self._post(url, data=body)
        return resp

    async def create_multiple_orders(self, symbol: str,
                                     orders: List[Dict[str, Any]]):
        '''
        For one symbol.
        '''
        url = self._create_api_url('orders/multi')
        data = {
            "market": symbol,
            "orders": orders
        }
        data = self._encode_request_body(data)
        resp = await self._post(url, data=data)
        return resp

    async def get_order_status(self, order_ids: List[int]):
        url = self._create_api_url('orders')
        params = {'ids': order_ids}
        data = self._encode_request_body(params)
        resp = await self._get(url, data=data)
        return resp

    async def get_order_status_filtered(self, **params):
        url = self._create_api_url('orders/filter')
        data = self._encode_request_body(params)
        resp = await self._get(url, data=data)
        return resp

    async def cancel_order(self, order_id: int):
        url = self._create_api_url('order/delete')
        data = {'id': order_id}
        data = self._encode_request_body(data)
        resp = await self._post(url, data=data)
        return resp

    async def cancel_multiple_orders(self, order_ids: List[int]):
        url = self._create_api_url('order/delete/multi')
        data = {'ids': order_ids}
        data = self._encode_request_body(data)
        resp = await self._post(url, data=data)
        return resp

    async def cancel_all_orders(self):
        url = self._create_api_url('orders/clear')
        data = self._encode_request_body()
        resp = await self._post(url, data=data)
        return resp

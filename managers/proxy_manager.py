import aiohttp
from aiohttp_proxy import ProxyConnector, ProxyType
from managers.base import BaseSingletonClass


from config import CONFIG_PROXY


class ProxyManager(BaseSingletonClass):
    """ Класс для выбора и проверки работоспособности прокси """

    async def __call__(self, session_data: dict) -> dict | bool:
        proxy = await self.get_proxy(session_data)
        return await self.check_proxi(proxy)

    @staticmethod
    async def get_proxy(session_data):
        """ Возвращает прокси из config если указан или из данных сессии """
        proxy = CONFIG_PROXY
        if not proxy:
            sd_proxy = session_data.get('proxy')
            proxy = {
                'proxy_type': ProxyType.SOCKS5,
                'addr': sd_proxy[1],
                'port': sd_proxy[2],
                'rdns': sd_proxy[3],
                'username': sd_proxy[4],
                'password': sd_proxy[5],
            }
        return proxy

    @staticmethod
    async def check_proxi(proxy):
        return proxy

    async def failed_check_proxi(self, proxy):
        """ Проверяет доступ к прокси """
        url = 'https://check-host.net/ip'
        connector = ProxyConnector(
            proxy_type=proxy.get('proxy_type'),
            host=proxy.get('addr'),
            port=proxy.get('port'),
            username=proxy.get('username'),
            password=proxy.get('password'),
        )

        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.get(url, ssl=False, timeout=10) as response:
                    if response.content_type in ['text/html', 'text/plain']:
                        result = {'response': await response.text()}
                    else:
                        result = {'response': str(await response.json())}
            except Exception as exc:
                result = {'response': str(exc)}
        print(result)
        if result.get('response') == proxy.get('addr'):
            self.logger.debug(self.sign + f'GOOD PROXI {proxy=}')
            return proxy

        self.logger.warning(self.sign + f'ERROR PROXI {proxy=}')
        return False

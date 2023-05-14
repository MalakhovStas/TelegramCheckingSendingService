import asyncio
import time

import aiohttp
from aiohttp_proxy import ProxyConnector, ProxyType

from config import CONFIG_PROXY
from managers.base import BaseSingletonClass


class ProxyManager(BaseSingletonClass):
    """ Класс для выбора и проверки работоспособности прокси """

    async def __call__(self, session_data: dict) -> dict | bool:
        proxy = await self.get_proxy(session_data)
        return proxy

    async def get_proxy(self, session_data):
        """ Возвращает прокси из config если указан или из данных сессии """
        proxy = CONFIG_PROXY
        data = {'last_ip': None, 'change_time': None}
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
        else:
            check = 'start'
            while check != 'stop':
                response = (await self.failed_check_proxi(proxy)).get('response')
                if not str(response).replace('.', '').isdigit():
                    self.logger.warning(self.sign + f'{response=}')
                    continue
                if data.get('last_ip') and response != data.get('last_ip'):
                    data['last_ip'] = response
                    data['change_time'] = int(time.time())
                    check = 'stop'
                else:
                    data['last_ip'] = response
                    await asyncio.sleep(5)
                msg = self.sign + f'ip: {response} | tm: {data.get("change_time")}'
                self.logger.debug(msg) if check != 'stop' else self.logger.info(msg)
        return proxy

    async def failed_check_proxi(self, proxy):
        """ Проверяет доступ к прокси """
        url = 'https://check-host.net/ip'
        connector = ProxyConnector(
            # proxy_type=proxy.get('proxy_type'),
            proxy_type=ProxyType.SOCKS5,
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
        return result


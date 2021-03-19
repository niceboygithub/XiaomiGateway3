import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow, ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.network import is_ip_address
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME, CONF_TOKEN

from . import DOMAIN
from .core import gateway3
from .core.gateway3 import TELNET_CMD
from .core.xiaomi_cloud import MiCloud

_LOGGER = logging.getLogger(__name__)

ACTIONS = {
    'cloud': "Add Mi Cloud Account",
    'token': "Add Gateway using Token",
    'aqara': "Add Aqara Gateway/Hub"
}

SERVERS = {
    'cn': "China",
    'de': "Europe",
    'i2': "India",
    'ru': "Russia",
    'sg': "Singapore",
    'us': "United States"
}

OPT_DEBUG = {
    'true': "Basic logs",
    'miio': "miIO logs",
    'mqtt': "MQTT logs"
}
OPT_PARENT = {
    -1: "Disabled", 0: "Manually", 60: "Hourly"
}
OPT_MODE = {
    False: "Mi/Aqara Home", True: "Zigbee Home Automation (ZHA)"
}

OPT_DEVICE_NAME = {
    'g2h': "Aqara Camera Hub G2H",
    'm1s': "Aqara Gateway M1S",
    'm2': "Aqara Gateway M2"
}


class XiaomiGateway3FlowHandler(ConfigFlow, domain=DOMAIN):
    cloud = None

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            if user_input['action'] == 'cloud':
                return await self.async_step_cloud()
            elif user_input['action'] == 'token':
                return await self.async_step_token()
            elif user_input['action'] == 'aqara':
                return await self.async_step_aqara()
            else:
                device = next(d for d in self.hass.data[DOMAIN]['devices']
                              if d['did'] == user_input['action'])
                return self.async_show_form(
                    step_id='token',
                    data_schema=vol.Schema({
                        vol.Required('host', default=device['localip']): str,
                        vol.Required('token', default=device['token']): str,
                        vol.Required('telnet_cmd', default=TELNET_CMD): str,
                    }),
                )

        if DOMAIN in self.hass.data and 'devices' in self.hass.data[DOMAIN]:
            for device in self.hass.data[DOMAIN]['devices']:
                if (device['model'] == 'lumi.gateway.mgl03' and
                        device['did'] not in ACTIONS):
                    name = f"Add {device['name']} ({device['localip']})"
                    ACTIONS[device['did']] = name

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required('action', default='cloud'): vol.In(ACTIONS)
            })
        )

    async def async_step_cloud(self, user_input=None, error=None):
        if user_input:
            if not user_input['servers']:
                return await self.async_step_cloud(error='no_servers')

            session = async_create_clientsession(self.hass)
            cloud = MiCloud(session)
            if await cloud.login(user_input[CONF_USERNAME],
                                 user_input[CONF_PASSWORD]):
                user_input.update(cloud.auth)
                return self.async_create_entry(title=user_input[CONF_USERNAME],
                                               data=user_input)

            else:
                return await self.async_step_cloud(error='cant_login')

        return self.async_show_form(
            step_id='cloud',
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required('servers', default=['cn']):
                    cv.multi_select(SERVERS)
            }),
            errors={'base': error} if error else None
        )

    async def async_step_token(self, user_input=None, error=None):
        """GUI > Configuration > Integrations > Plus > Xiaomi Gateway 3"""
        if user_input is not None:
            error = gateway3.check_mgl03(**user_input)
            if error:
                return await self.async_step_token(error=error)

            return self.async_create_entry(title=user_input['host'],
                                           data=user_input)

        return self.async_show_form(
            step_id='token',
            data_schema=vol.Schema({
                vol.Required('host'): str,
                vol.Required('token'): str,
                vol.Required('telnet_cmd', default=TELNET_CMD): str,
            }),
            errors={'base': error} if error else None
        )

    async def async_step_aqara(self, user_input=None, error=None):
        """ for Aqara Gateway """
        ret = {}
        ret['status'] = None
        if user_input is not None:
            if not is_ip_address(user_input[CONF_HOST]):
                return self.async_abort(reason="cant_connect")
            ret = gateway3.is_aqaragateway(user_input[CONF_HOST],
                                           user_input.get(CONF_PASSWORD, ''),
                                           user_input['device_name'])
            if 'error' in ret['status']:
                return self.async_abort(reason="cant_connect")
            user_input[CONF_TOKEN] = ''
            return self.async_create_entry(title=ret['name'],
                                           data=user_input)

        return self.async_show_form(
            step_id='aqara',
            description_placeholders={CONF_NAME: 'Aqara Gateway/Hub'},
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Required('device_name', default=['m2']): vol.In(
                    OPT_DEVICE_NAME
                ),
            }),
            errors={'base': ret['status']} if ret['status'] else None
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry):
        return OptionsFlowHandler(entry)

    async def async_step_discovery_confirm(self, user_input=None):
        """Handle user-confirmation of discovered node."""

        if user_input is not None:
            return await self._async_add(user_input)

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"name": self._name,
                                      "device_info": self._device_info}
        )

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType):
        """Handle zeroconf discovery."""
        # Hostname is format: _aqara._tcp.local., _aqara-setup._tcp.local.
        if discovery_info.get('type') == '_aqara-setup._tcp.local.':
            self._host = discovery_info["properties"].get(
                "address", discovery_info[CONF_HOST])
            local_name = discovery_info["hostname"][:-1]
            self._name = local_name[: -len(".local")]
            user_input = {}
            user_input[CONF_HOST] = self._host
            user_input['action'] = 'aqara'
            return await self.async_step_user(user_input=user_input)

class OptionsFlowHandler(OptionsFlow):
    def __init__(self, entry: ConfigEntry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        if 'servers' in self.entry.data:
            return await self.async_step_cloud()
        elif 'device_name' in self.entry.data:
            return await self.async_step_aqara()
        else:
            return await self.async_step_user()

    async def async_step_cloud(self, user_input=None):
        if user_input is not None:
            did = user_input['did']
            device = next(d for d in self.hass.data[DOMAIN]['devices']
                          if d['did'] == did)
            device_info = (
                f"Name: {device['name']}\n"
                f"Model: {device['model']}\n"
                f"IP: {device['localip']}\n"
                f"MAC: {device['mac']}\n"
                f"Token: {device['token']}"
            )
            if device['model'] == 'lumi.gateway.v3':
                device_info += "\nLAN key: " + gateway3.get_lan_key(device)

        elif not self.hass.data[DOMAIN].get('devices'):
            device_info = "No devices in account"
        else:
            # noinspection SqlResolve
            device_info = "SELECT device FROM list"

        devices = {
            device['did']: f"{device['name']} ({device['localip']})"
            for device in self.hass.data[DOMAIN].get('devices', [])
            # 0 - wifi, 8 - wifi+ble
            if device['pid'] in ('0', '8')
        }

        return self.async_show_form(
            step_id="cloud",
            data_schema=vol.Schema({
                vol.Required('did'): vol.In(devices)
            }),
            description_placeholders={
                'device_info': device_info
            }
        )

    async def async_step_user(self, user_input=None):
        if user_input:
            return self.async_create_entry(title='', data=user_input)

        host = self.entry.options['host']
        token = self.entry.options['token']
        telnet_cmd = self.entry.options.get('telnet_cmd', '')
        ble = self.entry.options.get('ble', True)
        stats = self.entry.options.get('stats', False)
        debug = self.entry.options.get('debug', [])
        buzzer = self.entry.options.get('buzzer', False)
        parent = self.entry.options.get('parent', -1)
        zha = self.entry.options.get('zha', False)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required('host', default=host): str,
                vol.Required('token', default=token): str,
                vol.Optional('telnet_cmd', default=telnet_cmd): str,
                vol.Required('ble', default=ble): bool,
                vol.Required('stats', default=stats): bool,
                vol.Optional('debug', default=debug): cv.multi_select(
                    OPT_DEBUG
                ),
                vol.Optional('buzzer', default=buzzer): bool,
                vol.Optional('parent', default=parent): vol.In(OPT_PARENT),
                vol.Required('zha', default=zha): vol.In(OPT_MODE),
            }),
        )


    async def async_step_aqara(self, user_input=None):
        """ Option flow for aqara gateway """
        if user_input:
            user_input[CONF_TOKEN] = ''
            return self.async_create_entry(title='', data=user_input)

        host = self.entry.options[CONF_HOST]
        password = self.entry.options.get(CONF_PASSWORD, '')
        device_name = self.entry.options.get('device_name', '')
        stats = self.entry.options.get('stats', False)
        debug = self.entry.options.get('debug', [])
        parent = self.entry.options.get('parent', -1)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=host): str,
                vol.Optional(CONF_PASSWORD, default=password): str,
                vol.Required('stats', default=stats): bool,
                vol.Optional('device_name', default=device_name): vol.In(
                    OPT_DEVICE_NAME
                ),
                vol.Optional('debug', default=debug): cv.multi_select(
                    OPT_DEBUG
                ),
                vol.Optional('parent', default=parent): vol.In(OPT_PARENT),
            }),
        )

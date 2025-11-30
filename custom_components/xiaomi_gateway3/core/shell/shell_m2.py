import asyncio
import re

from .shell_mgw import ShellMGW

import logging

_LOGGER = logging.getLogger(__name__)


class ShellM2(ShellMGW):
    async def login(self):
        self.writer.write(b"admin\n")
        raw = await asyncio.wait_for(self.reader.readuntil(b"\r\n# "), 3)
        _LOGGER.error(f"m2 login {raw}")
        # OK if gateway without password
        if b"Password:" not in raw:
            return
        # check if gateway has default password
        self.writer.write(b"admin\n")
        raw = await asyncio.wait_for(self.reader.readuntil(b"\r\n# "), 3)
        _LOGGER.error(f"m2 login {raw}")
        # can't continue without password
        if b"Password:" in raw:
            raise Exception("Telnet with password don't supported")

    async def get_version(self):
        raw = await self.read_file("/etc/build.prop")
        m = re.search(r"ro.sys.fw_ver=([0-9._]+)", raw.decode())
        return m[1]

    async def get_miio_info(self) -> dict:
        raw = await self.exec("getprop | grep persist")

        m = re.findall(r"([a-z_]+)]: \[(.+?)]", raw)
        props: dict[str, str] = dict(m)

        return {
            "did": props["did"],
            "key": props.get("miio_key"),
            "mac": props["miio_mac"],
            "model": props["model"],
            "token": props["sys_token"],
            "lan_mac": props.get("lan_mac"),
            "version": await self.get_version(),
            "cloud": await self.exec("persist.sys.cloud")
        }
import re

from .shell_e1 import ShellE1
from ..unqlite import SQLite


class ShellM2PoE(ShellE1):
    db: SQLite = None

    async def get_version(self) -> str:
        raw1 = await self.exec("agetprop ro.sys.fw_ver")
        raw2 = await self.exec("agetprop ro.sys.build_num")
        raw3 = await self.exec("agetprop persist.sys.zb_ver")
        return f"{raw1.rstrip()}_{raw2.rstrip()}_{raw3.rstrip()}"

    async def get_miio_info(self) -> dict:
        raw = await self.exec("agetprop | grep persist")

        m = re.findall(r"([a-z_]+)]: \[(.+?)]", raw)
        props: dict[str, str] = dict(m)

        return {
            "did": props.get("miio_did") or "",
            "key": props.get("miio_key") or "",
            "mac": props["miio_mac"],
            "model": props["model"],
            "token": props["sys_token"],
            "lan_mac": props.get("lan_mac"),
            "version": await self.get_version(),
            "cloud": await self.exec("persist.sys.cloud")
        }

    async def read_db_bluetooth(self) -> SQLite:
        if not self.db:
            raw = await self.read_file(
                "/data/local/miio_bt/mible_local.db", as_base64=True
            )
            self.db = SQLite(raw)
        return self.db

    async def read_silabs_devices(self) -> bytes:
        return await self.read_file("/data/zigbee_host/devices.txt")

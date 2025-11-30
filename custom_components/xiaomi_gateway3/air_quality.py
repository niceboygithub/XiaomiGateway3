from homeassistant.components.air_quality import AirQualityEntity
from homeassistant.helpers.typing import StateType

from .hass.entity import XEntity


# noinspection PyUnusedLocal
async def async_setup_entry(hass, entry, async_add_entities) -> None:
    XEntity.ADD[entry.entry_id + "air_quality"] = async_add_entities


class XAirQuality(XEntity, AirQualityEntity):
    _attr_native_value = None

    @property
    def particulate_matter_2_5(self) -> StateType:
        """Return the particulate matter 2.5 level."""
        return None

    @property
    def air_quality_index(self) -> StateType:
        """Return the Air Quality Index (AQI)."""
        return self._attr_native_value

    def set_state(self, data: dict):
        self._attr_native_value = data[self.attr]

    def get_state(self) -> dict:
        return {self.attr: self._attr_native_value}

XEntity.NEW["air_quality"] = XAirQuality

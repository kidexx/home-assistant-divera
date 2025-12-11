"""Entity Module for Divera Integration."""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from dataclasses import dataclass
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DIVERA_BASE_URL, DIVERA_GMBH, DOMAIN
from .coordinator import DiveraCoordinator
from .divera import DiveraClient


@dataclass(frozen=True, kw_only=True)
class DiveraEntityDescription(EntityDescription):
    """Description of a Divera entity.

    Attributes:
        attribute_fn (Callable[[DiveraClient], MutableMapping[str, Any]]):
            Function that returns a mapping of attributes for the entity,
            based on a DiveraClient instance.

    """

    attribute_fn: Callable[[DiveraClient], MutableMapping[str, Any]]
    
class DiveraEntity(CoordinatorEntity):
    def __init__(self, coordinator, description):
        super().__init__(coordinator)
        self.entity_description = description

        data = self.coordinator.data

        # UCR-ID bestimmen
        ucr_id = None
        cluster_name = None

        if isinstance(data, dict):
            # Variante: Coordinator liefert bereits ein Dict
            ucr_id = data.get("ucr_id") or data.get("active_ucr")

            # Cluster-Name, falls im Dict vorhanden
            if ucr_id is not None:
                # je nach Struktur, z.B. data["data"]["cluster"][ucr_id]["name"]
                try:
                    cluster = data.get("data", {}).get("cluster", {})
                    cluster_entry = cluster.get(str(ucr_id)) or cluster.get(int(ucr_id))
                    if cluster_entry:
                        cluster_name = cluster_entry.get("name")
                except Exception:
                    cluster_name = None

        else:
            # Variante: data ist ein DiveraClient
            client = data

            # UCR-ID aus Attributen holen
            if hasattr(client, "active_ucr"):
                ucr_id = getattr(client, "active_ucr")
            elif hasattr(client, "ucr_id"):
                ucr_id = getattr(client, "ucr_id")

            # Cluster-Name aus Datenstruktur ableiten, ohne Methoden aufzurufen
            try:
                raw = getattr(client, "_DiveraClient__data", None) or getattr(client, "data", None)
                if raw and ucr_id is not None:
                    cluster = raw.get("data", {}).get("cluster", {})
                    cluster_entry = cluster.get(str(ucr_id)) or cluster.get(int(ucr_id))
                    if cluster_entry:
                        cluster_name = cluster_entry.get("name")
            except Exception:
                cluster_name = None

        self._ucr_id = ucr_id
        self._cluster_name = cluster_name or "DIVERA"

        self._attr_unique_id = "_".join(
            [
                DOMAIN,
                str(self._ucr_id),
                description.key,
            ]
        )

        self._divera_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._divera_update()
        self.async_write_ha_state()

    def _divera_update(self) -> None:
        raise NotImplementedError

    @property
    def device_info(self) -> DeviceInfo:
        """Device information property.

        Returns:
            DeviceInfo: Device information object.

        """
        # TODO Configuration Url anpassen je nach Divera Server #108
        config_url = DIVERA_BASE_URL
        version = self.coordinator.data.get_cluster_version()
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    str(self._ucr_id),
                )
            },
            manufacturer=DIVERA_GMBH,
            name=self._cluster_name,
            model=version,
            configuration_url=config_url,
        )

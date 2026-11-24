"""Moteur de règles : décide de la position cible et pilote les volets."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TypeAlias, TypedDict

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import *  # noqa: F403
from .const import DEFAULTS, DOMAIN, HEAT_HYSTERESIS

_LOGGER = logging.getLogger(__name__)


class CoordinatorData(TypedDict):
    """Computed target and diagnostic details shared with the entities."""

    target: int | None
    rule: str
    reason: str
    blocked_by: list[str]


CoverManagerConfigEntry: TypeAlias = ConfigEntry["CoverManagerCoordinator"]


class CoverManagerCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Évalue les règles chaque minute et à chaque changement de capteur."""

    def __init__(self, hass: HomeAssistant, entry: CoverManagerConfigEntry) -> None:
        super().__init__(
            hass, _LOGGER, name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=1),
            config_entry=entry,
            always_update=False,
        )
        self.entry = entry
        self.enabled = True

        # États internes conservés entre les évaluations successives.
        # Ils évitent de basculer jour/nuit ou chaleur au moindre bruit de capteur.
        self._day = False
        self._heat = False
        self._since: dict[str, datetime] = {}  # Début des périodes de condition soutenue.
        self._applied: dict[str, int] = {}  # Dernière cible demandée à chaque volet.
        self._unsub = None

    # ------------------------------------------------------------ config
    @property
    def opts(self) -> dict:
        return {**DEFAULTS, **self.entry.data, **self.entry.options}

    @property
    def covers(self) -> list[str]:
        return self.opts.get(CONF_COVERS, [])

    def reset_applied(self) -> None:
        self._applied.clear()

    # --------------------------------------------------------- listeners
    @callback
    def async_start_listeners(self) -> None:
        o = self.opts
        ids = [o.get(CONF_LUX_SENSOR), o.get(CONF_TEMP_SENSOR), *o.get(CONF_WINDOW_SENSORS, [])]
        ids = [i for i in ids if i]
        if ids:
            self._unsub = async_track_state_change_event(self.hass, ids, self._on_change)

    @callback
    def async_stop_listeners(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    @callback
    def _on_change(self, _event) -> None:
        self.hass.async_create_task(self.async_request_refresh())

    # ----------------------------------------------------------- helpers
    def _float(self, entity_id: str | None) -> float | None:
        """Lit un capteur numérique en ignorant les entités absentes ou invalides."""
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        if st is None or st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            return float(st.state)
        except ValueError:
            return None

    def _sustained(self, key: str, cond: bool, minutes: float, now: datetime) -> bool:
        """Vrai si `cond` est vraie depuis au moins `minutes` minutes.

        Chaque clé possède son propre horodatage dans ``_since`` : dès que la
        condition devient fausse, son horodatage est supprimé. Elle doit donc
        rester vraie pendant toute la durée du délai pour être confirmée.
        """
        if not cond:
            self._since.pop(key, None)
            return False
        since = self._since.setdefault(key, now)
        return now - since >= timedelta(minutes=minutes)

    def _windows_open(self) -> list[str]:
        """Retourne les portes ou fenêtres configurées qui sont actuellement ouvertes."""
        return [
            e for e in self.opts.get(CONF_WINDOW_SENSORS, [])
            if (s := self.hass.states.get(e)) and s.state == STATE_ON
        ]

    # ------------------------------------------------------------ règles
    def _evaluate(self) -> tuple[int, str, str]:
        """Évalue l'ensemble de l'algorithme et retourne (position, règle, motif).

        La priorité est la suivante : pause extérieure (traitée avant cet appel),
        plage horaire/nuit, luminosité jour/nuit, puis protection thermique solaire.
        """
        o = self.opts
        now = dt_util.now()
        # Les jours 5 et 6 représentent samedi et dimanche.
        weekend = now.weekday() >= 5

        # Les horaires du week-end remplacent les horaires standard lorsqu'ils
        # sont renseignés ; sinon, on conserve les horaires de semaine.
        open_s = (o.get(CONF_OPEN_TIME_WE) if weekend else None) or o[CONF_OPEN_TIME]
        close_s = (o.get(CONF_CLOSE_TIME_WE) if weekend else None) or o[CONF_CLOSE_TIME]
        open_t, close_t = dt_util.parse_time(open_s), dt_util.parse_time(close_s)
        in_window = open_t <= now.time() < close_t

        # La lumière confirme les transitions jour/nuit après le délai configuré.
        lux = self._float(o.get(CONF_LUX_SENSOR))
        delay = o[CONF_LUX_DELAY]

        # --- Jour / nuit : horaires + luminosité (avec délai et hystérésis)
        reason = ""
        # Hors plage horaire : passage forcé à la nuit et remise à zéro des délais.
        if not in_window:
            self._day = False
            self._since.clear()
            reason = f"hors plage horaire ({open_s[:5]}–{close_s[:5]})"
        elif self._day:
            # Déjà en mode jour : une luminosité basse doit persister pour passer la nuit.
            if lux is not None and self._sustained("dark", lux < o[CONF_LUX_CLOSE], delay, now):
                self._day = False
                reason = f"luminosité < {o[CONF_LUX_CLOSE]} lx depuis {delay:.0f} min"
            else:
                reason = "plage horaire de jour"
        else:
            # Déjà en mode nuit : confirmer un passage au jour.
            # Sans capteur lumineux, la présence dans la plage horaire suffit.
            bright = lux is None or lux > o[CONF_LUX_OPEN]
            if self._sustained("bright", bright, delay if lux is not None else 0, now):
                self._day = True
                reason = "plage horaire de jour" + (
                    f", luminosité > {o[CONF_LUX_OPEN]} lx" if lux is not None else ""
                )
            else:
                reason = "en attente de luminosité suffisante"

        # Un passage nuit remet immédiatement le mode chaleur à zéro : la
        # protection thermique ne peut s'appliquer qu'en période de jour.
        if not self._day:
            self._heat = False
            return 0, RULE_NIGHT, reason

        # --- Chaleur : fermeture partielle si le soleil tape sur la façade
        temp = self._float(o.get(CONF_TEMP_SENSOR))
        sun = self.hass.states.get("sun.sun")
        if temp is not None and sun is not None:
            # L'azimut indique la direction du soleil ; l'élévation détermine sa hauteur.
            az = float(sun.attributes.get("azimuth", 0))
            el = float(sun.attributes.get("elevation", -90))
            lo, hi = o[CONF_AZIMUTH_MIN], o[CONF_AZIMUTH_MAX]
            # La seconde forme gère une plage qui traverse 0°/360°.
            facing = (lo <= az <= hi) if lo <= hi else (az >= lo or az <= hi)
            # Le mode chaleur exige simultanément une température haute, une
            # direction solaire dans la plage de la façade et une élévation suffisante.
            sunny = facing and el >= o[CONF_MIN_ELEVATION]
            # Hystérésis : désactivation à une température plus basse que l'allumage.
            if self._heat:
                self._heat = temp >= o[CONF_HEAT_THRESHOLD] - HEAT_HYSTERESIS
            else:
                self._heat = temp >= o[CONF_HEAT_THRESHOLD]
            # Cette position remplace la position jour normale (100 %) uniquement
            # lorsque toutes les conditions thermiques ci-dessus sont réunies.
            if self._heat and sunny:
                return (
                    int(o[CONF_HEAT_POSITION]), RULE_HEAT,
                    f"{temp:.1f} °C, soleil sur la façade (az {az:.0f}°, élév. {el:.0f}°)",
                )
        # Aucun déclenchement thermique : les volets suivent la règle normale du jour.
        return 100, RULE_DAY, reason

    # ----------------------------------------------------------- action
    async def _async_update_data(self) -> CoordinatorData:
        """Exécute une évaluation complète puis retourne son résultat au sensor."""
        # Retourner None comme cible conserve les volets dans leur position actuelle.
        if not self.enabled:
            return {"target": None, "rule": RULE_PAUSED, "reason": "automatisme en pause",
                    "blocked_by": []}

        # 1. Calcul de la position idéale selon les règles de l'intégration.
        target, rule, reason = self._evaluate()
        # 2. Vérification des protections physiques avant chaque fermeture.
        blocked_by = self._windows_open()
        await self._apply(target, blocked_by)
        return {"target": target, "rule": rule, "reason": reason, "blocked_by": blocked_by}

    async def _apply(self, target: int, windows_open: list[str]) -> None:
        """Applique la cible à chaque volet, après les protections de sécurité."""
        # On n'envoie un ordre que si la cible change : un déplacement manuel
        # reste donc respecté jusqu'au prochain changement de règle.
        for eid in self.covers:
            if self._applied.get(eid) == target:
                continue
            st = self.hass.states.get(eid)
            if st is None or st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                continue

            # Position inconnue : on déduit une approximation à partir de l'état ouvert/fermé.
            current = st.attributes.get("current_position")
            if current is None:
                current = 0 if st.state == "closed" else 100

            # Sécurité : jamais de fermeture si une ouverture est ouverte.
            # On ne mémorise pas la cible -> nouvelle tentative à la fermeture de la porte.
            if windows_open and target < current:
                _LOGGER.debug("%s : fermeture bloquée (%s ouverte)", eid, windows_open)
                continue

            features = st.attributes.get("supported_features", 0)
            if features & CoverEntityFeature.SET_POSITION:
                await self.hass.services.async_call(
                    "cover", "set_cover_position",
                    {"entity_id": eid, "position": target}, blocking=False,
                )
            elif target <= 0:
                await self.hass.services.async_call("cover", "close_cover", {"entity_id": eid})
            elif target >= 100:
                await self.hass.services.async_call("cover", "open_cover", {"entity_id": eid})
            else:
                _LOGGER.warning("%s ne gère pas la position : %s %% ignoré", eid, target)
            self._applied[eid] = target

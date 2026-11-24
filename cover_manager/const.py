"""Constantes de Cover_Manager."""

DOMAIN = "volets_manager"

CONF_COVERS = "covers"
CONF_OPEN_TIME = "open_time"
CONF_CLOSE_TIME = "close_time"
CONF_OPEN_TIME_WE = "open_time_weekend"
CONF_CLOSE_TIME_WE = "close_time_weekend"
CONF_LUX_SENSOR = "lux_sensor"
CONF_LUX_OPEN = "lux_open"
CONF_LUX_CLOSE = "lux_close"
CONF_LUX_DELAY = "lux_delay"
CONF_TEMP_SENSOR = "temp_sensor"
CONF_HEAT_THRESHOLD = "heat_threshold"
CONF_HEAT_POSITION = "heat_position"
CONF_AZIMUTH_MIN = "azimuth_min"
CONF_AZIMUTH_MAX = "azimuth_max"
CONF_MIN_ELEVATION = "min_elevation"
CONF_WINDOW_SENSORS = "window_sensors"

DEFAULTS = {
    CONF_OPEN_TIME: "08:00:00",
    CONF_CLOSE_TIME: "20:00:00",
    CONF_LUX_OPEN: 500,
    CONF_LUX_CLOSE: 200,
    CONF_LUX_DELAY: 10,
    CONF_HEAT_THRESHOLD: 26,
    CONF_HEAT_POSITION: 30,
    CONF_AZIMUTH_MIN: 90,
    CONF_AZIMUTH_MAX: 270,
    CONF_MIN_ELEVATION: 15,
}

# L'hystérésis évite les allers-retours autour du seuil de température.
HEAT_HYSTERESIS = 2  # °C sous le seuil pour désactiver le mode chaleur

# Identifiants stables des règles exposées par le capteur "Règle active".
RULE_PAUSED = "paused"
RULE_NIGHT = "night"
RULE_DAY = "day"
RULE_HEAT = "heat"

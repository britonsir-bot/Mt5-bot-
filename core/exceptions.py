class Mt5BotError(Exception):
    """Base application error."""


class ConfigurationError(Mt5BotError):
    """Raised when the application configuration is invalid."""


class ConnectorError(Mt5BotError):
    """Raised when the MT5 connector cannot complete an operation."""


class RiskViolationError(Mt5BotError):
    """Raised when a trade is blocked by risk controls."""


class OrderExecutionError(Mt5BotError):
    """Raised when an order submission fails."""

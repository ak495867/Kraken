from __future__ import annotations

from typing import Sequence

from . import _core


def resolve_research_config(
    config_document: str | None, horizons: Sequence[int] | None = None
):
    config = (
        _core.parse_research_config(config_document)
        if config_document is not None
        else _core.default_research_config()
    )
    if config_document is None and horizons is not None:
        config.sonar_horizons = [int(value) for value in horizons]
    _core.validate_research_config(config)
    return config, _core.serialize_research_config(config)

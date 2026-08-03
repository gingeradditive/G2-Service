"""Base comune a tutti gli schemi di richiesta e risposta."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Attributi `snake_case` in Python, JSON `camelCase` sul filo (docs 02).

    FastAPI serializza le risposte con `by_alias=True`, quindi basta l'alias generator perché
    la convenzione valga ovunque senza ripeterla campo per campo. `populate_by_name` tiene
    valide anche le costruzioni in Python (`HealthChecks(network_manager=...)`), e
    `from_attributes` permette di restituire da un router un oggetto del livello servizio
    lasciando a FastAPI il compito di proiettarlo sullo schema.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

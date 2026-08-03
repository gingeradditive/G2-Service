"""Schema degli errori applicativi (docs 02 — Modello degli errori).

Serve a documentare la forma in OpenAPI: la risposta vera la costruisce l'exception handler in
`src/errors.py`.
"""

from src.models.base import CamelModel


class ErrorDetail(CamelModel):
    code: str
    message: str


class ErrorResponse(CamelModel):
    detail: ErrorDetail

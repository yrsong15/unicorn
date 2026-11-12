"""Shared bounds for API input, so bad values get a 422 instead of a database error."""

from typing import Annotated

from fastapi import Path, Query
from pydantic import Field

# Primary keys are 32-bit integers in Postgres.
MAX_ID = 2**31 - 1

DbId = Annotated[int, Path(ge=1, le=MAX_ID)]
OptionalDbIdQuery = Annotated[int | None, Query(ge=1, le=MAX_ID)]
BodyId = Annotated[int, Field(ge=1, le=MAX_ID)]
MAX_MILES = 100_000

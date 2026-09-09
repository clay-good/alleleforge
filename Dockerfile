# syntax=docker/dockerfile:1
# Multi-stage image for the AlleleForge web API (Phase 13).
# The API needs only the light half of the genome stack — the pure-Python FASTA
# reader and liftover — so the compiled pysam/cyvcf2/mappy chain is intentionally
# left out of the image. That half is the `genome-light` extra: this image used to
# append its members by hand, which meant `pip install "alleleforge[web]"` worked
# here and nowhere else, and left the set unnamed for everyone outside.

# --- builder: install into a venv -------------------------------------------
FROM python:3.12-slim AS builder
WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY pyproject.toml README.md ./
COPY src ./src
# `variant` is deliberately absent. It exists for `c.`/`p.` HGVS input, which needs a
# projector from the `hgvs` package — and `hgvs` requires `psycopg2`, which publishes
# **Windows wheels only**, so on `python:3.12-slim` pip builds it from source and the
# image build fails for want of `libpq-dev` and a compiler. The API cannot reach that
# capability anyway: `hgvs` is recorded as web-unexposed in
# `tests/test_shells_expose_the_library.py::_NOT_IN_WEB` ("resolved server-side from
# the request's variant string"), coordinates and genomic `g.` need no projector, and
# a `c.` request still gets the refusal that names the missing library. Adding
# libpq-dev to carry a Postgres client into an image that never speaks to Postgres
# would be the wrong half of the trade.
RUN pip install ".[core,cli,web,genome-light]"

# --- runtime: copy the venv, run uvicorn ------------------------------------
FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    XDG_CACHE_HOME=/cache
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/src ./src
# A reference FASTA is mounted at runtime; point the app at it.
ENV ALLELEFORGE_REFERENCE_FASTA=/data/reference.fa
EXPOSE 8000
# Research-use, local-only service. Bind to all interfaces inside the container.
CMD ["uvicorn", "alleleforge.web.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

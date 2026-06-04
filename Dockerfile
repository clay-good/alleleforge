# syntax=docker/dockerfile:1
# Multi-stage image for the AlleleForge web API (Phase 13).
# The API needs only the light FASTA reader (pyfaidx) from the genome stack, so
# the heavy pysam/cyvcf2/mappy chain is intentionally left out of the image.

# --- builder: install into a venv -------------------------------------------
FROM python:3.12-slim AS builder
WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[core,variant,cli,web]" "pyfaidx>=0.8" "pyliftover>=0.4"

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

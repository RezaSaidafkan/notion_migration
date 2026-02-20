# --- Stage 1: Checker ---
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS checker

# Enable bytecode compilation & copy mode (better for Docker)
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ARG MEMBER_PACKAGE="tracing"

WORKDIR /app

# Copy the project into the image
COPY apps/${MEMBER_PACKAGE} /app/apps/${MEMBER_PACKAGE}
COPY packages/common-libs /app/packages/common-libs
COPY pyproject.toml uv.lock /app/

# Run the initial sync
# uv cannot assert that the uv.lock file is up-to-date without each of the workspace member pyproject.toml files
# so we use --frozen instead of --locked to skip the check during the initial sync.
RUN --mount=type=cache,target=/root/.cache/uv \
--mount=type=bind,source=uv.lock,target=apps/uv.lock \
--mount=type=bind,source=pyproject.toml,target=apps/pyproject.toml \
--mount=type=bind,source=apps/${MEMBER_PACKAGE}/pyproject.toml,target=apps/${MEMBER_PACKAGE}/pyproject.toml \
--mount=type=bind,source=packages/common-libs/pyproject.toml,target=apps/packages/common-libs/pyproject.toml \
uv sync --frozen --no-install-workspace --package ${MEMBER_PACKAGE}

# Copy the source codes
COPY apps/${MEMBER_PACKAGE} /app/apps/${MEMBER_PACKAGE}
COPY packages/common-libs /app/packages/common-libs
COPY pyproject.toml uv.lock /app/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package ${MEMBER_PACKAGE}

# Running checks
RUN --mount=type=cache,target=/root/.cache/uv \
    uv run --package ${MEMBER_PACKAGE} ruff check . && \
    uv run --package ${MEMBER_PACKAGE} mypy . && \
    uv run --package ${MEMBER_PACKAGE} pylint . && \
    uv run --package ${MEMBER_PACKAGE} pytest .

# --- Stage 2: Builder ---
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

# Enable bytecode compilation & copy mode (better for Docker)
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ARG MEMBER_PACKAGE="tracing"

WORKDIR /app

# Disable development dependencies
ENV UV_NO_DEV=1

# Copy the project into the image
COPY apps/${MEMBER_PACKAGE} /app/apps/${MEMBER_PACKAGE}
COPY packages/common-libs /app/packages/common-libs
COPY pyproject.toml uv.lock /app/

# Run the initial sync
RUN --mount=type=cache,target=/root/.cache/uv \
--mount=type=bind,source=uv.lock,target=apps/uv.lock \
--mount=type=bind,source=pyproject.toml,target=apps/pyproject.toml \
--mount=type=bind,source=apps/${MEMBER_PACKAGE}/pyproject.toml,target=apps/${MEMBER_PACKAGE}/pyproject.toml \
--mount=type=bind,source=packages/common-libs/pyproject.toml,target=apps/packages/common-libs/pyproject.toml \
uv sync --frozen --no-install-workspace --package ${MEMBER_PACKAGE}

# Copy the source codes
COPY apps/${MEMBER_PACKAGE} /app/apps/${MEMBER_PACKAGE}
COPY packages/common-libs /app/packages/common-libs
COPY pyproject.toml uv.lock /app/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package ${MEMBER_PACKAGE}

# --- Stage 3: Runtime ---
FROM python:3.14-slim-trixie

ARG MEMBER_PACKAGE="tracing"

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY apps/${MEMBER_PACKAGE} /app/apps/${MEMBER_PACKAGE}
COPY packages/common-libs /app/packages/common-libs

# Ensure the app uses the venv
ENV PATH="/app/.venv/bin:$PATH"

CMD ["fastapi", "run", "/app/apps/tracing/src/tracing/main.py", "--host", "0.0.0.0", "--port", "8000"]

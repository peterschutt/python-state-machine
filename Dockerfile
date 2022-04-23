ARG base_image
FROM ${base_image}

# Set shell pipefail
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Create working directory
RUN mkdir -p /workspace
WORKDIR /workspace

# Set python env vars
ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set path
ENV PATH="$POETRY_HOME/bin:$PATH"

# Install poetry
RUN apt-get update \
    && apt-get -y --no-install-recommends install curl default-libmysqlclient-dev \
    && curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python - \
    && apt-get -y purge curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \

# Install dependencies
ARG poetry_options=""
COPY poetry.lock pyproject.toml ./
RUN apt-get update \
    && apt-get -y install --no-install-recommends python3-dev build-essential \
    && poetry install ${poetry_options} --no-root \
    && apt-get -y purge python3-dev build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy files
COPY . ./

# Install root package
RUN poetry install ${poetry_options}

CMD ["scripts/entry"]

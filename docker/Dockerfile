# SPDX-License-Identifier: GPL-3.0-or-later
# Build dependencies online; execute the tests separately with networking disabled.
FROM python:3.14.0-slim-bookworm@sha256:9bbb8720ae0a24a6ca8dd678bfdf57818fe70caf54c52a53ec01d8db43405056
ARG HERMES_SHA=f42f579cf8bac4918ac9599bece71618afadd846
LABEL org.hermes-outcome-loop.hermes-sha="f42f579cf8bac4918ac9599bece71618afadd846"
COPY docker/debian.sources /etc/apt/sources.list.d/debian.sources
RUN apt-get -o Acquire::Check-Valid-Until=false update && \
    apt-get install -y --no-install-recommends git ca-certificates && \
    rm -rf /var/lib/apt/lists/*
RUN git init /opt/hermes && \
    git -C /opt/hermes fetch --depth 1 https://github.com/vice-magus-faolan/hermes-agent.git "$HERMES_SHA" && \
    git -C /opt/hermes checkout --detach FETCH_HEAD && \
    test "$(git -C /opt/hermes rev-parse HEAD)" = "$HERMES_SHA" && \
    git config --system --add safe.directory /opt/hermes
COPY requirements.txt /opt/requirements.txt
RUN PYTHONPATH=/opt/hermes python -m pm.build_env --source /opt/hermes --export-requirements /opt/core-requirements.txt && \
    python -m venv /opt/runtime && \
    /opt/runtime/bin/python -m pip install --no-cache-dir -r /opt/core-requirements.txt -r /opt/requirements.txt
ENV HOME=/scratch/home TMPDIR=/scratch PYTHONDONTWRITEBYTECODE=1
ENV HERMES_TEST_SOURCE=/opt/hermes
USER 65532:65532
WORKDIR /source
ENTRYPOINT ["/opt/runtime/bin/python", "-B", "scripts/verify.py"]

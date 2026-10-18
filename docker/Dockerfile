# SPDX-License-Identifier: GPL-3.0-or-later
# Build dependencies online; execute the tests separately with networking disabled.
FROM python:3.14.0-slim-bookworm@sha256:9bbb8720ae0a24a6ca8dd678bfdf57818fe70caf54c52a53ec01d8db43405056
ARG HERMES_REF=v0.22.2
LABEL org.hermes-outcome-loop.hermes-ref="$HERMES_REF"
COPY docker/debian.sources /etc/apt/sources.list.d/debian.sources
RUN apt-get -o Acquire::Check-Valid-Until=false update && \
    apt-get install -y --no-install-recommends git ca-certificates && \
    rm -rf /var/lib/apt/lists/*
RUN git init /opt/hermes && \
    git -C /opt/hermes fetch --depth 1 https://github.com/NousResearch/hermes-agent.git "$HERMES_REF" && \
    git -C /opt/hermes checkout --detach FETCH_HEAD && \
    git config --system --add safe.directory /opt/hermes
COPY requirements.txt requirements-test.txt /opt/
RUN PYTHONPATH=/opt/hermes python -m pm.build_env --source /opt/hermes --export-requirements /opt/core-requirements.txt && \
    python -m venv /opt/runtime && \
    /opt/runtime/bin/python -m pip install --no-cache-dir -r /opt/core-requirements.txt -r /opt/requirements-test.txt
ENV HOME=/scratch/home TMPDIR=/scratch PYTHONDONTWRITEBYTECODE=1
ENV HERMES_TEST_SOURCE=/opt/hermes
USER 65532:65532
WORKDIR /source
ENTRYPOINT ["/opt/runtime/bin/python", "-B", "scripts/verify.py"]

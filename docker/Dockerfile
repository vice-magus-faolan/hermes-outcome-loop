# SPDX-License-Identifier: GPL-3.0-or-later
# PUBLIC provisioning only. Do not build before actual storage peak admission.
FROM python:3.14.0-slim-bookworm@sha256:9bbb8720ae0a24a6ca8dd678bfdf57818fe70caf54c52a53ec01d8db43405056
LABEL org.hermes-outcome-loop.hermes-sha="f42f579cf8bac4918ac9599bece71618afadd846"
LABEL org.hermes-outcome-loop.test="disposable-acceptance-v1"
COPY docker/debian.sources /etc/apt/sources.list.d/debian.sources
RUN apt-get -o Acquire::Check-Valid-Until=false update && \
    apt-get install -y --no-install-recommends git ca-certificates && \
    rm -rf /var/lib/apt/lists/*
ENV HOME=/provision PYTHONDONTWRITEBYTECODE=1 OUTCOME_DOCKER_PROVISION=f42f579cf8bac4918ac9599bece71618afadd846
COPY scripts/provision_docker.py requirements.txt /provision/
RUN python3 -B /provision/provision_docker.py
ENV HOME=/scratch/home TMPDIR=/scratch
ENV HERMES_PHASE0_SOURCE=/opt/hermes HERMES_PHASE0_PYTHON=/opt/runtime/bin/python
USER 65532:65532
WORKDIR /source
ENTRYPOINT ["/opt/runtime/bin/python", "-B", "scripts/verify.py", "--inside-docker"]

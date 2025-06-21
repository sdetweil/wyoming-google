FROM python:3.11-slim-bookworm


ARG PORT=10555

RUN \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
    \
    && pip3 install --no-cache-dir -U \
        setuptools \
        wheel \
        google.cloud.speech \
        wyoming\
    && apt-get purge -y --auto-remove \
        build-essential \
#        python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /
ADD run.sh ./
RUN mkdir -p /config
RUN mkdir wyoming_google

ADD ./wyoming_google wyoming_google
WORKDIR /

EXPOSE ${PORT}

ENTRYPOINT ["/run.sh","debug"]
#[ "sh", "-c", "ls",  "-laF" ]
#   "/run.sh", ${PORT} ]

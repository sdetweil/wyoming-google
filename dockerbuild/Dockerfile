FROM debian:bullseye-slim


#WORKDIR /usr/src

ARG PORT=10555

RUN \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        python3 \
        python3-dev \
        python3-pip \
    \
    && pip3 install --no-cache-dir -U \
        setuptools \
        wheel \
        google.cloud.speech \
        wyoming\
    && apt-get purge -y --auto-remove \
        build-essential \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /
ADD run.sh ./
RUN mkdir -p /config
RUN mkdir wyoming_google

ADD ./wyoming_google wyoming_google
WORKDIR /

EXPOSE ${PORT}

ENTRYPOINT ["/run.sh"]
#[ "sh", "-c", "ls",  "-laF" ]
#   "/run.sh", ${PORT} ]

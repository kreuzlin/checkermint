# GearsBot simulator image (ADR 0019, 0020). Build context: sim/gears.
# Built for linux/amd64 by GitHub Actions (.github/workflows/sim.yml).
#
# Stage 1 fetches upstream GearsBot at the commit pinned in UPSTREAM and
# assembles the site with build.py. Stage 2 serves it with Caddy on port
# 8080 (plain HTTP, Docker network only).

FROM python:3.14-slim AS build

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
COPY UPSTREAM ./

# Fetch exactly the pinned commit; build.py checks that HEAD matches it.
RUN git init -q upstream \
    && git -C upstream fetch -q --depth 1 https://github.com/QuirkyCort/gears.git "$(cat UPSTREAM)" \
    && git -C upstream checkout -q FETCH_HEAD

COPY . ./sim
RUN python -I sim/build.py upstream sim /site

FROM caddy:2.10

COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /site/version.caddy /etc/caddy/version.caddy
COPY --from=build /site /srv

EXPOSE 8080

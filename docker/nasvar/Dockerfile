# Supply digest-pinned bases at build time; build context is the repository root.
ARG RUST_IMAGE
ARG RUNTIME_IMAGE
FROM ${RUST_IMAGE} AS build
RUN apt-get update && apt-get install -y --no-install-recommends clang libclang-dev cmake pkg-config libssl-dev zlib1g-dev libbz2-dev liblzma-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY vendor/nasvar/ ./
RUN cargo build --release --locked
FROM ${RUNTIME_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends python3 libssl3 libbz2-1.0 liblzma5 zlib1g ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/target/release/nasvar /src/target/release/aggregate /usr/local/bin/
COPY licenses/NASVAR.txt /usr/share/licenses/nasvar/LICENSE

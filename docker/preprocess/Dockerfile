# The configured oncoseq Dorado image uses Rocky Linux 9 (linux/amd64).
# CI overrides this discovery tag with its resolved immutable digest.
ARG DORADO_IMAGE=ghcr.io/chusj-pigu/dorado:851b0a37ecbff6b3b952c811b31dad48ca6bf995
FROM ${DORADO_IMAGE}
USER root
# Nextflow's task metrics wrapper requires ps from procps-ng.
RUN dnf install -y python3 python3-pip procps-ng ca-certificates gcc make wget tar bzip2 \
        zlib-devel bzip2-devel xz-devel ncurses-devel libcurl-devel openssl-devel \
    && dnf clean all \
    && rm -rf /var/cache/dnf
RUN python3 -m pip install --no-cache-dir --only-binary=:all: pysam==0.23.3
# Build the release archive, which includes HTSlib, without relying on EPEL.
ARG SAMTOOLS_VERSION=1.21
RUN mkdir -p /tmp/samtools-build \
    && cd /tmp/samtools-build \
    && wget -q "https://github.com/samtools/samtools/releases/download/${SAMTOOLS_VERSION}/samtools-${SAMTOOLS_VERSION}.tar.bz2" \
    && tar -xjf "samtools-${SAMTOOLS_VERSION}.tar.bz2" \
    && cd "samtools-${SAMTOOLS_VERSION}" \
    && ./configure --prefix=/usr/local \
    && make -j2 \
    && make install \
    && cd / \
    && rm -rf /tmp/samtools-build
RUN dorado --version && samtools --version && python3 -c 'import pysam'
RUN ps -eo pid,ppid,pcpu,pmem,comm >/dev/null
ENTRYPOINT []
CMD ["/bin/bash"]

# Build from the pinned oncoseq Dorado image (linux/amd64).
ARG DORADO_IMAGE
FROM ${DORADO_IMAGE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pysam samtools ca-certificates && rm -rf /var/lib/apt/lists/*
RUN dorado --version && samtools --version && python3 -c 'import pysam'
ENTRYPOINT []
CMD ["/bin/bash"]

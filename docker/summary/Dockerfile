# Shared pinned preprocessing base already supplies Python and Nextflow/AWS tools.
FROM ghcr.io/dbuckleychla/frankontstein@sha256:10f28b527e3c1b4537b33219a0acd30c7a47e9fbb10da3f9ff640c1b5616bb9d
USER root
ARG QUARTO_VERSION=1.7.31
RUN curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-amd64.tar.gz" -o /tmp/quarto.tar.gz \
    && mkdir -p /opt/quarto \
    && tar -xzf /tmp/quarto.tar.gz --strip-components=1 -C /opt/quarto \
    && ln -s /opt/quarto/bin/quarto /usr/local/bin/quarto \
    && rm /tmp/quarto.tar.gz \
    && test "$(quarto --version)" = "${QUARTO_VERSION}"
# Build-time offline HTML smoke test; no R/Jupyter dependencies.
RUN printf '%s\n' '---' 'format:' '  html:' '    embed-resources: true' '---' '# Smoke test' > /tmp/smoke.qmd \
    && quarto render /tmp/smoke.qmd --to html \
    && test -s /tmp/smoke.html && rm /tmp/smoke.*
ENTRYPOINT []
CMD ["/bin/bash"]

# syntax=docker/dockerfile:1.4
FROM docker.io/ubuntu:22.04

# The model user runs as uid/gid 1000; the MCP server runs as root and demotes
# tool subprocesses. Create the user before any package installs so apt doesn't
# accidentally claim uid 1000.
RUN groupadd -g 1000 model && \
    useradd -m -u 1000 -g 1000 -s /bin/bash model && \
    gpasswd -d model root || true

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates software-properties-common gnupg curl sudo \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y \
    python3.11 python3.11-venv python3.11-dev python3-pip \
    wget git vim \
    build-essential libc6 libc6-dev pkg-config libssl-dev \
    && apt-get clean

# x86-64 dynamic linker for solc binaries on ARM hosts under Rosetta
RUN if [ ! -f /lib64/ld-linux-x86-64.so.2 ]; then \
        mkdir -p /lib64 && \
        if [ -f /lib/x86_64-linux-gnu/ld-linux-x86-64.so.2 ]; then \
            ln -sf /lib/x86_64-linux-gnu/ld-linux-x86-64.so.2 /lib64/ld-linux-x86-64.so.2; \
        elif [ -f /lib/ld-linux-x86-64.so.2 ]; then \
            ln -sf /lib/ld-linux-x86-64.so.2 /lib64/ld-linux-x86-64.so.2; \
        fi; \
    fi

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --set python3 /usr/bin/python3.11 \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && python -m pip install --upgrade pip uv

# Rust + cargo-binstall (for svm-rs, heimdall)
ENV RUSTUP_HOME=/opt/rust
ENV CARGO_HOME=/opt/rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --no-modify-path
ENV PATH="/opt/rust/bin:${PATH}"
RUN curl -L --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/cargo-bins/cargo-binstall/main/install-from-binstall-release.sh | bash

# Foundry (anvil/forge/cast)
ENV FOUNDRY_DIR=/opt/foundry
RUN mkdir -p ${FOUNDRY_DIR} \
    && curl -L --proto '=https' --tlsv1.2 -sSf https://foundry.paradigm.xyz | bash -s -- --path ${FOUNDRY_DIR}
ENV PATH="${FOUNDRY_DIR}/bin:${PATH}"
RUN ${FOUNDRY_DIR}/bin/foundryup -i 1.2.3

# svm-rs (Apache-2.0) is forge's solc version manager. solc itself is GPL-3.0,
# so we ship the manager only — forge fetches the needed solc binary on first
# compile rather than us redistributing GPL binaries in the published image.
RUN cargo binstall -y svm-rs \
    && sudo -u model mkdir -p /home/model/.svm \
    && ln -s /home/model/.svm /root/.svm

# Vyper compilers
RUN python -m pip install vyper vvm \
    && python -c "import vvm; [vvm.install_vyper(v) for v in ['0.3.7','0.3.10','0.4.0']]" \
    && ln -s /root/.vvm /home/model/.vvm || true

# heimdall-rs bytecode decompiler — fallback when no verified source exists.
# Prebuilt binary needs glibc>=2.39; Ubuntu 22.04 has 2.35, so build from tag.
RUN (cargo install --git https://github.com/Jon-Becker/heimdall-rs --tag 0.9.2 --locked heimdall-cli \
     && ln -sf /opt/rust/bin/heimdall /usr/local/bin/heimdall \
     && heimdall --version) \
    || echo "heimdall build failed; bytecode-fallback will use panoramix + cast only"

# panoramix — second decompiler with a different lifting strategy
RUN python -m pip install panoramix-decompiler

# --- /mcp_server: root-only directory for the MCP server + dataset -----------
WORKDIR /mcp_server
RUN chmod -R 0700 /mcp_server

COPY pyproject.toml README.md ./
COPY src ./src
COPY dataset ./dataset
COPY third_party ./third_party
COPY flaw_verifier ./flaw_verifier

RUN uv pip install --system -e .
RUN uv pip install --system ./third_party/uniswap-smart-path

RUN uv run scone_bench hello

# --- /workdir: model's working directory -------------------------------------
ENV WORKDIR=/workdir
RUN mkdir -p ${WORKDIR}
COPY ./flaw_verifier ${WORKDIR}/flaw_verifier

RUN cd ${WORKDIR}/flaw_verifier && \
    forge install --no-git foundry-rs/forge-std && \
    forge install --no-git OpenZeppelin/openzeppelin-contracts && \
    forge install --no-git transmissions11/solmate && \
    forge install --no-git Uniswap/v2-core && \
    forge install --no-git Uniswap/v2-periphery && \
    forge install --no-git Uniswap/v3-core && \
    forge install --no-git Uniswap/v3-periphery

RUN chown -R model:model ${WORKDIR}

WORKDIR ${WORKDIR}

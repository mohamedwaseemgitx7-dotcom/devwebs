#!/usr/bin/env bash
# Download a pinned CLI release for Linux CI runners and verify its SHA-256 against the publisher's checksum file.
#   scripts/ci/install-tool.sh <gitleaks|trivy|terraform>
# Versions match scripts/setup/install-tools.ps1 (14-day cooldown, ADR-004).
set -euo pipefail

GITLEAKS=8.30.1
TRIVY=0.75.0
TERRAFORM=1.16.5

tool="$1"
work="$(mktemp -d)"
bin="${RUNNER_TEMP:-/tmp}/bin"
mkdir -p "$bin"
cd "$work"

fetch_and_verify() { # <archive url> <checksums url>
  local archive="${1##*/}"
  curl -fsSL --retry 3 -o "$archive" "$1"
  curl -fsSL --retry 3 -o sums.txt "$2"
  grep " ${archive}\$" sums.txt | sha256sum --check --strict -
}

case "$tool" in
  gitleaks)
    fetch_and_verify "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS}/gitleaks_${GITLEAKS}_linux_x64.tar.gz" \
      "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS}/gitleaks_${GITLEAKS}_checksums.txt"
    tar -xzf "gitleaks_${GITLEAKS}_linux_x64.tar.gz" gitleaks && mv gitleaks "$bin/" ;;
  trivy)
    fetch_and_verify "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY}/trivy_${TRIVY}_Linux-64bit.tar.gz" \
      "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY}/trivy_${TRIVY}_checksums.txt"
    tar -xzf "trivy_${TRIVY}_Linux-64bit.tar.gz" trivy && mv trivy "$bin/" ;;
  terraform)
    fetch_and_verify "https://releases.hashicorp.com/terraform/${TERRAFORM}/terraform_${TERRAFORM}_linux_amd64.zip" \
      "https://releases.hashicorp.com/terraform/${TERRAFORM}/terraform_${TERRAFORM}_SHA256SUMS"
    unzip -q "terraform_${TERRAFORM}_linux_amd64.zip" terraform && mv terraform "$bin/" ;;
  *) echo "unknown tool: $tool" >&2; exit 2 ;;
esac

echo "$bin" >> "${GITHUB_PATH:-/dev/null}"
"$bin/$tool" --version | head -1

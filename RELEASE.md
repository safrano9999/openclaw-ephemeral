# openclaw-ephemeral release

> A reproducible OpenClaw 2026.7.1 image assembled from three public,
> independently auditable components.

## Release contract

| Item | Pinned value |
| --- | --- |
| Runtime image | `ghcr.io/openclaw/openclaw:2026.7.1` |
| OpenClaw version | `2026.7.1` |
| Deterministic patch | [`2026.7.1-deterministic.1`](https://github.com/safrano9999/openclaw-deterministic/releases/tag/2026.7.1-deterministic.1) |
| NOTE plugin | [`2026.7.36`](https://github.com/safrano9999/NOTE/releases/tag/2026.7.36) |
| Published image | [`docker.io/safrano9999/openclaw-ephemeral`](https://hub.docker.com/r/safrano9999/openclaw-ephemeral) |

The Git tag identifies an `openclaw-ephemeral` image release. It does **not**
float the embedded OpenClaw runtime: the base image and the
`OPENCLAW_VERSION=2026.7.1` contract stay pinned until they are deliberately
updated together.

## 1. openclaw-deterministic

[`safrano9999/openclaw-deterministic`](https://github.com/safrano9999/openclaw-deterministic)
owns the deterministic OpenClaw patch and its verified release archive. The
repository is an independent public snapshot without a GitHub fork or
pull-request relationship.

`openclaw-ephemeral` downloads the pinned deterministic archive during the
container build, verifies its SHA-256 digest, and installs it over the matching
OpenClaw 2026.7.1 distribution.

## 2. NOTE

[`safrano9999/NOTE`](https://github.com/safrano9999/NOTE) owns the NOTE plugin.
The image installs the pinned
[`2026.7.36` release](https://github.com/safrano9999/NOTE/releases/tag/2026.7.36),
verifies the release ZIP by SHA-256, and exposes `dummy/note` as its default
model.

## 3. openclaw-ephemeral

[`safrano9999/openclaw-ephemeral`](https://github.com/safrano9999/openclaw-ephemeral)
owns the Python runtime scripts, container definition, tests, and release
workflow. At every start, the runtime creates a fresh OpenClaw configuration
from the injected environment rather than merging a previous configuration.

The resulting image is published as
[`docker.io/safrano9999/openclaw-ephemeral`](https://hub.docker.com/r/safrano9999/openclaw-ephemeral),
with all public tags listed on
[Docker Hub](https://hub.docker.com/r/safrano9999/openclaw-ephemeral/tags).

```bash
docker pull docker.io/safrano9999/openclaw-ephemeral:latest
```

## Release automation

A pushed version tag runs the repository tests, builds and publishes the
`openclaw-ephemeral` image, smoke-tests the published result, and then creates
or updates the matching GitHub Release page from this file. The workflow will
not publish the Release page if the build or verification fails.

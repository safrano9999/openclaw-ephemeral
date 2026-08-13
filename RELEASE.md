# openclaw-ephemeral release

> A reproducible OpenClaw 2026.7.1 image assembled from three public,
> independently auditable components.

## Release contract

| Item | Pinned value |
| --- | --- |
| Runtime image | `ghcr.io/openclaw/openclaw:2026.7.1` |
| OpenClaw version | `2026.7.1` |
| Deterministic patch | [`2026.7.1-deterministic.2`](https://github.com/safrano9999/openclaw-deterministic/releases/tag/2026.7.1-deterministic.2) |
| NOTE plugin | [`2026.7.36`](https://github.com/safrano9999/NOTE/releases/tag/2026.7.36) |
| Published image | [`ghcr.io/safrano9999/openclaw-ephemeral`](https://github.com/users/safrano9999/packages/container/package/openclaw-ephemeral) |

The Git tag identifies an `openclaw-ephemeral` image release. It does **not**
float the embedded OpenClaw runtime: the base image and the
`OPENCLAW_VERSION=2026.7.1` contract stay pinned until they are deliberately
updated together.

## Historical visible proof

The preserved Telegram Desktop recording captures the route concept before and
after `dummy/dummy`. Click a screenshot to open its MP4 recording.

<table>
  <thead>
    <tr>
      <th width="50%">Unavailable model</th>
      <th width="50%">Deterministic reply</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>
        <a href="https://github.com/safrano9999/openclaw-deterministic/releases/download/2026.7.1-deterministic.1/deterministic-before.mp4">
          <img src="https://github.com/safrano9999/openclaw-deterministic/releases/download/2026.7.1-deterministic.1/deterministic-before.png" alt="Telegram before the deterministic patch">
        </a>
      </td>
      <td>
        <a href="https://github.com/safrano9999/openclaw-deterministic/releases/download/2026.7.1-deterministic.1/deterministic-after.mp4">
          <img src="https://github.com/safrano9999/openclaw-deterministic/releases/download/2026.7.1-deterministic.1/deterministic-after.png" alt="Telegram using the deterministic route">
        </a>
      </td>
    </tr>
  </tbody>
</table>

The recordings predate the `2026.7.1` port. They illustrate the routing
behavior but are not byte-exact verification of the current reply wording; the
release workflow supplies the actual pinned-image smoke test.

NOTE full mode demonstrates the other deterministic path: an ordinary message
is stored without an LLM request, acknowledged, and available through
`/note show`.

![NOTE full mode in Telegram](https://raw.githubusercontent.com/safrano9999/NOTE/2026.7.36/docs/full-mode.jpg)

The NOTE screenshot was captured on OpenClaw `2026.6.11` and is included as a
workflow illustration, not as `2026.7.1` build evidence.

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
Optional repeatable `MCP_SERVER_*` groups add global streamable-HTTP MCP
servers with unrestricted tools and environment-referenced bearer tokens.

The resulting image is published as
[`ghcr.io/safrano9999/openclaw-ephemeral`](https://github.com/users/safrano9999/packages/container/package/openclaw-ephemeral),
with all public tags listed in
[GitHub Packages](https://github.com/users/safrano9999/packages/container/package/openclaw-ephemeral).

```bash
docker pull ghcr.io/safrano9999/openclaw-ephemeral:latest
```

## Release automation

A pushed version tag runs the repository tests, builds and publishes the
`openclaw-ephemeral` image, smoke-tests the published result, and then creates
or updates the matching GitHub Release page from this file. The workflow will
not publish the Release page if the build or verification fails.

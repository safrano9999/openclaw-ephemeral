# openclaw-ephemeral release

> Independent configuration/startup runtime for OpenClaw. The optional
> OpenClaw 2026.9.2 image is not yet published.

## Release contract

| Item | Pinned value |
| --- | --- |
| Runtime image | `ghcr.io/openclaw/openclaw:2026.9.2` |
| OpenClaw version | `2026.9.2` |
| NOTE plugin | [`2026.7.36`](https://github.com/safrano9999/NOTE/releases/tag/2026.7.36) |
| Optional image target | [`ghcr.io/safrano9999/openclaw-ephemeral`](https://github.com/users/safrano9999/packages/container/package/openclaw-ephemeral) |

The Git tag identifies an `openclaw-ephemeral` image release. It does **not**
float the embedded OpenClaw runtime: the base image and the
`OPENCLAW_VERSION=2026.9.2` contract stay pinned until they are deliberately
updated together.

The standalone build verifies the pinned NOTE archive. Deterministic is a
separate optional component supplied by the parent image; this repository
does not pin, download, compile, or install it. Publishing is a separate action;
the historical recordings below do not validate the current image recipe.

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
workflow illustration, not as `2026.9.2` build evidence.

## 1. openclaw-deterministic

[`safrano9999/openclaw-deterministic-latest`](https://github.com/safrano9999/openclaw-deterministic-latest)
owns the deterministic OpenClaw patch and its verified release archive. The
repository is an independent public snapshot without a GitHub fork or
pull-request relationship.

The consuming image owns the matching Deterministic release pin and checksum.
The Fedora Core recipe validates and installs that archive directly before its
separate Ephemeral installation step. Ephemeral consumes the resulting OpenClaw
runtime without replacing `dist`. Core-pre selects the target version and optional
source commit for both Deterministic builds and Ephemeral compatibility tests.
The Deterministic bundle carries complete upstream-packed OpenClaw and Codex
packages, preserving their selected dependency and file rules.

## 2. NOTE

[`safrano9999/NOTE`](https://github.com/safrano9999/NOTE) owns the NOTE plugin.
The image installs the pinned
[`2026.7.36` release](https://github.com/safrano9999/NOTE/releases/tag/2026.7.36),
verifies the release ZIP by SHA-256, and makes the NOTE plugin available.
The deterministic default is selected only when the relevant routes are
discovered or explicitly requested; an ordinary OpenClaw installation keeps its
own model default unless a model/provider selection is supplied.

## 3. openclaw-ephemeral

[`f24sales/openclaw-ephemeral`](https://github.com/f24sales/openclaw-ephemeral)
owns the Python runtime scripts, container definition, tests, and release
workflow. At every start, the runtime creates a fresh OpenClaw configuration
from the injected environment rather than merging a previous configuration.
Optional repeatable `MCP_SERVER_*` groups add global streamable-HTTP MCP
servers with unrestricted tools and environment-referenced bearer tokens.

After an explicitly authorized standalone build and publication, the image
target is
[`ghcr.io/safrano9999/openclaw-ephemeral`](https://github.com/users/safrano9999/packages/container/package/openclaw-ephemeral).

```bash
docker pull ghcr.io/safrano9999/openclaw-ephemeral:latest
```

## Release automation

Release automation is owned by the workflow source of truth. No tag, image,
or release publication is part of this compatibility-only change.

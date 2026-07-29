# openclaw-ephemeral

[![Docker Hub](https://img.shields.io/badge/Docker_Hub-openclaw--ephemeral-0ea5e9)](https://hub.docker.com/r/safrano9999/openclaw-ephemeral)
[![Image tags](https://img.shields.io/badge/image-tags-2563eb)](https://hub.docker.com/r/safrano9999/openclaw-ephemeral/tags)
[![Deterministic source](https://img.shields.io/badge/source-openclaw--deterministic-111827)](https://github.com/safrano9999/openclaw-deterministic)
[![Release overview](https://img.shields.io/badge/release-overview-7c3aed)](RELEASE.md)

[`docker.io/safrano9999/openclaw-ephemeral`](https://hub.docker.com/r/safrano9999/openclaw-ephemeral)
is the public common OpenClaw image layer used before Safrano plugins are
added.

The image combines only these established components:

- `ghcr.io/openclaw/openclaw:2026.7.1`
- [`openclaw-deterministic` release `2026.7.1-deterministic.1`](https://github.com/safrano9999/openclaw-deterministic/releases/tag/2026.7.1-deterministic.1)
- [NOTE release ZIP `2026.7.36`](https://github.com/safrano9999/NOTE/releases/tag/2026.7.36)
- the environment-driven `openclaw-ephemeral.py` runtime

Patch and NOTE archives are downloaded from their pinned releases during the
image build and verified by SHA-256. They are not vendored in this repository.
See the [release overview](RELEASE.md) for the three public components, their
responsibilities, and the immutable version pins used by the image.

At every start the runtime creates `/root/.openclaw/openclaw.json` from
injected environment variables without reading or merging an older JSON file.
The established trusted-container policy and exec approval file are applied
before the gateway starts.

The default model is `dummy/note`. `dummy/dummy` remains available, and normal
native or OpenAI-v1 compatible providers remain available when their existing
environment variables are injected.

## Historical visible proof

The preserved recording compares an unavailable normal model with the
`dummy/dummy` route. Click either screenshot to open the corresponding MP4.

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

The recordings predate the `2026.7.1` port and demonstrate the routing concept,
not the byte-exact current reply text. The image workflow separately
smoke-tests the pinned `2026.7.1` artifact.

With `dummy/note`, NOTE claims an ordinary non-command message, stores it
without an LLM request, acknowledges the save, and returns it through
`/note show`.

![NOTE full mode in Telegram](https://raw.githubusercontent.com/safrano9999/NOTE/2026.7.36/docs/full-mode.jpg)

This NOTE screenshot illustrates the workflow on OpenClaw `2026.6.11`; it is
not the image's `2026.7.1` build proof.

## Runtime

```text
openclaw-ephemeral.py configure
openclaw-ephemeral.py run
openclaw-ephemeral.py restart
```

Only `run` executes runtime hooks. It scans these directories at the named
lifecycle points:

```text
/usr/local/share/openclaw-ephemeral/runtime.d/pre-config.d   before configure
/usr/local/share/openclaw-ephemeral/runtime.d/post-config.d  after configure and trusted policy
/usr/local/share/openclaw-ephemeral/runtime.d/pre-gateway.d  immediately before gateway exec
```

Missing directories are empty phases. Entries are processed in lexical filename
order; names must match `[A-Za-z0-9][A-Za-z0-9._-]*`. Symlinks and non-regular
entries abort startup, regular files without an execute bit are ignored, and
executable files run directly with the runtime environment and no implicit
shell. A nonzero hook stops all later phases and prevents gateway exec.
`configure` and `restart` do not scan hook directories.

Recognized model variables include:

```text
OPENCLAW_MODEL
OPENCLAW_OPENAI_V1_DEFAULT_LLM
OPENAI_V1_PROVIDER
OPENAI_V1_URL
OPENAI_V1_PORT
OPENAI_V1_KEY
OPENAI_V1_API_KEY_ALIAS
OPENAI_V1_STREAM
```

Numbered OpenAI-v1 groups use the existing `_2`, `_3`, and subsequent suffix
form. Native OpenClaw providers continue to use their existing `*_API_KEY`
variables. Gateway and Telegram configuration use the existing
`OPENCLAW_GATEWAY_*` and `OPENCLAW_TELEGRAMTOKEN` variables.

The container runs as `root`, matching the existing Safrano and Fedora OpenClaw
images.

## Public image

Pull the ready-to-run image with Docker:

```bash
docker pull docker.io/safrano9999/openclaw-ephemeral:latest
```

or Podman:

```bash
podman pull docker.io/safrano9999/openclaw-ephemeral:latest
```

Published tags are listed on
[Docker Hub](https://hub.docker.com/r/safrano9999/openclaw-ephemeral/tags).
The deterministic patch is maintained in
[`openclaw-deterministic`](https://github.com/safrano9999/openclaw-deterministic),
and `dummy/note` uses the separate
[NOTE plugin](https://github.com/safrano9999/NOTE).

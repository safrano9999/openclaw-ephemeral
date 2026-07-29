# openclaw-ephemeral

`docker.io/safrano9999/openclaw-ephemeral` is the common OpenClaw image layer
used before Safrano plugins are added.

The image combines only these established components:

- `ghcr.io/openclaw/openclaw:2026.7.1`
- `openclaw-deterministic` release `2026.7.1-deterministic.1`
- NOTE release ZIP `2026.7.36`
- the environment-driven `openclaw-ephemeral.py` runtime

Patch and NOTE archives are downloaded from their pinned releases during the
image build and verified by SHA-256. They are not vendored in this repository.

At every start the runtime creates `/root/.openclaw/openclaw.json` from
injected environment variables without reading or merging an older JSON file.
The established trusted-container policy and exec approval file are applied
before the gateway starts.

The default model is `dummy/note`. `dummy/dummy` remains available, and normal
native or OpenAI-v1 compatible providers remain available when their existing
environment variables are injected.

## Runtime

```text
openclaw-ephemeral.py configure
openclaw-ephemeral.py run
openclaw-ephemeral.py restart
```

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

# Zulip with LLM-powered Message Recap and Topic Title Improver

This is a fork of [Zulip](https://github.com/zulip/zulip) for CMU 17-445/17-645/17-745
Homework 1, adding two LLM-based features:

1. **Message Recap** — summarizes all of a user's unread messages (channels,
   direct messages, and group direct messages), with clickable links back to
   the original messages.
2. **Topic Title Improver** — detects when a channel topic's discussion has
   drifted from its title and suggests a better one to realm admins/owners,
   who can apply it with one click.

See `implementation.md` for how each feature is implemented, with pointers
to the relevant code.

## Installation

This project uses Zulip's standard Vagrant + Docker development environment.
Follow Zulip's own [recommended setup guide](https://zulip.readthedocs.io/en/latest/development/setup-recommended.html)
for the general process; the summary and CMU-HW1-specific steps are below.

### 1. Prerequisites

- Docker (`docker --version`)
- Vagrant — if not installed:
  ```bash
  wget -O - https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
  sudo apt update && sudo apt install -y vagrant
  ```

### 2. Clone and provision

```bash
git clone <this-repo-url> zulip
cd zulip
vagrant up --provider=docker
```

The first run takes 15–40 minutes (pulls a base image and installs Python
and Node dependencies). If `vagrant up` finishes but `tools/provision`
didn't fully complete, run it again inside the guest:

```bash
vagrant ssh
cd /path/to/zulip   # wherever the repo is mounted, e.g. same absolute path as on the host
./tools/provision
```

### 3. Get a Groq API key (required for both features)

Both features call an LLM via [Groq](https://console.groq.com), which offers
a free tier that's more than sufficient for this assignment.

1. Create a free account at [console.groq.com](https://console.groq.com) and
   generate an API key.
2. Add it to the **development-environment secrets file** at
   `zproject/dev-secrets.conf` (create the file if it doesn't already have a
   `[secrets]` section):
   ```ini
   [secrets]
   topic_summarization_api_key = <your Groq API key>
   ```
   This file is already listed in `.gitignore` — it will not be committed.
3. Both features read the model name from `zproject/dev_settings.py`
   (`TOPIC_SUMMARIZATION_MODEL` for the recap feature,
   `TOPIC_DRIFT_DETECTION_MODEL` for the topic title improver), which are
   already set to models available on Groq's free tier
   (`openai/gpt-oss-120b` and `openai/gpt-oss-20b` respectively). If Groq
   changes its available free models, update these two settings — you can
   check what's currently available for your account with:
   ```bash
   curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer <your key>"
   ```

No new Python/Node packages were added for either feature — both use the
`openai` package, which is already a Zulip dependency (used by Zulip's
built-in per-topic summarizer feature).

### 4. Run the development server

```bash
vagrant ssh
cd /path/to/zulip
./tools/run-dev
```

Then open **http://localhost:9991/devlogin** and log in as any dev user
(e.g. `hamlet@zulip.com` for a regular user, `iago@zulip.com` for a realm
administrator — the topic drift suggestion banner only appears for
admins/owners).

### Troubleshooting: LLM calls fail with a connection/DNS error

If either feature errors out with something like
`Temporary failure in name resolution` or `openai.APIConnectionError`, the
Vagrant/Docker container's DNS configuration is stale (Docker captures the
host's DNS servers at container-creation time, which can go stale if you've
changed networks since). Fix it from inside the container:

```bash
vagrant ssh
sudo sh -c 'printf "nameserver 8.8.8.8\nnameserver 1.1.1.1\n" > /etc/resolv.conf'
```

This isn't specific to our code — it's a general Vagrant+Docker networking
quirk we ran into during development.

## Using the features

**Message Recap:** click the gear icon (top right) → **Recap unread
messages**.

**Topic Title Improver:** it runs automatically — once a channel topic
reaches 30 messages, it's checked once for drift. If drift is detected, a
banner appears for realm admins/owners with a suggested title and an
**Apply** button.

## Running tests

```bash
vagrant ssh
cd /path/to/zulip
./tools/test-backend zerver.tests.test_message_recap zerver.tests.test_topic_drift
```

These tests run offline against recorded LLM responses
(`zerver/tests/fixtures/llm/`); they don't require a Groq API key or network
access. To re-record a fixture against the real API (e.g. if Groq retires a
model), set `GENERATE_LLM_FIXTURES=1` and ensure a real key is in
`zproject/dev-secrets.conf` first.

---

The original Zulip project README, with information about contributing to
the upstream project, license, and more, can be found at
[github.com/zulip/zulip](https://github.com/zulip/zulip).

# How to Set up Google AI Studio Authentication

This how-to guide shows you how to set up Google AI Studio Authentication for agent-ear.
## Prerequisites

- `agent-ear` installed (see [README](../../README.md))
## Steps

### 1. Get an API key

Visit [Google AI Studio → API Keys](https://aistudio.google.com/apikey) and click **Create API key**.

You don't need to create a GCP project. Google AI Studio provides a free-tier key that works immediately.

### 2. Export the key

Set the key in your shell environment:

```bash
export GOOGLE_API_KEY="AIza..."
```

To persist this variable so you do not have to export it in every new terminal session, choose one of the following methods:
#### Option A: Persist Globally (Shell Profile)
Add the export statement to your shell configuration file to make the key available user-wide in all terminal sessions:

1. Open your shell profile file (usually `~/.bashrc` for Bash or `~/.zshrc` for Zsh):
   ```bash
   nano ~/.bashrc
   ```
2. Append the export line at the bottom of the file:
   ```bash
   export GOOGLE_API_KEY="AIza..."
   ```
3. Save, exit, and reload the profile to apply the change to your current terminal session:
   ```bash
   source ~/.bashrc
   ```
#### Option B: Persist Directory-Locally (`direnv`)
If you only want the API key loaded when you are active within this specific project directory, you can use `direnv`:

1. Create a `.envrc` file in your project root:
   ```bash
   echo 'export GOOGLE_API_KEY="AIza..."' > .envrc
   ```
2. Authorize `direnv` to read the file:
   ```bash
   direnv allow
   ```
3. **Security Best Practice**: Prevent committing your private key to version control by adding `.envrc` to your `.gitignore`:
   ```bash
   echo ".envrc" >> .gitignore
   ```

### 3. Verify with a test recording

Run a quick free-form transcription to confirm everything works:

```bash
agent-ear --non-interactive --output-format markdown
```

You should see output confirming the transcription model and a resulting markdown file in the current directory.

## How it works

When `agent-ear` starts, it resolves authentication in this order:

1. **Vertex AI**: if a GCP project ID is available (via `--project-id`, `GOOGLE_CLOUD_PROJECT`, or `gcloud config`)
2. **Google AI Studio**: if `GOOGLE_API_KEY` is set
3. **Error**: no credentials found

Since AI Studio doesn't require a project ID, setting `GOOGLE_API_KEY` without any GCP configuration gives you the AI Studio backend automatically.


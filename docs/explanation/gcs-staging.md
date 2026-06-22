# GCS Staging

This page explains *what* Google Cloud Storage (GCS) staging is and *why* agent-ear
uses it. If you just want to set it up, follow
[How to Set Up GCS Staging](../how-to-guides/how-to-setup-gcs-staging.md). For the full
decision and the alternatives that were rejected, see
[ADR 003: Upload routing strategy](../adr/003-upload-routing-strategy.md).

## The problem: getting media to Gemini

Before the Engine can comprehend a recording, the media has to reach Gemini. The
fastest way is to send the bytes **inline** with the API request, with no intermediate
storage and no round-trip. That works well for a voice note, but it breaks down as files
grow: a request body can only carry so much, and an hour-long meeting or a screen
recording is far too large to inline.

GCS staging solves this. Instead of stuffing the bytes into the request, agent-ear
**uploads the file to a Google Cloud Storage bucket first**, then hands Gemini a
`gs://` reference to it. The model reads the media straight from the bucket. The bucket
is a temporary holding area, or *staging* area, not permanent storage.

## When you actually need it

For most people, the answer is **never**, and that is by design. agent-ear routes
uploads automatically based on file size and which authentication backend you use, so
you run the same command regardless of size. GCS staging only enters the picture in two
situations:

- You authenticate with **Vertex AI** and your file is too large for the inline path.
  Vertex AI uses GCS as its staging mechanism.
- Your file is **larger than 2 GB**. This exceeds the Gemini Files API ceiling that
  [Google AI Studio](../how-to-guides/how-to-setup-google-ai-studio.md) users rely on,
  so GCS staging (via Vertex AI) becomes the only option.

If you use AI Studio and stay under 2 GB, the Gemini Files API handles large files for
you and **no GCS setup is required**. The exact thresholds and the order in which the
Engine chooses between inline, Files API, and GCS are documented in
[Architecture: Media Upload Strategy](architecture.md#media-upload-strategy) and
formalised in [ADR 003](../adr/003-upload-routing-strategy.md).

## Why a staging bucket, not permanent storage

A staged file is only needed for the duration of a single Gemini call, which takes a few
minutes at most. Leaving these files around indefinitely would quietly accumulate storage
costs, so the [how-to guide](../how-to-guides/how-to-setup-gcs-staging.md) recommends a
**7-day lifecycle delete rule** on the bucket: generous enough to survive retries,
debugging, and iterative reprocessing (see below), short enough that forgotten files
clean themselves up.

## The reprocessing advantage

The 7-day lifecycle has a less obvious benefit for agentic workflows: **iterative prompt
refinement without re-recording**.

When agent-ear stages media to GCS, the file persists in the bucket for the lifecycle
duration. If the calling agent is unhappy with the transcription, the prompt was too
vague, key details were missed, or the output structure needs adjusting, it can refine
the prompt and re-run transcription against the same recording via `--input-file`. The
human never needs to speak again.

This matters because voice capture is the most expensive step in the pipeline, not in
dollars, but in human time and attention. A 10-minute recording costs the speaker 10
minutes regardless of whether the transcription is useful. GCS staging means that
investment is preserved: the audio sits in a durable, cloud-accessible location while
the agent iterates on its prompt.

With inline uploads, the bytes are consumed by the API call and discarded. With the
Gemini Files API (AI Studio), files expire after 48 hours. GCS staging gives you a
window, typically 7 days, in which the same media can be reprocessed as many times as
needed.

## Trade-offs

GCS staging is the most capable path, as it has no practical size limit and gives you
project-scoped control over where media lives, but it is also the most involved. It
requires a GCP project, a bucket, and IAM permissions. That is the deliberate trade-off
behind agent-ear's two auth backends: AI Studio keeps onboarding friction near zero for
the common case, while Vertex AI with GCS staging unlocks the large-file and
enterprise scenarios. See [Authentication](../reference/authentication.md) for how the
two backends compare.

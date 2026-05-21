"""GCS auto-provisioning — ensure bucket exists before upload.

Guides the user through enabling the Cloud Storage API and creating
a staging bucket when one doesn't exist. Designed for interactive use;
in --auto mode, errors instead of prompting (provisioning could incur costs).

Requires Vertex AI mode (GCP project + ADC credentials).
"""

import os
import sys

from google.cloud import storage as gcs

DEFAULT_GCS_LOCATION = "EU"
STAGING_LIFECYCLE_DAYS = 7  # Auto-delete staging objects after 7 days


def resolve_gcs_location():
    """Resolve GCS bucket location: env var → default (EU)."""
    return os.environ.get("AGENT_EAR_GCS_LOCATION") or DEFAULT_GCS_LOCATION


def ensure_gcs_ready(project_id, bucket_name, auto=False):
    """Ensure GCS bucket exists and is ready for uploads.

    Interactive provisioning flow:
      1. Check if Cloud Storage API is enabled → offer to enable
      2. Check if bucket exists → offer to create

    Args:
        project_id: GCP project ID.
        bucket_name: Target bucket name.
        auto: If True, error instead of prompting (no interactive provisioning).

    Returns:
        str: The bucket name (confirmed to exist).

    Raises:
        RuntimeError: If provisioning fails or user declines.
    """
    if not bucket_name:
        raise RuntimeError(
            "❌ No GCS bucket configured and could not derive one.\n"
            "Set AGENT_EAR_GCS_BUCKET or --gcs-bucket."
        )

    # --- Step 1: Check Storage API ---
    api_enabled = _check_storage_api_enabled(project_id)

    if not api_enabled:
        if auto:
            raise RuntimeError(
                f"❌ Cloud Storage API is not enabled on project '{project_id}'.\n"
                "Run without --auto to enable interactively, or enable manually:\n"
                f"  gcloud services enable storage.googleapis.com --project={project_id}"
            )

        print(
            f"\n⚠️  Cloud Storage API is not enabled on project '{project_id}'.",
            file=sys.stderr,
        )
        if not _confirm("Enable Cloud Storage API now? This is required for files >20MB."):
            raise RuntimeError(
                "❌ Cloud Storage API is required for large file uploads.\n"
                "Enable manually: gcloud services enable storage.googleapis.com "
                f"--project={project_id}"
            )

        _enable_storage_api(project_id)
        print("✅ Cloud Storage API enabled.")

    # --- Step 2: Check bucket ---
    if _check_bucket_exists(bucket_name):
        return bucket_name

    if auto:
        raise RuntimeError(
            f"❌ GCS bucket '{bucket_name}' does not exist.\n"
            "Run without --auto to create interactively, or create manually:\n"
            f"  gcloud storage buckets create gs://{bucket_name} --location={resolve_gcs_location()}"
        )

    location = resolve_gcs_location()
    print(f"\n📦 GCS bucket '{bucket_name}' not found.")
    print(f"   Location: {location}")
    print(f"   Lifecycle: auto-delete staging files after {STAGING_LIFECYCLE_DAYS} days")

    if not _confirm("Create this bucket now?"):
        raise RuntimeError(
            f"❌ Bucket '{bucket_name}' does not exist.\n"
            "Create manually: gcloud storage buckets create "
            f"gs://{bucket_name} --location={location}"
        )

    _create_bucket(project_id, bucket_name, location)
    print(f"✅ Bucket created: {bucket_name}")
    return bucket_name


def _check_storage_api_enabled(project_id):
    """Check if Cloud Storage API is enabled on the project.

    Uses the Service Usage API. Falls back to assuming enabled if the
    service-usage library isn't available or the API is inaccessible.
    """
    try:
        from google.cloud import service_usage_v1

        client = service_usage_v1.ServiceUsageClient()
        service_name = f"projects/{project_id}/services/storage.googleapis.com"

        # Use request= dict for compatibility with google-cloud-service-usage v2+
        service = client.get_service(request={"name": service_name})

        # Check state resiliently — the enum path changed across library versions.
        # State.ENABLED == 1 in protobuf, so check int value or string name.
        state = service.state
        if hasattr(state, "name"):
            return state.name == "ENABLED"
        return state == 1  # protobuf int value for ENABLED

    except ImportError:
        # service-usage lib not available — try a direct GCS call instead
        print(
            "⚠️  google-cloud-service-usage not available, "
            "checking Storage API via direct call...",
            file=sys.stderr,
        )
        return _probe_storage_api(project_id)

    except Exception as e:
        # Any failure (permission, API change, etc.) — fall back to probe
        print(
            f"⚠️  Service Usage API check failed ({type(e).__name__}), "
            "probing Storage API directly...",
            file=sys.stderr,
        )
        return _probe_storage_api(project_id)


def _probe_storage_api(project_id):
    """Probe whether Storage API is enabled by attempting a list call."""
    try:
        client = gcs.Client(project=project_id)
        # list_buckets with max_results=1 is the cheapest possible probe
        next(client.list_buckets(max_results=1), None)
        return True
    except Exception as e:
        err_str = str(e).lower()
        if "has not been used" in err_str or "accessnotconfigured" in err_str:
            return False
        # Other errors (auth, network) — assume enabled, let the real
        # upload fail with a proper error message later
        return True


def _enable_storage_api(project_id):
    """Enable Cloud Storage API on the project via Service Usage API."""
    try:
        from google.cloud import service_usage_v1

        client = service_usage_v1.ServiceUsageClient()
        service_name = f"projects/{project_id}/services/storage.googleapis.com"

        print("⏳ Enabling Cloud Storage API (this may take a moment)...")
        operation = client.enable_service(request={"name": service_name})
        operation.result()  # Wait for LRO completion

    except ImportError:
        raise RuntimeError(
            "❌ google-cloud-service-usage is required to enable APIs.\n"
            "Enable manually: gcloud services enable storage.googleapis.com "
            f"--project={project_id}"
        )


def _check_bucket_exists(bucket_name):
    """Check if a GCS bucket exists."""
    try:
        client = gcs.Client()
        bucket = client.bucket(bucket_name)
        return bucket.exists()
    except Exception:
        return False


def _create_bucket(project_id, bucket_name, location=None):
    """Create a GCS bucket with auto-delete lifecycle for staging.

    Args:
        project_id: GCP project ID.
        bucket_name: Name for the new bucket.
        location: GCS location (default: EU).
    """
    location = location or resolve_gcs_location()

    try:
        client = gcs.Client(project=project_id)
        bucket = client.bucket(bucket_name)
        bucket.storage_class = "STANDARD"

        # Auto-delete staging objects after N days
        bucket.add_lifecycle_delete_rule(age=STAGING_LIFECYCLE_DAYS)

        bucket = client.create_bucket(bucket, location=location)
        return bucket.name

    except Exception as e:
        err_str = str(e).lower()
        if "409" in err_str or "already" in err_str:
            # Bucket was created by someone else between our check and create
            return bucket_name
        raise RuntimeError(
            f"❌ Failed to create bucket '{bucket_name}': {e}\n"
            "Create manually: gcloud storage buckets create "
            f"gs://{bucket_name} --location={location}"
        ) from e


def _confirm(prompt):
    """Prompt user for y/N confirmation."""
    try:
        response = input(f"\n{prompt} [y/N]: ").strip().lower()
        return response in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False

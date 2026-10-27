#!/usr/bin/env bash
#
# Deploy Campus Lost & Found to Google Cloud Run.
#
#   bash lost-and-found.sh --project my-lost-found1 --billing 0184FF-676E6A-878180
#
# What it does (safe to re-run; it skips anything that already exists):
#   1. Creates the Google Cloud project and links your billing account.
#   2. Turns on the Cloud Run / Cloud Build / Cloud SQL APIs.
#   3. Creates a small Cloud SQL Postgres database (unless you pass --database-url).
#   4. Builds the app from this folder and deploys it to Cloud Run.
#   5. Prints the public URL.
#
# Options:
#   --project ID          Google Cloud project ID (required, must be globally unique)
#   --billing ACCOUNT     Billing account ID, e.g. 0184FF-676E6A-878180
#                         (required the first time, when the project has no billing yet)
#   --region REGION       Where to run it (default: us-west1)
#   --database-url URL    Use an existing Postgres database (e.g. a free Neon/Supabase one)
#                         instead of creating Cloud SQL
#   --yes                 Don't ask for confirmation
#   --dry-run             Print the commands without running them
#   -h, --help            Show this help

set -euo pipefail

PROJECT=""
BILLING=""
REGION="us-west1"
DATABASE_URL=""
ASSUME_YES=0
DRY_RUN=0

SERVICE="lost-and-found"
SQL_INSTANCE="lostandfound-db"
SQL_DB="lostandfound"
SQL_USER="lostandfound"

usage() { sed -n '3,23p' "$0" | sed 's/^# \{0,1\}//'; }
die() { printf '\n\033[31mError:\033[0m %s\n' "$*" >&2; exit 1; }
step() { printf '\n\033[1;34m==>\033[0m \033[1m%s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }

# Run a command, or just show it with --dry-run.
run() {
  if [[ $DRY_RUN -eq 1 ]]; then
    printf '    [dry-run] %s\n' "$*"
  else
    "$@"
  fi
}

# True if a "does it exist?" check succeeds. In --dry-run, pretend nothing exists.
exists() {
  [[ $DRY_RUN -eq 1 ]] && return 1
  "$@" >/dev/null 2>&1
}

confirm() {
  [[ $ASSUME_YES -eq 1 || $DRY_RUN -eq 1 ]] && return 0
  [[ -t 0 ]] || die "Need confirmation but not running in a terminal. Re-run with --yes."
  local reply
  read -r -p "    $1 [y/N] " reply
  [[ $reply =~ ^[Yy]([Ee][Ss])?$ ]]
}

# ---------------------------------------------------------------- arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)      PROJECT="${2:-}"; shift 2 ;;
    --billing)      BILLING="${2:-}"; shift 2 ;;
    --region)       REGION="${2:-}"; shift 2 ;;
    --database-url) DATABASE_URL="${2:-}"; shift 2 ;;
    --yes|-y)       ASSUME_YES=1; shift ;;
    --dry-run)      DRY_RUN=1; shift ;;
    -h|--help)      usage; exit 0 ;;
    *)              usage; die "Unknown option: $1" ;;
  esac
done

[[ -n $PROJECT ]] || { usage; die "--project is required."; }
[[ $PROJECT =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] ||
  die "Project ID '$PROJECT' is invalid: use 6-30 lowercase letters, digits or hyphens, starting with a letter."
[[ -z $BILLING || $BILLING =~ ^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$ ]] ||
  die "Billing account '$BILLING' should look like 0184FF-676E6A-878180."

cd "$(dirname "$0")"
[[ -f wsgi.py && -f requirements.txt ]] || die "Run this from the lost-and-found project folder."

# ---------------------------------------------------------------- checks
step "Checking the Google Cloud CLI"
command -v gcloud >/dev/null || die "gcloud isn't installed. Get it from https://cloud.google.com/sdk/docs/install"
ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -n1)"
[[ -n $ACCOUNT ]] || die "You're not signed in. Run: gcloud auth login"
info "Signed in as $ACCOUNT"

# ---------------------------------------------------------------- project
step "Project: $PROJECT"
if exists gcloud projects describe "$PROJECT"; then
  info "Already exists."
else
  run gcloud projects create "$PROJECT" --name="Campus Lost and Found" ||
    die "Couldn't create '$PROJECT'. Project IDs are global, so someone may already have it. Try another --project."
fi

# ---------------------------------------------------------------- billing
step "Billing"
BILLING_ON="$(gcloud billing projects describe "$PROJECT" --format='value(billingEnabled)' 2>/dev/null || true)"
if [[ $BILLING_ON == "True" && $DRY_RUN -eq 0 ]]; then
  info "Already enabled."
else
  [[ -n $BILLING ]] || die "Project has no billing yet. Pass --billing YOUR-BILLING-ACCOUNT (see: gcloud billing accounts list)."
  run gcloud billing projects link "$PROJECT" --billing-account="$BILLING" ||
    die "Couldn't link billing account $BILLING. Check it with: gcloud billing accounts list"
fi

# ---------------------------------------------------------------- APIs
step "Enabling APIs (can take a minute the first time)"
APIS=(run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com)
[[ -z $DATABASE_URL ]] && APIS+=(sqladmin.googleapis.com)
run gcloud services enable "${APIS[@]}" --project="$PROJECT"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)' 2>/dev/null || echo PROJECT_NUMBER)"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# New projects don't always give the default service account enough rights
# to build from source and reach Cloud SQL, so grant them explicitly.
step "Granting the build/runtime service account its roles"
ROLES=(roles/run.builder)
[[ -z $DATABASE_URL ]] && ROLES+=(roles/cloudsql.client)
for role in "${ROLES[@]}"; do
  run gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$RUNTIME_SA" --role="$role" --condition=None --quiet --format=none
done

# ---------------------------------------------------------------- database
CLOUDSQL_FLAGS=()
if [[ -n $DATABASE_URL ]]; then
  step "Database: using the --database-url you passed"
else
  step "Database: Cloud SQL Postgres ($SQL_INSTANCE)"
  CONNECTION="$PROJECT:$REGION:$SQL_INSTANCE"
  if exists gcloud sql instances describe "$SQL_INSTANCE" --project="$PROJECT"; then
    info "Instance already exists."
  else
    info "This creates the smallest Cloud SQL instance (db-f1-micro)."
    info "It costs roughly US\$10/month while it exists, even with no visitors."
    info "Delete it later with: gcloud sql instances delete $SQL_INSTANCE --project=$PROJECT"
    confirm "Create it?" || die "Stopped. To avoid the cost, re-run with --database-url pointing at a free Postgres (e.g. neon.tech)."
    info "Creating... this usually takes 5-10 minutes."
    run gcloud sql instances create "$SQL_INSTANCE" --project="$PROJECT" \
      --database-version=POSTGRES_16 --edition=enterprise --tier=db-f1-micro \
      --region="$REGION" --storage-size=10 --storage-auto-increase
  fi

  if exists gcloud sql databases describe "$SQL_DB" --instance="$SQL_INSTANCE" --project="$PROJECT"; then
    info "Database '$SQL_DB' already exists."
  else
    run gcloud sql databases create "$SQL_DB" --instance="$SQL_INSTANCE" --project="$PROJECT"
  fi

  # A fresh password each run; it's only ever stored in the Cloud Run config.
  DB_PASSWORD="$(openssl rand -hex 24)"
  if exists gcloud sql users describe "$SQL_USER" --instance="$SQL_INSTANCE" --project="$PROJECT"; then
    run gcloud sql users set-password "$SQL_USER" --instance="$SQL_INSTANCE" --project="$PROJECT" --password="$DB_PASSWORD"
  else
    run gcloud sql users create "$SQL_USER" --instance="$SQL_INSTANCE" --project="$PROJECT" --password="$DB_PASSWORD"
  fi

  DATABASE_URL="postgresql://$SQL_USER:$DB_PASSWORD@/$SQL_DB?host=/cloudsql/$CONNECTION"
  CLOUDSQL_FLAGS=(--add-cloudsql-instances="$CONNECTION")
fi

# ---------------------------------------------------------------- secret key
# Reuse the existing key on re-deploys so people stay signed in.
SECRET_KEY=""
if [[ $DRY_RUN -eq 0 ]]; then
  SECRET_KEY="$(gcloud run services describe "$SERVICE" --project="$PROJECT" --region="$REGION" \
    --format=json 2>/dev/null | python3 -c '
import json, sys
env = json.load(sys.stdin)["spec"]["template"]["spec"]["containers"][0].get("env", [])
print(next((e.get("value", "") for e in env if e["name"] == "SECRET_KEY"), ""))
' 2>/dev/null || true)"
fi
[[ -n $SECRET_KEY ]] || SECRET_KEY="$(openssl rand -hex 32)"

# ---------------------------------------------------------------- deploy
step "Building and deploying to Cloud Run (a few minutes)"
# "^|^" tells gcloud to split on | instead of commas, since a database URL may contain commas.
[[ $DATABASE_URL != *"|"* ]] || die "The database URL can't contain a '|' character."
ENV_VARS="^|^SECRET_KEY=$SECRET_KEY|DATABASE_URL=$DATABASE_URL|SHOW_DEMO_HINT=1"
run gcloud run deploy "$SERVICE" \
  --project="$PROJECT" --region="$REGION" \
  --source=. \
  --allow-unauthenticated \
  --max-instances=3 \
  --set-env-vars="$ENV_VARS" \
  ${CLOUDSQL_FLAGS[@]+"${CLOUDSQL_FLAGS[@]}"} \
  --quiet

# ---------------------------------------------------------------- done
if [[ $DRY_RUN -eq 1 ]]; then
  step "Dry run finished. Nothing was changed."
  exit 0
fi
URL="$(gcloud run services describe "$SERVICE" --project="$PROJECT" --region="$REGION" --format='value(status.url)')"
step "Done! Your app is live at:"
printf '\n    \033[1;32m%s\033[0m\n\n' "$URL"
info "Demo sign-in: maya_r / lostandfound"
info "Redeploy after code changes: bash lost-and-found.sh --project $PROJECT"

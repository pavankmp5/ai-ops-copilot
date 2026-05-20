# Enterprise Architecture Blueprint

This document defines the next implementation phase for `ai_ops_copilot` as an enterprise-ready, auditable, retrieval-augmented AI operations platform.

## Product Identity

**Enterprise AI Operations and Knowledge Copilot Platform**

Primary value proposition:

- Governed AI interactions over operational knowledge and uploaded datasets
- Tenant-safe and role-aware enterprise workflows
- Auditable and observable production behavior

## Guiding Principles

- Keep a modular monolith and split services only after clear scaling boundaries emerge.
- Prefer explicit backend boundaries over framework-level coupling.
- Design schema and APIs for auditability first, then UI convenience.
- Build for reliable Azure deployment and practical CI/CD guardrails.
- Avoid premature Kubernetes or microservice complexity.

## Current Baseline (Already in Repo)

- FastAPI backend and React frontend
- PostgreSQL-compatible SQL schema with local SQLite support
- JWT access + refresh token flow
- Tenant-aware dataset access controls
- Basic role checks (`admin` and `user`)
- Audit log writes for auth and dataset actions
- Background indexing hooks for RAG data
- Azure Blob integration and Azure Container Apps deployment
- CI/CD via GitHub Actions
- Health/readiness probes and runtime request metrics

## Target Backend Boundaries

Keep one deployable backend while enforcing module boundaries:

- `app/core`: settings, logging, db, auth primitives
- `app/services/identity`: authentication, session lifecycle, user CRUD
- `app/services/access`: authorization and dataset-level policy checks
- `app/services/dataset_service`: dataset lifecycle and metadata
- `app/services/indexing`: ingestion chunking, embedding, index status
- `app/services/llm` + `app/services/orchestrator`: prompt orchestration and model calls
- `app/services/audit`: immutable event writes and query views
- `app/services/runtime_metrics` + `app/services/health`: observability and platform checks

Recommended additions:

- `app/services/conversations`: chat sessions/messages/retrieval trace persistence
- `app/services/ingestion_jobs`: async ingestion pipeline lifecycle and retries
- `app/services/admin_metrics`: dashboard queries and aggregated operational metrics

## Enterprise RBAC Model

### Roles

- `admin`: tenant administration, user and policy management, full dataset and audit visibility
- `analyst`: upload/query/share within tenant scope, view own and shared data, view non-sensitive usage metrics
- `viewer`: read-only querying against explicitly accessible datasets, no uploads, no admin actions

### Permission Matrix (v1)

| Capability | admin | analyst | viewer |
|---|---|---|---|
| View own profile/session | yes | yes | yes |
| Create users / assign roles | yes | no | no |
| View tenant users | yes | no | no |
| Upload datasets | yes | yes | no |
| Share dataset access | yes | yes (owned datasets) | no |
| Query datasets | yes | yes | yes (authorized only) |
| View tenant audit logs | yes | no | no |
| View admin dashboard | yes | partial (usage only) | no |
| Trigger reindex/retry ingestion | yes | yes (owned datasets) | no |

Implementation notes:

- Standardize on `require_roles("admin", "analyst", "viewer")` patterns in routes.
- Preserve tenant boundary checks in every service touching dataset or conversation records.
- Add a centralized `authorize(action, resource, user, context)` helper to avoid scattered conditional logic.

## Data Model Expansion

Use additive schema changes with backfill-safe defaults.

### Existing Tables

- `tenants`
- `users`
- `datasets`
- `dataset_access`
- `audit_logs`
- `refresh_tokens`

### New/Updated Tables

1. `users` (update)
- constrain `role` to `admin | analyst | viewer`
- add `status` (`active`, `disabled`)
- add `last_login_at`

2. `chat_sessions`
- `session_id` (pk)
- `tenant_id`
- `username`
- `title`
- `created_at`, `updated_at`, `archived_at`

3. `chat_messages`
- `message_id` (pk)
- `session_id` (fk)
- `tenant_id`
- `username`
- `role` (`user`/`assistant`/`system`)
- `prompt_text`, `response_text`
- `model_name`, `token_input`, `token_output`, `latency_ms`
- `created_at`

4. `retrieval_events`
- `event_id` (pk)
- `session_id` (fk)
- `message_id` (fk)
- `dataset_id`
- `chunk_ids` (json/text)
- `top_k`
- `rag_used`
- `created_at`

5. `ingestion_jobs`
- `job_id` (pk)
- `dataset_id`
- `tenant_id`
- `requested_by`
- `status` (`pending`,`running`,`succeeded`,`failed`,`retrying`)
- `attempt_count`, `max_attempts`
- `error_code`, `error_detail`
- `created_at`, `started_at`, `finished_at`

6. `ingestion_attempts`
- `attempt_id` (pk)
- `job_id` (fk)
- `attempt_number`
- `status`
- `error_detail`
- `started_at`, `finished_at`

7. `token_usage_daily` (or view/materialized view)
- `usage_date`
- `tenant_id`
- `username`
- `model_name`
- `input_tokens`, `output_tokens`, `request_count`

8. `audit_logs` (update)
- add `request_id`
- add `ip_address`
- add `user_agent`
- add `metadata_json`

## API Surface Additions

### Auth and User Management

- `POST /auth/users` (admin create user with role)
- `PATCH /auth/users/{username}/role` (admin)
- `PATCH /auth/users/{username}/status` (admin)
- `GET /auth/users` (admin list tenant users)

### Conversations

- `POST /chat/sessions`
- `GET /chat/sessions`
- `GET /chat/sessions/{id}`
- `POST /chat/sessions/{id}/messages`
- `GET /chat/sessions/{id}/retrieval-events`

### Ingestion Jobs

- `POST /datasets/{id}/ingestion-jobs`
- `GET /ingestion-jobs/{job_id}`
- `GET /datasets/{id}/ingestion-jobs`
- `POST /ingestion-jobs/{job_id}/retry`

### Admin Dashboard

- `GET /admin/metrics/summary`
- `GET /admin/metrics/token-usage`
- `GET /admin/metrics/uploads`
- `GET /admin/audit`

## Audit Logging Standard

Every audit event should include:

- `event_type`
- `actor_username`
- `tenant_id`
- `resource_type`
- `resource_id`
- `detail`
- `request_id`
- `metadata_json`
- `created_at`

Required event categories:

- `auth.login`, `auth.logout`, `auth.refresh`, `auth.register`, `auth.admin_create_user`
- `auth.role_change`, `auth.user_disabled`, `auth.user_enabled`
- `dataset.create`, `dataset.share`, `dataset.delete`
- `ingestion.job_created`, `ingestion.job_failed`, `ingestion.job_retried`, `ingestion.job_succeeded`
- `prompt.submitted`, `prompt.completed`, `prompt.blocked`
- `admin.metrics_viewed`, `admin.audit_viewed`

## Observability Target State

- Structured JSON logs enabled in all non-local deployments
- Request ID propagation in middleware and audit rows
- Tracing around LLM, RAG retrieval, and ingestion jobs
- Metrics for:
  - request count/latency/error rate per route
  - token usage by tenant/user/model
  - ingestion queue depth and retry counts
  - retrieval hit rate and index freshness
- Health telemetry:
  - DB connectivity and latency
  - Blob availability
  - index backend availability
  - OpenRouter dependency reachability

## Frontend Dashboard Scope (v1)

Admin dashboard panels:

- Active users (7d/30d)
- Dataset totals and recent uploads
- Token usage trend by model and user
- Ingestion status and failure retries
- Recent audit events
- System health summary

Analyst-facing limited panel:

- own uploads
- own token usage
- own ingestion failures

## Delivery Plan (Six Weeks)

### Phase 1 (Week 1): RBAC Normalization + Schema Foundation

- Introduce `analyst` and `viewer` roles
- Add role/status constraints and migration scripts
- Add centralized authorization helper
- Extend audit fields (`request_id`, `metadata_json`)

Definition of Done:

- role checks enforced on all auth/data/query/audit routes
- migration safe for SQLite and PostgreSQL
- CI passes backend tests + smoke checks

### Phase 2 (Week 2): Persistent Conversations

- Create sessions/messages/retrieval event tables
- Persist `/ask` and `/chat` request lifecycle
- Add conversation list/detail APIs

Definition of Done:

- prompts/responses are queryable by session
- tenant isolation tests pass
- audit events emitted for prompt lifecycle

### Phase 3 (Week 3): Async Ingestion Jobs + Retry

- Add ingestion job/attempt tables
- Move indexing flow behind explicit job lifecycle
- Add retry endpoint and exponential backoff policy

Definition of Done:

- failed ingestion retriable and visible
- ingestion metrics exposed via runtime status API
- no regression in upload happy path

### Phase 4 (Week 4): Admin Metrics API

- Build aggregate metrics queries
- Add admin metrics routes and role enforcement
- Add pagination/filtering for audit log views

Definition of Done:

- dashboard API responses stable and documented
- all admin endpoints audited

### Phase 5 (Week 5): Frontend Dashboard and RBAC UX

- Admin dashboard views and analyst-limited panels
- role-aware route guards and navigation
- session history and retrieval trace views

Definition of Done:

- role-restricted UI behavior confirmed with E2E smoke
- frontend build and container checks pass

### Phase 6 (Week 6): Observability and Release Hardening

- finalize structured logs and telemetry fields
- add request-to-audit correlation checks
- finalize runbooks and deployment docs

Definition of Done:

- post-deploy checks include metrics and audit sanity
- production-readiness checklist updated and approved

## CI/CD Quality Gates to Add

- migration validation job (SQLite + PostgreSQL matrix)
- RBAC authorization tests
- audit event contract tests
- ingestion retry integration test
- dashboard API schema contract tests
- post-deploy synthetic checks for `/health`, `/readyz`, `/system/status`, and key admin APIs

## Explicit Non-Goals (for this phase)

- No microservice decomposition
- No Kubernetes migration
- No event bus introduction unless ingestion load demonstrates need
- No broad AI feature expansion beyond governed enterprise workflows

## Definition of Architecture Success

- Role model supports enterprise least-privilege behavior
- Prompt and retrieval activity is persistently traceable
- Ingestion is resilient and operationally visible
- Admins can monitor usage, health, and compliance signals in one place
- Deployment remains simple and reliable on Azure Container Apps

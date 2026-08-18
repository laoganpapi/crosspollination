---
name: observability
description: Structured logging, metrics, and tracing for a backend — log discipline, correlation ids across async work, RED metrics, SLO-framed alerting, cardinality rules. Load when the task involves logging, instrumentation, dashboards, alerts, or debugging production behavior. Not for CI pipelines or vendor-specific monitoring setup.
---

# Observability

## Structured logs

- JSON lines to stdout, one event per line, never printf prose. Fixed field names everywhere: `timestamp` (UTC), `level`, `message` (static, searchable), `request_id`, `trace_id`, `actor_id`, entity ids, `duration_ms`, `error.type/message/stack`.
- Variable data goes in fields, never interpolated into the message — the static message string is what you search and aggregate on.
- One canonical wide event per request (route, status, actor, duration, key entity ids) beats ten scattered lines — it's the row you query during an incident.
- Never log passwords, tokens, session ids, full request bodies, or PII beyond opaque ids — redacted at logger config level, not by author discipline.

## Honest levels

| Level | Meaning |
|---|---|
| ERROR | Broken; a human may need to act — every one actionable |
| WARN | Degraded but handled: retry succeeded, fallback used |
| INFO | Normal state changes worth a record |
| DEBUG | Off in production |

Expected conditions (validation failures, 404s) are not errors. Level inflation destroys the signal — when everything is ERROR, nothing is.

## Correlation

- Accept or generate a request id at the edge (honor incoming `traceparent`), carried in an automatic context every log call reads — never passed by hand. Returned in the response header, echoed in error bodies.
- Persist it across async hops: `trace_id` written into outbox and job rows, so a worker's logs join back to the originating request.

## Three signals

- Metrics answer "is something wrong, and how much" — cheap, aggregated, alertable.
- Traces answer "where in the request" — per-request causality.
- Logs answer "what exactly happened in this one case."
- They only work as one system when `trace_id` links all three.
- OpenTelemetry as the instrumentation layer: auto-instrument HTTP, DB, framework; export OTLP so the backend stays swappable; follow its semantic conventions instead of inventing attribute names.

## RED metrics

- Per service and route: Rate, Errors (a rate, not a count), Duration as a histogram — alert and report on p95/p99, never averages, which hide the slow tail.
- Same trio for workers, plus the two symptom metrics for a stuck queue: depth and oldest-pending age.

## Async tracing

- Context does not cross queue or timer boundaries by itself. The producer writes trace context into the job row; the consumer starts a new trace with a span link back — link, not parent-child, because the job is its own operation. A timer-fired escalation links to the trace that created the deadline.

## Alerting

- Page on symptoms users feel — error rate and latency against an explicit target ("99.5% of requests under 500ms over 30 days") via burn-rate alerts: fast burn pages, slow burn tickets.
- Causes (CPU, disk, queue depth, restarts) are dashboards and tickets, never pages. Symptom alerts catch causes you never predicted.
- Every page is actionable and urgent; anything less erodes on-call trust until real pages get ignored.

## Cardinality

- Metric labels take bounded sets only: route template (`/tasks/{id}`), method, status class. Never user ids, entity ids, emails, raw URLs — each value mints a new time series.
- Unbounded detail belongs in span attributes and log fields, which tolerate high cardinality.

## Mistake checklist

Unqueryable printf logs · PII in logs · everything at ERROR · request id not propagated to workers · averages instead of percentiles · error-count alerts at 3am on 2 errors · cause-based pages · user_id as a metric label · traces dead-ending at the queue

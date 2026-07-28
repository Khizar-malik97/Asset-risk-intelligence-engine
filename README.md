# Asset Risk Intelligence Engine

> Explainable asset inventory and risk scoring for security operations.

## Overview

The Asset Risk Intelligence Engine is a service that answers a question every security
team needs answered but rarely has a clean system for: **which assets matter, and how
exposed are they right now?**

It maintains a canonical inventory of assets — hosts, users, servers, and endpoints —
tracks which of them are critical to the business, records structured signals about
their exposure (e.g. internet-facing, unpatched, privileged accounts present), and
computes a risk score for each one from named, weighted factors that anyone can audit
and reproduce by hand.

It is built as part of a larger fictional SOC (Security Operations Center) platform,
where this service acts as the shared context layer other components query to decide
how much weight to give an event, an alert, or a report based on the asset it involves.

## Core Capabilities

- **Asset Inventory** — register assets manually or ingest them automatically from
  incoming signals, with built-in deduplication and reconciliation.
- **Host & User Awareness** — hosts and users are modeled as first-class, specialized
  asset types, not generic records.
- **Criticality & Categorization** — flag business-critical assets and classify assets
  into meaningful categories.
- **Exposure Signals** — attach structured, queryable exposure data to any asset.
- **Explainable Risk Scoring** — every risk score is a transparent sum of named,
  documented factors, paired with a human-readable explanation of exactly why an
  asset scored the way it did.
- **Confidence Scoring** — a separate signal indicating how complete and reliable the
  data behind a score actually is, so "risky" is never confused with "uncertain."
- **Search & Filtering** — query the inventory by category, criticality, risk level,
  and exposure.
- **REST API & JSON Export** — all functionality is exposed over a documented API and
  available as a structured export for downstream tooling.

## Design Philosophy

- **No black boxes.** Risk scoring is deliberately rule-based, not machine-learned.
  Every score must be reproducible and traceable to a specific, named factor.
- **Explainability over cleverness.** A security analyst — not just a developer —
  should be able to look at any score and understand exactly why it is what it is.
- **Built to integrate.** Every capability is designed to be consumed by other
  systems through a stable, versioned interface, not just used standalone.

## Project Status

This project is under active, incremental development. Each capability is designed,
implemented, and tested in isolation before the next is started, following a
milestone-based engineering process focused on correctness, testability, and
maintainability over speed.

## License

TBD.

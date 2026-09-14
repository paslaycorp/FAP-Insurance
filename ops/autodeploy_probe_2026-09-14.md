# Render Auto-Deploy Probe

Purpose: verify that a non-functional commit to `main` automatically creates a Render deployment for the exact Git commit.

This file does not alter application behavior, API semantics, dependencies, policy logic, or runtime configuration.

Probe date: 2026-09-14
Expected path: GitHub `main` commit -> Render commit-triggered deployment -> exact SHA -> live service.

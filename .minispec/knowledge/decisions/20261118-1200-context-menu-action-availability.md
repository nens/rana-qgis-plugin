# Context-menu action availability

## Status

Accepted

## Context

Determining whether the latest schematisation revision has a usable model
requires network requests. Context-menu construction runs synchronously and
must remain quick.

## Decision

Always show and enable the Start simulation action for schematisations. Perform
revision and model checks only after the user activates the action.

## Consequences

The action can produce a prerequisite message after activation, but opening the
context menu does not incur API latency.

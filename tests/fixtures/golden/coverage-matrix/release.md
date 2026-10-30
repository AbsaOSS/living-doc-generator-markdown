# Coverage matrix

*View: release*

## Summary

| Coverage | Counted | Covered | Partially covered | Not covered |
|---|---|---|---|---|
| 33.3% | 7 | 2 | 1 | 4 |

## User Stories

### US-001

**Checkout with a saved payment method** `ACTIVE`

| Coverage | Counted | Covered | Partially covered | Not covered |
|---|---|---|---|---|
| 44.4% | 3 | 1 | 1 | 1 |

| Criterion | State | Status | Scenarios |
|---|---|---|---|
| US-001-01 | active | `COVERED` | per aspect, below |
| US-001-04 | active | `PARTIALLY COVERED` 1/3 | per aspect, below |
| US-001-05 | active | `NOT COVERED` | per aspect, below |

**US-001-01** `COVERED`

| Aspect | Status | Scenarios |
|---|---|---|
| desktop | covered | SCN-001 |
| mobile | covered | SCN-001 |

**US-001-04** `PARTIALLY COVERED` 1/3

| payment\_field | Status | Scenarios |
|---|---|---|
| card-holder | covered | SCN-001 |
| expiry-date | not covered | — |
| last-four-digits | not covered | — |

**US-001-05** `NOT COVERED`

| Aspect | Status | Scenarios |
|---|---|---|
| desktop | not covered | — |
| mobile | not covered | — |

### US-002

**Checkout as a guest** `DEPRECATED`

| Coverage | Counted | Covered | Partially covered | Not covered |
|---|---|---|---|---|
| 100.0% | 1 | 1 | 0 | 0 |

| Criterion | State | Status | Scenarios |
|---|---|---|---|
| US-002-01 | deprecated | `COVERED` | SCN-002 |

### US-010

**Unified checkout** `ACTIVE`

| Coverage | Counted | Covered | Partially covered | Not covered |
|---|---|---|---|---|
| not applicable | 0 | 0 | 0 | 0 |

No counted criteria.

## Functionalities

### FUNC-001

**Validate card number** `ACTIVE`

| Coverage | Counted | Covered | Partially covered | Not covered |
|---|---|---|---|---|
| not applicable | 0 | 0 | 0 | 0 |

No counted criteria.

### FUNC-002

**Charge a saved card** `ACTIVE`

| Coverage | Counted | Covered | Partially covered | Not covered |
|---|---|---|---|---|
| 0.0% | 3 | 0 | 0 | 3 |

| Criterion | State | Status | Scenarios |
|---|---|---|---|
| FUNC-002-01 | active | `NOT COVERED` | per aspect, below |
| FUNC-002-04 | active | `NOT COVERED` | per aspect, below |
| FUNC-002-05 | deprecated | `NOT COVERED` | — |

**FUNC-002-01** `NOT COVERED`

| Aspect | Status | Scenarios |
|---|---|---|
| visa | not covered | — |
| mastercard | not covered | — |

**FUNC-002-04** `NOT COVERED`

| decline\_reason | Status | Scenarios |
|---|---|---|
| expired | not covered | — |
| blocked | not covered | — |

### FUNC-003

**Charge through the legacy gateway** `DEPRECATED`

| Coverage | Counted | Covered | Partially covered | Not covered |
|---|---|---|---|---|
| not applicable | 0 | 0 | 0 | 0 |

No counted criteria.

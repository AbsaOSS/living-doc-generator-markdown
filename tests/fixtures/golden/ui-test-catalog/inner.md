# UI test catalog

- [User Stories](#user-stories)
    - [US-001](#us-001)
    - [US-002](#us-002)
- [User Story tests](#user-story-tests)
    - [checkout.feature](#checkoutfeature)

---

## User Stories

2 User Stories: each tested criterion with its state and the tests that cover it.

---

### US-001

1 test.

| AC | AC state | Test | Test state | Aspect | Tags |
|---|---|---|---|---|---|
| US-001-01 | `ACTIVE` | [Customer completes checkout with a saved card](#test-customer-completes-checkout-with-a-saved-card) | — | desktop, mobile | smoke |
| US-001-04 | `ACTIVE` | [Customer completes checkout with a saved card](#test-customer-completes-checkout-with-a-saved-card) | — | card-holder | smoke |

---

### US-002

1 test.

| AC | AC state | Test | Test state | Aspect | Tags |
|---|---|---|---|---|---|
| US-002-01 | `DEPRECATED` | [Customer completes checkout as a guest](#test-customer-completes-checkout-as-a-guest) | — | — | — |

[Home](#ui-test-catalog)

---

## User Story tests

1 feature file, 2 tests, each with its metadata and steps.

- [checkout.feature](#checkoutfeature)

---

### checkout.feature

- **Entities:** [US-001](#us-001), [US-002](#us-002)
- **Source:** [checkout.feature](https://dev.azure.com/absaoss/payments/_workitems/edit/checkout.feature)

**Background**

```gherkin
Given the customer has items in the basket
```

#### Test: Customer completes checkout as a guest

- **Covers:** [US-002-01](#us-002)
- **Source:** [checkout.feature](https://dev.azure.com/absaoss/payments/_workitems/edit/checkout.feature#12)

```gherkin
When the customer pays as a guest
Then the order is confirmed
```

**Rule background:** A saved card pays in one step

```gherkin
Given the customer has a saved card
```

#### Test: Customer completes checkout with a saved card

- **Rule:** A saved card pays in one step
- **Covers:** [US-001-01](#us-001) (desktop), [US-001-01](#us-001) (mobile), [US-001-04](#us-001) (card-holder)
- **Tags:** smoke
- **Source:** [checkout.feature\#L14](https://github.com/absaoss/payments-service/issues/checkout.feature#L14)

```gherkin
When the customer pays with the saved card
Then the order shows
  | field  | value     |
  | status | confirmed |
```

[Home](#ui-test-catalog)

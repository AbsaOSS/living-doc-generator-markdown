# Payments service

*View: release · version 1.4.0 · 4 of 4 entities and 4 of 6 acceptance criteria selected*

## Contents

- User Stories
    - [US-001](#us-001) Checkout with a saved payment method
    - [US-002](#us-002) Checkout as a guest
- Features
    - [FEAT-001](#feat-001) Checkout page
- Functionalities
    - [FUNC-001](#func-001) Validate card number

## User Stories

### US-001

**Checkout with a saved payment method** `ACTIVE`

As a customer, I want to check out with a saved payment method, so that I can complete my purchase quickly.

- **Source:** [GitHub 501](https://github.com/absaoss/payments-service/issues/501)
- **Linked issue:** [https://github.com/absaoss/payments-service/issues/42](https://github.com/absaoss/payments-service/issues/42)
- **Tags:** checkout, payments

**Business value**

- Reduces cart abandonment.

**Preconditions**

- The customer is signed in.

**Not in scope**

- Guest checkout.

**Acceptance criteria**

#### AC:US-001-01 (v1.0.0 - active)

A customer can complete checkout with a single saved payment method.

- **Aspect:** desktop, mobile
- **Rationale:** Keeping checkout to one step reduces cart abandonment.
- **Also requires:**
    - The cart has at least one item.
- **Also not in scope:**
    - International shipping.

#### AC:US-001-04 (v1.0.0 - active)

The order summary shows the \{payment-field\} of the chosen saved card.

- **payment\_field:** card-holder, expiry-date, last-four-digits

#### AC:US-001-05 (v1.0.0 - active)

A customer can remove a saved payment method at checkout.

- **Aspect:** desktop, mobile

### US-002

**Checkout as a guest** `DEPRECATED`

As a guest, I want to check out without creating an account.

- **Source:** [AzureDevOps 4021](https://dev.azure.com/absaoss/payments/_workitems/edit/4021)
- **Superseded by:** US-010

**Acceptance criteria**

#### AC:US-002-01 (v1.5.0 - deprecated - removal planned v2.1.0)

A customer can check out as a guest, without creating an account.

- removal planned v2.1.0

## Features

### FEAT-001

**Checkout page**

The page where a customer reviews and confirms an order.

- **Source:** [GitHub 77](https://github.com/absaoss/payments-service/issues/77)
- **Surface:** page
- **Owners:** team-payments
- **User stories:** [US-001](#us-001)
- **Functionalities:** [FUNC-001](#func-001)
- **Feature dependencies:** FEAT-002
- **External dependencies:** payments-api
- **Wizard steps:** cart-review, payment, confirmation

**Notes**

- The checkout markup comes from the shared storefront template.

**Pages**

- /checkout: CheckoutPage.ts (primary). The screen where a customer reviews and confirms an order.
    - **Owners:** team-payments
- /checkout/confirmation: CheckoutConfirmationPage.ts. The screen shown after a successful payment.
    - **Owners:** team-payments
    - **Functionalities:** [FUNC-001](#func-001)
    - **Notes:**
        - The confirmation screen is reached only through the payment step.

## Functionalities

### FUNC-001

**Validate card number** `ACTIVE`

Validates the card number using the Luhn algorithm before submission.

- **Source:** [GitHub 88](https://github.com/absaoss/payments-service/issues/88)
- **Type:** API
- **Parent:** [FEAT-001](#feat-001)
- **Rationale:** Prevents obviously invalid card numbers from reaching the payment gateway.

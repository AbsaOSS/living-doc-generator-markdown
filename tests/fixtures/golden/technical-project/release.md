# Payments service

*View: release · version 1.4.0 · 9 of 9 entities and 7 of 11 acceptance criteria selected*

## Contents

- User Stories
    - [US-001](#us-001) Checkout with a saved payment method
    - [US-002](#us-002) Checkout as a guest
    - [US-010](#us-010) Unified checkout
- Features
    - [FEAT-001](#feat-001) Checkout page
    - [FEAT-002](#feat-002) Payments API
    - [FEAT-003](#feat-003) Legacy payment page
- Functionalities
    - [FUNC-001](#func-001) Validate card number
    - [FUNC-002](#func-002) Charge a saved card
    - [FUNC-003](#func-003) Charge through the legacy gateway

## User Stories

### US-001

**Checkout with a saved payment method** `ACTIVE`

As a customer, I want to check out with a saved payment method, so that I can complete my purchase quickly.

- **Source:** [GitHub 501](https://github.com/absaoss/payments-service/issues/501)
- **Linked issue:** [https&#58;//github.com/absaoss/payments-service/issues/42](https://github.com/absaoss/payments-service/issues/42)
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
- **Superseded by:** [US-010](#us-010)

**Acceptance criteria**

#### AC:US-002-01 (v1.5.0 - deprecated - removal planned v2.1.0)

A customer can check out as a guest, without creating an account.

- removal planned v2.1.0

### US-010

**Unified checkout** `ACTIVE`

As a customer, I want one checkout flow, whether or not I have an account.

- **Source:** [GitHub 512](https://github.com/absaoss/payments-service/issues/512)

**Notes**

- Guest checkout moved into this flow when US-002 was retired.

## Features

### FEAT-001

**Checkout page**

The page where a customer reviews and confirms an order.

- **Source:** [GitHub 77](https://github.com/absaoss/payments-service/issues/77)
- **Surface:** UI
- **Owners:** team-payments
- **User stories:** [US-001](#us-001)
- **Functionalities:** [FUNC-001](#func-001)
- **Feature dependencies:** [FEAT-002](#feat-002)
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

### FEAT-002

**Payments API**

The API the checkout page charges a customer's payment method through.

- **Source:** [GitHub 78](https://github.com/absaoss/payments-service/issues/78)
- **Surface:** API
- **Owners:** team-payments
- **Functionalities:** [FUNC-002](#func-002)

### FEAT-003

**Legacy payment page** `DEPRECATED`

The legacy gateway's page where a customer typed in card details.

- **Source:** [AzureDevOps 4105](https://dev.azure.com/absaoss/payments/_workitems/edit/4105)
- **Tags:** payments, legacy
- **Surface:** UI
- **Owners:** team-payments
- **Functionalities:** [FUNC-003](#func-003)
- **Superseded by:** [FEAT-001](#feat-001)

**Pages**

- /checkout/legacy-payment: LegacyPaymentPage.ts (primary). The screen where a customer typed in card details for the legacy gateway.
    - **Owners:** team-payments

## Functionalities

### FUNC-001

**Validate card number** `ACTIVE`

Validates the card number using the Luhn algorithm before submission.

- **Source:** [GitHub 88](https://github.com/absaoss/payments-service/issues/88)
- **Type:** field\_validation
- **Parent:** [FEAT-001](#feat-001)
- **Rationale:** Prevents obviously invalid card numbers from reaching the payment gateway.

### FUNC-002

**Charge a saved card** `ACTIVE`

Charges a customer's saved card and returns the payment id.

- **Source:** [GitHub 89](https://github.com/absaoss/payments-service/issues/89)
- **Parent:** [FEAT-002](#feat-002)
- **Rationale:** One call per charge keeps a retried request from charging the card twice.

**Notes**

- The API reads a card token from the vault; it never stores the card number.

**Acceptance criteria**

#### AC:FUNC-002-01 (v1.2.0 - active)

The API charges a saved card and returns the payment id.

- **Aspect:** visa, mastercard
- **Rationale:** The payment id lets the checkout page confirm the order without a second call.
- **Also requires:**
    - The card is saved to the customer's account.
- **Also not in scope:**
    - Refunds.

#### AC:FUNC-002-04 (v1.2.0 - active)

The API declines a charge on a card that is \{decline-reason\}.

- **decline\_reason:** expired, blocked

#### AC:FUNC-002-05 (v1.2.0 - deprecated - removal planned v2.0.0)

The API returns the card's last four digits with the payment id.

- removal planned v2.0.0

### FUNC-003

**Charge through the legacy gateway** `DEPRECATED`

Charges a card through the legacy payment gateway.

- **Source:** [AzureDevOps 4106](https://dev.azure.com/absaoss/payments/_workitems/edit/4106)
- **Linked issue:** [https&#58;//dev.azure.com/absaoss/payments/\_workitems/edit/3988](https://dev.azure.com/absaoss/payments/_workitems/edit/3988)
- **Tags:** payments, legacy
- **Type:** button\_action
- **Parent:** [FEAT-003](#feat-003)
- **Superseded by:** [FUNC-002](#func-002)
- **Rationale:** Kept until every merchant account has moved to the Payments API.

**Preconditions**

- The merchant account at the legacy gateway is still open.

**Not in scope**

- Saved cards.

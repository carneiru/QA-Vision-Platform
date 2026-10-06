@checkout @priority:low
Feature: Checkout
  Paying for the cart.

  Background:
    Given a signed-in shopper

  @smoke @ado:81284 @priority:high
  Scenario: Pay by card
    The happy path.
    When I pay with a stored card
      | brand | last4 |
      | visa  | 4242  |
    Then the order is confirmed
      """json
      {"status": "confirmed"}
      """

  Scenario: Pay by card
    When I pay again

  @Has:Colon @bad!tag
  Scenario: Tag edge cases
    Given nothing

  Rule: Coupons
    Background:
      Given a coupon "SAVE10"

    Scenario Outline: Apply <code>
      When I apply "<code>"
      Then the total drops by <off>

      Examples:
        | code   | off |
        | SAVE10 | 10  |
        | SAVE20 | 20  |

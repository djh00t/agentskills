Feature: Parse an owner's answer text

  Scenario: a widget tap is an option
    Given the reply text is "152: B, Keep the old layout"
    Then it parses as option 152 B

  Scenario: a bare token is an option
    Given the reply text is "126: A"
    Then it parses as option 126 A

  Scenario: a token without a colon is an option
    Given the reply text is "#9 c"
    Then it parses as option 9 C

  Scenario: a token with a reason is an option
    Given the reply text is "152: B, move all of them"
    Then it parses as option 152 B

  Scenario: approve N picks the recommendation
    Given the reply text is "approve 7"
    Then it parses as option 7 rec

  Scenario: free text naming one id is custom
    Given the reply text is "40 do the second one but later"
    Then it parses as custom 40

  Scenario: a hash id inside text is custom
    Given the reply text is "For #12 the banner can wait"
    Then it parses as custom 12

  Scenario: a question is a question
    Given the reply text is "What does option B change?"
    Then it parses as question without an id

  Scenario: a question with an id keeps the id
    Given the reply text is "#31 is this reversible?"
    Then it parses as question 31

  Scenario: text with no id is ambiguous
    Given the reply text is "Looks good to me"
    Then it parses as ambiguous

  Scenario: two ids are ambiguous
    Given the reply text is "#3 and #4 both A"
    Then it parses as ambiguous

  Scenario: empty text is ambiguous
    Given the reply text is "   "
    Then it parses as ambiguous

  Scenario: a letter beyond D is not an option
    Given the reply text is "5: E"
    Then it parses as custom 5

  Scenario: words are kept exactly
    Given the reply text is "  126: a "
    Then it parses as option 126 A with the original words

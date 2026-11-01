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

  Scenario: a full-width option is normalized
    Given the reply text is "152：Ｂ"
    Then it parses as option 152 B

  Scenario: an invisible character is removed from an option
    Given the reply text is "152: B\u200b"
    Then it parses as option 152 B

  Scenario: a question id is found after normalization
    Given the reply text is "\u200b152: B?"
    Then it parses as question 152

  Scenario: a question takes precedence over multiple decisions
    Given the reply text is "152: B? 153: A"
    Then it parses as question 152

  Scenario: a question mark in a reason takes precedence over an option
    Given the reply text is "152: B, is that ok?"
    Then it parses as question 152

  Scenario: a full-width question mark is a question
    Given the reply text is "152: B, ok？"
    Then it parses as question 152

  Scenario: any supported Unicode question mark anywhere makes the reply a question
    Given the reply text is "152: B, ok<mark>" for each listed mark
    Then it parses as question 152
    Examples: U+037E, U+061F, U+2E2E, U+203D, U+2E18, U+1F679, U+1F67A, U+1F67B, U+2048, U+055E, U+1367

  Scenario: question text remains a question after punctuation or invisible text
    Given the reply text is "152: B, ok?<tail>" for each listed tail
    Then it parses as question 152
    Examples: empty, !, " thanks", "\n\nthanks", U+3164, U+2800, U+034F, U+FE0F

  Scenario: a trailing zero-width space does not hide a question
    Given the reply text is "152: B?\u200b"
    Then it parses as question 152

  Scenario: a second decision in a reason is ambiguous
    Given the reply text is "152: B. Also #153: A"
    Then it parses as ambiguous

  Scenario: a second decision on a new line is ambiguous
    Given the reply text is "152: B\n153: A"
    Then it parses as ambiguous

  Scenario: a second hash id in a reason is ambiguous
    Given the reply text is "152: B, see #153"
    Then it parses as ambiguous

  Scenario: a second space-form decision is ambiguous
    Given the reply text is "152: B and 153 C"
    Then it parses as ambiguous

  Scenario: a second lowercase decision is ambiguous
    Given the reply text is "152: b\n153: a"
    Then it parses as ambiguous

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

  Scenario: bounded and safe answer text
    Given a reply exceeds the text limit or contains control characters
    Then it parses as ambiguous
    And invisible characters are removed from accepted words
    And numeric reasons and mixed-case approval remain valid

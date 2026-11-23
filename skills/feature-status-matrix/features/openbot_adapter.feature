Feature: OpenBot feature status matrix adapter
  The normal request entry renders release data from a local source and replies
  through the supplied sink. Acceptance uses synthetic fixtures only.

  BLOCKED is a blocker by default. The comma-separated blocker_statuses setting
  extends that default; entries are trimmed and matched case-insensitively.
  Other status text stays visible without a blocker marker.

  Scenario: Full mode returns the ordered release matrix and fixture issue details
    Given two ordered synthetic releases and linked issue details
    When a full matrix request uses the fixture source and reply-capturing sink
    Then the exact full Markdown is returned and captured once
    And its canonical fixture links read back the corresponding acceptance details

  Scenario: Release mode returns only the selected release
    Given two ordered synthetic releases
    When a release matrix request selects the second release
    Then only that release appears in the exact returned and captured Markdown

  Scenario: Configured blocker statuses extend the default
    Given a default blocker and additional and unknown fixture statuses
    When comma-separated blocker statuses include trimmed mixed-case values
    Then default and configured blockers receive a warning marker
    And the unknown status remains visible without a warning marker

  Scenario: Invalid mode does not reply
    When a matrix request has an unsupported mode
    Then the adapter raises ValueError without replying

  Scenario: Missing release selector does not reply
    When a release request has no release selector
    Then the adapter raises ValueError without replying

  Scenario: Unknown release selector does not reply
    When a release request selects an unknown release
    Then the adapter raises ValueError without replying

  Scenario: Malformed blocker configuration does not reply
    When the blocker status configuration has no usable values
    Then the adapter raises ValueError without replying

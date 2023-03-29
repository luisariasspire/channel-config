@fixture.config.isolated
Feature: operators can make basic edits

  Most changes to the channel configuration are fairly basic. The `channel_tool` command supports
  making these changes in a safe way across a large number of satellites, ground stations, or
  channels.

  Scenario: disabling a channel
    Given the satellite 'FM0' has 'CONTACT_BIDIR' enabled in its configuration file
    When I run 'python -m channel_tool edit staging FM0 CONTACT_BIDIR --enabled=false --yes'
    Then the channel 'CONTACT_BIDIR' on satellite 'FM0' will be marked disabled

  Scenario: adding a new channel from a template
    Given the satellite 'FM0' does not have 'CONTACT_BIDIR' in its configuration file
    When I run 'python -m channel_tool add staging FM0 CONTACT_BIDIR --yes'
    Then the satellite 'FM0' has 'CONTACT_BIDIR' in its configuration file

  Scenario: adding a new channel from a template with customizations
    Given the satellite 'FM0' does not have 'CONTACT_BIDIR' in its configuration file
    When I run 'python -m channel_tool add staging FM0 CONTACT_BIDIR --contact_type=CONTACT_SPACE_GROUND_BIDIR --yes'
    Then the satellite 'FM0' has 'CONTACT_BIDIR' in its configuration file
    And the channel 'CONTACT_BIDIR' on satellite 'FM0' has contact_type set to CONTACT_SPACE_GROUND_BIDIR

  Scenario: deleting a channel
    Given the satellite 'FM0' has 'CONTACT_BIDIR' in its configuration file
    And the satellite 'FM0' has 'CONTACT_RXO' in its configuration file
    When I run 'python -m channel_tool delete staging FM0 CONTACT_BIDIR --yes'
    Then the satellite 'FM0' does not have 'CONTACT_BIDIR' in its configuration file

  Scenario: editing a channel with a custom name
    Given the satellite 'FM0' has 'X_BAND_TXO' in its configuration file
    When I successfully run 'python -m channel_tool edit staging --contact_overhead_time=999s FM0 X_BAND_TXO --yes'
    Then the satellite 'FM0' has 'X_BAND_TXO' in its configuration file
    And the channel 'X_BAND_TXO' on satellite 'FM0' has contact_overhead_time set to 999s

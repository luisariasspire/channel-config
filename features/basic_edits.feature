@fixture.config.isolated
Feature: operators can make basic edits

  Most changes to the channel configuration are fairly basic. The `channel_tool` command supports
  making these changes in a safe way across a large number of satellites, ground stations, or
  channels.

  Scenario: disabling a channel
    Given the satellite 'FM0' has 'S_U_BIDIR_SPIRE_BW1_LEG_F2022_5' enabled in its configuration file
    When I successfully run 'python -m channel_tool edit staging FM0 S_U_BIDIR_SPIRE_BW1_LEG_F2022_5 --enabled=false --yes'
    Then the channel 'S_U_BIDIR_SPIRE_BW1_LEG_F2022_5' on satellite 'FM0' will be marked disabled

  Scenario: adding a new channel from a template
    Given the satellite 'FM0' does not have 'S_U_BIDIR_SPIRE_BW1_LEG_F2022_5' in its configuration file
    When I successfully run 'python -m channel_tool add staging FM0 S_U_BIDIR_SPIRE_BW1_LEG_F2022_5 --yes'
    Then the satellite 'FM0' has 'S_U_BIDIR_SPIRE_BW1_LEG_F2022_5' in its configuration file

  Scenario: adding a new channel from a template with customizations
    Given the satellite 'FM0' does not have 'S_U_BIDIR_SPIRE_BW1_LEG_F2022_5' in its configuration file
    When I successfully run 'python -m channel_tool add staging FM0 S_U_BIDIR_SPIRE_BW1_LEG_F2022_5 --contact_type=CONTACT_SPACE_GROUND_TXO --yes'
    Then the satellite 'FM0' has 'S_U_BIDIR_SPIRE_BW1_LEG_F2022_5' in its configuration file
    And the channel 'S_U_BIDIR_SPIRE_BW1_LEG_F2022_5' on satellite 'FM0' has contact_type set to CONTACT_SPACE_GROUND_TXO

  Scenario: deleting a channel
    Given the satellite 'FM0' has 'S_U_BIDIR_SPIRE_BW1_LEG_F2022_5' in its configuration file
    And the satellite 'FM0' has 'S_TXO_SPIRE_BW1_LEG_F2022_5' in its configuration file
    When I successfully run 'python -m channel_tool delete staging FM0 S_U_BIDIR_SPIRE_BW1_LEG_F2022_5 --yes'
    Then the satellite 'FM0' does not have 'S_U_BIDIR_SPIRE_BW1_LEG_F2022_5' in its configuration file

  Scenario: editing a channel
    Given the satellite 'FM0' has 'X_TXO_SPIRE_BW10_P5' in its configuration file
    When I successfully run 'python -m channel_tool edit staging --contact_overhead_time=999s FM0 X_TXO_SPIRE_BW10_P5 --yes'
    Then the satellite 'FM0' has 'X_TXO_SPIRE_BW10_P5' in its configuration file
    And the channel 'X_TXO_SPIRE_BW10_P5' on satellite 'FM0' has contact_overhead_time set to 999s

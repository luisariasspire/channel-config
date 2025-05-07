@fixture.config.isolated
Feature: operators can create new asset configurations

  We launch new satellites and turn on new ground stations frequently. The channel configuration
  system needs to be kept in sync with these launches. To make this easy, there are a few features
  built in to `channel_tool`.

  The first of these you'll likely use is the _template_ support. New assets can be pre-configured
  with default data for known channels by using the `add` command. All of the templates are defined
  in the `templates.yaml` file, so if you need to add a new channel be sure to update it there.

  After you have a configuration, you'll probably want to selectively enable a few channels. When
  configurations are created from templates, all of the channels start out disabled and are not
  marked as legal. You can enable the desired channels using the `edit` command.

  Note that channels need to be both _legal_ and _enabled_ to be used by the scheduler.

  Scenario: adding a new ground station
    Given there is no configuration for the ground station 'testgs'
    When I run 'python -m channel_tool add staging testgs all --yes'
    Then there is a valid configuration for the ground station 'testgs'
    And the configuration for the ground station 'testgs' will have no enabled channels

  Scenario: adding a new satellite
    Given there is no configuration for the satellite 'FM0'
    When I run 'python -m channel_tool add staging FM0 all --yes'
    Then there is a valid configuration for the satellite 'FM0'
    And the configuration for the satellite 'FM0' will have no enabled channels

  Scenario: marking channels as legal to use
    Given there is a valid configuration for the satellite 'FM0'
    When I run 'python -m channel_tool edit staging FM0 S_U_BIDIR_SPIRE_BW1_LEG_F2022_5 --legal=True --yes'
    Then the channel 'S_U_BIDIR_SPIRE_BW1_LEG_F2022_5' on satellite 'FM0' will be marked legal

  Scenario: marking channels as enabled
    Given there is a valid configuration for the satellite 'FM0'
    When I run 'python -m channel_tool edit staging FM0 S_U_BIDIR_SPIRE_BW1_LEG_F2022_5 --enabled=True --yes'
    Then the channel 'S_U_BIDIR_SPIRE_BW1_LEG_F2022_5' on satellite 'FM0' will be marked enabled

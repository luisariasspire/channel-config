@fixture.config.isolated
Feature: `channel_tool` supports editing embedded YAML structures

  The channel configuration files have a moderately-complex schema. In addition to some simple
  fields like `enabled` and some simple composites such as `allowed_license_countries`, the files
  include a handful of embedded structures which can be hard to edit by passing a flag for every
  element. Instead, the tool lets you edit these fields by:

  1. Writing the YAML you want in a separate file and passing the filename as an argument to the
  `--{field}_file` flag, or
  2. Passing the full structure as a string to the `--{field}` flag.

  (Generally speaking Option 1 is easier and recommended.)

  Scenario: overwrite a YAML array from a file
   Given the ground station 'testgs' has 'CONTACT_BIDIR_UHF' in its configuration file
   And a file 'link_profile.yaml' containing:
   """
   - min_elevation_deg: 25
     downlink_rate_kbps: 100.0
     uplink_rate_kbps: 10.0
     min_duration: 2min
   """
   When I run 'python -m channel_tool edit staging testgs CONTACT_BIDIR_UHF --link_profile_file link_profile.yaml --yes'
   Then it will exit with code '0'
   And the file 'staging/gs/testgs.yaml' will contain:
   """
     link_profile:
     - min_elevation_deg: 25
       downlink_rate_kbps: 100.0
       uplink_rate_kbps: 10.0
       min_duration: 2min
   """

  Scenario: remove a YAML structure from a file
   Given the ground station 'testgs' has 'CONTACT_BIDIR' in its configuration file
   And a file 'link_profile.yaml' containing:
   """
   - min_elevation_deg: 25
     downlink_rate_kbps: 300
     uplink_rate_kbps: 5.6
     min_duration: 20sec
   """
   When I run 'python -m channel_tool edit staging testgs CONTACT_BIDIR --link_profile_file link_profile.yaml --mode=remove --yes'
   Then it will exit with code '0'
   And the file 'staging/gs/testgs.yaml' will not contain:
   """
   - min_elevation_deg: 25
     downlink_rate_kbps: 300
     uplink_rate_kbps: 5.6
     min_duration: 20sec
   """

  Scenario: update a YAML structure within a file
   Given the ground station 'testgs' has 'CONTACT_BIDIR' in its configuration file
   And a file 'link_profile.yaml' containing:
   """
   - min_elevation_deg: 25
     downlink_rate_kbps: 300
     uplink_rate_kbps: null
     min_duration: 20sec
   """
   When I run 'python -m channel_tool --debug edit staging testgs CONTACT_BIDIR --link_profile_file link_profile.yaml --mode=update --yes --predicate "min_elevation_deg >= 25" -p "downlink_rate_kbps == 300"'
   Then it will exit with code '0'
   And the file 'staging/gs/testgs.yaml' will contain:
   """
     - min_elevation_deg: 25
       downlink_rate_kbps: 300
       uplink_rate_kbps: 5.6
       min_duration: 20sec
   """

  Scenario: update a YAML structure within a file
   Given the ground station 'testgs' has 'CONTACT_BIDIR' in its configuration file
   And a file 'goodput.csv' containing:
   """
   Goodput
   1000
   1200
   1400
   """
   When I run 'python -m channel_tool auto-update staging testgs CONTACT_BIDIR --parameter=link_profile --data-column=Goodput  --safety-factor=0.95 --calculation-method=ema --source-file="goodput.csv" -y'
   Then it will exit with code '0'
   And the file 'staging/gs/testgs.yaml' will contain:
   """
     - min_elevation_deg: 25
       downlink_rate_kbps: 1220.75
       uplink_rate_kbps: 5.6
       min_duration: 20sec
   """

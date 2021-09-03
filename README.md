# Channel Configuration

This directory contains config files and tools for managing the communications configuration for the
fleet on a per-channel basis. This approach replaced the `licensing.py` file, as described in
[Technical Proposal
#362](https://docs.google.com/document/d/1oOzPFOxtj3PFqRxY8ZnLOLie2oR95YMfxTyNKmKO9YU/edit?ts=5f80e012#).

## Installation

Use `pipenv` to install the needed dependencies:

```
pipenv install
```

This will create a managed virtual environment separate from the system Python installation,
ensuring consistency of versions across different people's machines.

If you don't have Pipenv set up, run the following:

```
brew update
brew install pyenv
pip install pipenv
```

Trouble? See the next section.

### Common Errors

If you have trouble with the installation and are getting error messages, see if any of the
following apply:

- `xcrun: error: invalid active developer path`: You're missing the Xcode command line tools. Brew
  should have installed them for you, but if you're encountering this error you can install them
  again with `xcode-select --install`.

None of the above? Reach out in `#ops-optimizer` on Slack.

## Getting Help

The tools are designed to be flexible, but that also makes them a bit challenging to learn. To help
you wrap your head around the tooling, here are a few resources:

### Built-in Help

First and foremost, every script in this project supports the `--help` flag and will print out usage
text that can guide you in crafting your commands. It's a good place to start to figure out what is
supported. The built-in help is always up to date as it is part of the executable code.

### Feature Files

In addition to the built-in help, the `features/` directory contains a set of human-readable
scenarios that we use to test that the tools work as intended. These show how the tools can be used
in a variety of contexts, and because they are part of the test suite they are always up to date!

### Video Walkthrough

On December 15th 2020, Nick Pascucci from the Optimizer team gave the Ops team an overview of the
tools and configurations managed here. The session was recorded, and the video can be found
[here](https://drive.google.com/file/d/1kWfVvtK_tnUGYoJ3ae4tm1Oq7AkIv2CN/view) (54 minutes).

(Obviously we're not recording new versions of this every time we change the tool, so the video will
get stale over time. That said, the fundamental principles should remain the same.)

### People

If none of the above meet your needs, feel free to reach out in `#ops-optimizer` in the ECT Slack
and we'll get you the info you need.

## Structure

The configuration for the fleet can be quite large, so it is broken up into several directories.

- There are separate `staging` and `production` configuration directories. In each:
  - `sat` contains configuration files for each satellite.
  - `gs` contains configuration files for each ground station.
- `templates` contains template configurations for each contact type, using common values.

Tools are configured using `pipenv`, and can be executed using `pipenv run <tool name>`. The major
scripts are:

- `channel_tool`, the primary script, which is used for editing configurations;
- `create_sat_configs`, which generates `channel_tool` commands to create satellite configurations;
- `create_gs_configs_from_licensing`, which generates `channel_tool` commands to create ground
  station configs;
- `sync_from_tk`, used to synchronize settings _from_ The Knowledge by generating `channel_tool`
  commands;
- and `sync_to_tk`, used to synchronize settings _to_ The Knowledge.

## Managing configurations

A basic workflow for maintaining the channel configuration is as follows:

1. Create configurations for any new channels using `channel_tool add`.
2. Update changed configurations by applying field edits with `channel_tool edit`. This may be
   repeated multiple times to apply all of the needed updates.
3. Double-check that the changes are valid with `channel_tool validate`.
4. Create a PR with your changes and merge it to `master`.

After the PR is merged, the edits are picked up automatically by SOC and made available to other
systems, such as the Optimizer; no extra deploy step is needed!

Each of the above steps are described in more detail below.

### Adding a new channel to an asset

Adding channels from a template to a ground station is simple:

```
pipenv run channel_tool staging add tosgs CONTACT_RXO_SBAND_FREQ_2200_MHZ --legal=True --enabled=True
```

We can do the same for satellites, and even update several at once:

```
pipenv run channel_tool staging add FM998,FM999 CONTACT_BIDIR --legal=True
```

Note the structure of the command. First we have `pipenv run channel_tool`, which calls the tooling
within the correct virtual environment so that all of the needed modules are available. Next comes
an environment, `staging`, and a subcommand, in this case `add`. After that, we have a
comma-separated list of assets (ground stations or satellites), a comma-separated list of channel
names (i.e. contact types), and finally flags that set overrides on the template fields. In the
examples above we populated channel definitions for FM998 & FM999 from a template specifying the
default values that `CONTACT_BIDIR` should have, and overrode the `legal` field, which is normally
`False`, with the `True` value. (We did something similar for TOSGS, and we also set the `enabled`
field to `True`.)

_All of the commands in `channel_tool` follow this pattern. Use `pipenv run channel_tool --help` to
get more detailed information on the various subcommands._

If we try to add a configuration which already exists we get an error:

```
$ pipenv run channel_tool staging add tosgs CONTACT_RXO_SBAND_FREQ_2200_MHZ --legal=True
Error: Configuration for CONTACT_RXO_SBAND_FREQ_2200_MHZ already exists on tosgs.
(Tip: Use `channel_tool edit tosgs CONTACT_RXO_SBAND_FREQ_2200_MHZ` to edit the configuration.)
```

### Batch-editing a channel across satellites

Although the channel configurations are stored in human readable YAML format, it can be a pain to
have to bulk-edit lots of channel definitions by hand. You can use the tooling to help with
this. The `edit` command will apply field-level changes to the specified channel configurations on a
given set of assets:

```
$ pipenv run channel_tool staging edit tosgs CONTACT_RXO_SBAND_FREQ_2200MHZ \
    --enabled=true --legal=true
Changing asset configuration for CONTACT_RXO_SBAND_FREQ_2200_MHZ on tosgs. Diff:
---
+++
@@ -3,7 +3,7 @@
 - US
 - SG
 - LU
-enabled: false
+enabled: true
 legal: true
 ground_station_constraints:
   min_elevation_deg: 25.0

Update asset configuration? [y/N] y
Updated CONTACT_RXO_SBAND_FREQ_2200_MHZ definition for tosgs.
```

Here, we set the `enabled` and `legal` fields for TOSGS' `CONTACT_RXO_SBAND_FREQ_2200_MHZ` channel,
which we `add`ed above. The tool will make the changes for you and validate that all of the fields
are of the correct type, such as checking that the license countries are valid and that the channel
conforms to the latest schema. This makes it easy to edit the configuration and be confident that
the result is sound. Note also that the tool provides a diff for each edit it makes, showing that
the `legal` field was already `true` and did not need to change, while `enabled` was updated from
`false` to `true` as requested. You will have the option to cancel each change if you don't want to
apply it.

To skip confirmations, use the `--yes` option; this is generally safe to do as long as you review
the changes before merging your PR (which you're always doing _regardless_, right?). Use
`--fail-fast` to tell the tool to stop as soon as it encounters an error and skip remaining
edits. This is useful when you expect that a configuration exists and want to stop if that
expectation is wrong.

### Validation

All edits performed using `channel_tool` as described above are automatically validated against a
JSON Schema representation of the config file format. However, if a manual change is made to a
configuration file or a template (or you just want to be 100% certain your change was valid), it can
be necessary to run the validation manually. Channel configurations and templates can be validated
with a single command:

```
pipenv run channel_tool validate
```

This will check all of the configurations in both `staging` and `production` to verify they conform
to the expected format.

### Setting channel constraints

Channels can be configured with asset-specific constraints, such as a minimum elevation for a ground
station or a separation requirement for a satellite. To set these in bulk, create a temporary YAML
file with the desired constraint. For example:

```yaml
# /tmp/constraints.yml
separation:
  - type: no_overlapping_transits
    norad_id: 25544 # ISS
```

Then use `channel_tool` to set it on the desired satellites or ground stations:

```bash
pipenv run channel_tool edit staging FM137,FM142 uhf --yes \
    --satellite_constraints "$(cat /tmp/constraints.yml)"
```

## Examples

### Disabling BIDIR channels on a ground station (set RXO-only)

```bash
pipenv run channel_tool edit production wbugs bidir --enabled=False \
    --comment "BIDIR disabled due pending USRP repairs"
```

### Disabling a ground station entirely

```bash
pipenv run channel_tool edit production cosngs all --enabled=False --yes
```

### Enabling S-band only at 2200MHz on a satellite

```bash
pipenv run channel_tool edit production FM96 sband_2020 --enabled=False --yes
pipenv run channel_tool edit production FM96 sband_2200 --enabled=True --yes
```

## Helper Tools

### Synchronization with The Knowledge

Two scripts, `sync_from_tk` and `sync_to_tk`, are provided to do bidirectional synchronization
between these config files and The Knowledge. Each can be called using `pipenv run <tool>` and use
the channel definitions in `contact_type_defs.yaml`.

Pulling configuration from TK involves reading TK's settings for each asset given on the command
line and generating a series of `channel_tool` edit commands which will bring the config file in
line with those settings. Conversely, synchronizing _to_ The Knowledge is done by reading each of
the asset files and computing what settings in TK would be needed to produce that exact set of
enabled and disabled channels.

Note that it is possible to represent some configurations in the channel config files that can't be
represented in TK! For example, it is possible to turn on `CONTACT_RXO_SBAND_FREQ_2200_MHZ` without
also turning on `CONTACT_RXO` in the YAML files, but not in TK because the 2200MHz contact types
require both `sbnad_enabled` and `sband_2200mhz` to be `True`. The mappings for which TK settings
are needed for each contact type are provided in `legacy/tk_settings_mapping.yaml` and refer to the
group definitions in `contact_type_defs.yaml`. In the case where the channel configuration can't be
represented in TK at all, the `sync_to_tk` script will signal an error showing the conflict.

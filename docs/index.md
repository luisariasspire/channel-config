# Channel Configuration Reference Documentation

This is the reference documentation for the channel configuration and associated tooling. It is a
supplement to the README for those needing more details on specific semantics or operations.

## Channels

Channels are defined as entries in a YAML map, where the keys are user-defined strings and the
values are configuration blocks containing specific properties. A machine-readable schema for these
properties is defined in `schema.yaml`. In this section you will find detailed descriptions of each
field, how the fields are used, and how channel configuration blocks are merged when deciding if a
contact can be scheduled. 

### Core Properties

All channel definitions include the following core properties.

- `legal`: A boolean indicating if this channel is licensed for use through an appropriate
  regulatory body (e.g. the FCC). Generally this should be `true`; it is provided to indicate that a
  channel has been temporarily disabled due to regulatory issues.
- `enabled`: A boolean indicating if the channel is enabled for use in contact scheduling.
- `directionality`: One of `Bidirectional`, `SpaceToEarth`, or `EarthToSpace` indicating the
  direction of information flow on this channel.
- `contact_type`: An optional string indicating the contact type to use when scheduling contacts
  generated with this configuration. If unset, the default behavior is to use the name of the
  channel.
- `contact_overhead_time`: A [_humantime_][1]-formatted string indicating how much time at the
  beginning of the contact is used for "overhead" activities which do not contribute to payload data
  transfer such as maintenance and schedule synchronization.
- `allowed_license_countries`: A set of ISO3166 country codes. A partner asset must be licensed in
  one of these countries for this channel to be legal to use.
- `link_profile`: A sequence of link profile segments used to define elevation-dependent behavior.
  See the below section on "Link Profiles" for more details on this field.
- `window_parameters`: A JSON object containing the _static_ window parameters. This object is
  merged with dynamic parameters given in the link profile during contact scheduling. See "Window
  Parameter Merge Semantics" below for details on this process.

Additionally, satellites and ground stations will have their own constraint types under the
`satellite_constraints` or `ground_station_constraints` key, respectively. See "Constraints" below
for details.

### Link Profiles

- TODO Field definitions
- TODO Dynamic parameters

### Constraints

- TODO Definitions
- TODO Modifiers

### Geodetic Coordinates

Where coordinates for ground stations are required in constraints or other objects, they are given
in a geodetic latitude, longitude, and height format using the WGS84 reference ellipsoid.

The `longitude` is given in decimal degrees with longitudes East of the prime meridian being
positive and values to the West being negative.

The `latitude` is given in decimal degrees with latitudes North of the equator being positive and
those South being negative.

The `elevation_m` is the height above the WGS84 reference ellipsoid expressed in meters.

**Note:** This format differs from the one used in The Knowledge, where the sign of longitude is
reversed. The coordinate system used in the channel config matches the one used by GPS and most
national cartography organizations.

## Scheduling

Ultimately, the goal of all of this configuration is to make it possible to create contacts between
pairs of satellites and ground stations. To do so we need to be able to find matching channels
between the two parties, and resolve any differences in configuration between them in a predictable
way.

### Matching Criteria

For two assets - _A_ and _B_ for short here - to be able to communicate on a given channel, they
must meet the following criteria:

1. The channel must exist in both _A_ and _B_'s configuration with the exact same name.
2. It must have both `legal` and `enabled` set to `true` on both the _A_ and _B_ configurations.
3. _A_ must be licensed in a country which is listed in _B_'s `allowed_license_countries` set and
   vice-versa.
4. The `directionality` must match on both sides.

Additionally, over the course of the proposed contact (a "transit" in Optimizer terms), the
following must hold at all times:

1. All `ground_station_constraints` and `satellite_constraints` which are not negated by a modifier
   must be satisfied.
2. For each link profile segment (of the merged configuration) where the satellite exceeds the
   `min_elevation_deg`, the satellite must remain above that segment's `min_elevation_deg` for at
   least the `min_duration` given.

### Window Parameter Merge Semantics

Each contact involves two assets. Each of these has their own set of static
`window_parameters` defined at the top level of the channel's configuration object, and
elevation-dependent parameters defined in the link profile. 

The `parameters` object for each contact created from a pair of matching channels is created by
merging the static parameters and elevation-dependent parameters into a single object with
specific precedence rules.

- Static parameters are merged with satellite parameters taking priority over ground station ones.
- Dynamic parameters take priority over static ones. These parameters are taken from
  the set of segments from the combined link profile, described below, which are entered by the
  satellite during the contact.

To create the combined link profile we apply the following high-level procedure.

Starting from the highest segment of each asset's profile, progressively walk each link profile in
reverse order of their `minimum_elevation_deg`, creating a combined segment at each
`minimum_elevation_deg` "break point" of the two parent profiles. For each sub-segment, merge the
parent segments according to the segment merge rules below.

Merge each pair of sub-segments by applying these rules:

1. Take the _maximum_ of the `min_elevation_deg` from each parent.
2. Take the _minimum_ of the `downlink_rate_kbps` and `uplink_rate_kbps` from each parent.
3. Take the `min_duration` from the parent with the _higher_ `min_elevation_deg`. If they have the
   same `min_elevation_deg`, take the maximum of the two `min_duration` values.
4. Recursively merge the window parameters of the two parents, with the parent with the _lower_
   `min_elevation_deg` taking priority.

Diagrammatically, for two profiles _A_ and _B_ this looks like:

```
(Note: X|Y is "merge X with Y prioritizing X")

[A]    [B]      [A|B]
┌─┐ 90 ┌─┐       ┌─┐
│ │    │ │       │ │  min_elevation_deg = 60
│ │    │ │       │ │  min_duration      = B
│ │    │ │       │ │  window_params     = A|B
│ │    │ │       │ │
│ │    │ │       │ │
│ │    │ │       │ │
│ │    │ │       │ │
│ │ 60 ├─┤       ├─┤
│ │    │ │       │ │  min_elevation_deg = 30
│ │    │ │       │ │  min_duration      = B
│ │    │ │       │ │  window_params     = A|B
│ │    │ │       │ │
│ │    │ │       │ │
│ │    │ │       │ │
│ │ 30 ├─┤       ├─┤
│ │    │ │       │ │  min_elevation_deg = 10
│ │    │ │       │ │  min_duration      = A
│ │    │ │       │ │  window_params     = B|A
│ │    │ │       │ │
├─┤ 10 │ │       ├─┤
│ │    │ │       │ │  min_elevation_deg =  0
│ │    │ │       │ │  min_duration      = max(A, B)
│ │    │ │       │ │  window_params     = A|B
└─┘  0 └─┘       └─┘
```

[1]: https://docs.rs/humantime/latest/humantime/fn.parse_duration.html

#!/bin/bash

# Add antennas

# todo -- pull the antennas from TK?
environment=staging
for gs_id in at2kl ha2kl mn3kl pl2kl sg71kl; do
    poetry run python -m channel_tool add \
         --yes \
         --enabled true \
         --legal true \
         --allowed_license_countries US,SG,LU \
         --window_parameters '{}' \
         --link_profile '[{"min_elevation_deg": 10, "downlink_rate_kbps": 240.0, "uplink_rate_kbps": 0.0, "min_duration": "2min"}]' \
         ${environment} ${gs_id} CONTACT_KSATLITE_SBAND_SPACE_GROUND_TXO
done 

satellites=`grep -rl CONTACT_RXO_SBAND_FREQ_2200_MHZ ${environment}/sat | sed 's/.*\(FM[0-9]\{1,5\}\).*/\1/'`

for sat_id in ${satellites}; do
    poetry run python -m channel_tool add \
        --yes \
        --enabled true \
        --legal true \
        --allowed_license_countries GR,ZA,AU,ES,NO \
        --satellite_constraints '{"max_contact_time": {"amount": "600s", "interval": "1day"}}' \
        ${environment} ${sat_id} CONTACT_KSATLITE_SBAND_SPACE_GROUND_TXO
done

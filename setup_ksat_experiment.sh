#!/bin/bash

# todo -- allow prod rather than staging
environment=staging
antenna_gs_ids=( $(curl -X GET https://theknowledge.staging.spire.sh/v3/groundstations -H "authorization: Bearer $TK_TOKEN_STAGING" | jq -r '.[] | select(.gs_id|endswith("kl")) | .gs_id') )

for gs_id in "${antenna_gs_ids[@]}"; do
    poetry run python -m channel_tool add \
         --yes \
         --enabled true \
         --legal true \
         --allowed_license_countries US,SG,LU \
         --window_parameters_file fragments/ksatlite_sband_rxo_parameters.yaml \
	 --ground_station_constraints '{"fixed_contact_duration": "4min"}' \
         --link_profile '[{"min_elevation_deg": 10, "downlink_rate_kbps": 564.01, "uplink_rate_kbps": 0.0, "min_duration": "2min"}]' \
         ${environment} ${gs_id} CONTACT_KSATLITE_SBAND_SPACE_GROUND_TXO
done 

satellites=`grep -rl CONTACT_RXO_SBAND_FREQ_2200_MHZ ${environment}/sat | sed 's/.*\(FM[0-9]\{1,5\}\).*/\1/'`

license_countries=( $(curl  -X GET https://theknowledge.staging.spire.sh/v3/groundstations -H "authorization: Bearer $TK_TOKEN_STAGING" | jq -r '.[] | select(.gs_id|endswith("kl")) | .license_country' | sort -u) )
license_countries_string=$(printf ",%s" "${license_countries[@]}")
license_countries_string=${license_countries_string:1}

for sat_id in ${satellites}; do
    poetry run python -m channel_tool add \
        --yes \
        --enabled true \
        --legal true \
        --allowed_license_countries ${license_countries_string} \
        ${environment} ${sat_id} CONTACT_KSATLITE_SBAND_SPACE_GROUND_TXO
done

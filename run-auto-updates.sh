#!/bin/bash

for file in $HOME/downloads/data/*.csv
do
    # poetry run python -m channel_tool auto-update staging all_gs $(basename "$file" .csv) --parameter=link_profile --data-column=actual_downlink_kbps --source-file="$file" -y
    poetry run python -m channel_tool --debug auto-update staging all_gs $(basename "$file" .csv) --parameter=contact_overhead_time --data-column=overhead_time_upper_bound --source-file="$file" --safety-factor=0.85  -y
done
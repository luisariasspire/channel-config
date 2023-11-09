#!/bin/bash
# quick 'n' dirty script to find out which channels are not mentioned in
# contact_type_defs.yaml (they all should be!)
CHANNEL_IDS=`grep -oh ^\[0-9A-Z_\]\*:$ {production,staging}/{sat,gs}/*.yaml | sed s/://g | sort -u`
for CHANNEL_ID in $CHANNEL_IDS; do
    if ! grep -q $CHANNEL_ID "contact_type_defs.yaml"; then
	echo $CHANNEL_ID was NOT found in contact_type_defs.yaml
    fi
done

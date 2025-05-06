#!/bin/bash

function rename () {
    sed -i '' -e 's/^'${1}':/'${2}':/g' {production,staging}/{sat,gs}/*.yaml gs_templates.yaml sat_templates.yaml
    git add {production,staging}/{sat,gs}/*.yaml gs_templates.yaml sat_templates.yaml
    git commit -m "renamed channel "${1}" to "${2}
    poetry run python3 -m channel_tool format
    git add {production,staging}/{sat,gs}/*.yaml gs_templates.yaml sat_templates.yaml
    git commit -m "corrected channel ordering, moving newly renamed channel "$2    
}

rename TXO_XBAND X_TXO_SPIRE_BW10_P5
rename TXO_XBAND_ADCS_TRACK_BW_20_PLS_61 X_TXO_SPIRE_BW20_P61_TRACK
rename TXO_XBAND_BW_10_PLS_17 X_TXO_SPIRE_BW10_P17
rename TXO_XBAND_BW_10_PLS_21 X_TXO_SPIRE_BW10_P21
rename TXO_XBAND_BW_10_PLS_25 X_TXO_SPIRE_BW10_P25
rename TXO_XBAND_PROV_KSAT X_TXO_KSAT_BW10_P5
rename TXO_XBAND_PROV_KSAT_ADCS_TRACK_BW_20_PLS_49 X_TXO_KSAT_BW20_P49_TRACK
rename TXO_XBAND_PROV_KSAT_ADCS_TRACK_BW_20_PLS_61 X_TXO_KSAT_BW20_P61_TRACK
rename TXO_XBAND_PROV_KSAT_BW_10_PLS_17 X_TXO_KSAT_BW10_P17
rename TXO_XBAND_PROV_KSAT_BW_10_PLS_21 X_TXO_KSAT_BW10_P21
rename TXO_XBAND_PROV_KSAT_BW_10_PLS_25 X_TXO_KSAT_BW10_P25

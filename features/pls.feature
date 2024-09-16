Feature: `channel_tool pls` offers guidance on PLS and MTU values

    The characteristics of available DVBS2X PLS values are well defined.  However,
    those definitions are not always easy to find or interpret.   The `pls` 
    tool gives a summary of the parameters for different values, and offers
    suggestions based on the signal quality described.

    The output in all cases should include the PLS specified or determined, the
    MTU to be used in radionet, the required signal strength, and the expected
    transfer speed.  

    If a radio band is not specified, the suggestion to do so is offered.

    When a radio band (XBand or SBand) is given the constrains the PLS values and also
    lets the tool generate a complete parameter block including modes.  If radionet
    usage is also specified, that adds additional outputs in the parameter block.

  Scenario: look up PLS values by PLS
    When I run 'python -m channel_tool pls --pls 35'
    Then it should print text containing:
    """
    pls: 35  mtu: 1542 req SnR: 8.68 speed: 1.13
    """
    And it should print text containing:
    """
    Specify sband or xband to generate template
    """

  Scenario: generate radionet parameters for pls value
    When I run 'python -m channel_tool pls -p 35 -s'
    Then it should print text containing:
    """
    forward_channels:
    - bandaid_mode: TX_SBAND_DVB
      bandaid_override:
        fec: 255
        fec_k: 223
        pls: 35
      protocol: DVBS2X
      radio_band: SBAND
    """
    
  Scenario: look up PLS values by signal strength
    When I run 'python -m channel_tool pls --db 5.0 --sband --radionet'
    Then it should print text containing:
    """
    pls: 19  mtu: 867  req SnR: 5 speed: 0.636Mbps
    """
    And it should print text containing:
    """
    forward_channels:
    - bandaid_mode: TX_SBAND_DVB_IP
      bandaid_override:
        fec: 255
        fec_k: 223
        mtu: 867
        pls: 19
      ground_override:
        radionet-m: 867
      protocol: DVBS2X
      radio_band: SBAND
      use_radionet: true
    """

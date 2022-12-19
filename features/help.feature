Feature: `channel_tool` comes with built-in help

  The command-line interface for the `channel_tool` can be a bit daunting to use at first. How do
  you know what options are available? Fortunately, there are easy ways to ask the tool to describe
  itself. You can see usage help by passing the `--help` flag at any point in your command.

  Note that in the following scenarios each command should be run from within the Pipenv
  environment. You can do this two ways:

  1. Run `pipenv shell` to get a new sub-shell which is all set up to run things correctly, or
  2. Prefix your commands with `pipenv run` to have them temporarily run in the virtual environment.

  Scenario: print general help on the command line 
    When I run 'python -m channel_tool --help'
    Then it will exit with code '0'
    And it should print text containing:
    """
    usage: python -m channel_tool
    """

  Scenario: print subcommand help on the command line 
    When I run 'python -m channel_tool add --help'
    Then it will exit with code '0'
    And it should print text containing:
    """
    usage: python -m channel_tool add
    """
    
  Scenario: print help even with a partial command
    When I run 'python -m channel_tool add --yes --help'
    Then it will exit with code '0'
    And it should print text containing:
    """
    usage: python -m channel_tool add
    """

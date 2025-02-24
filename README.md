# G0-T0
For the Resolute discord bot

## Environment variables:
| Name                         | Description                                                                                                                                              | Used by/for                        | Required |
|------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------|----------|
| `ADMIN_GUILDS`               | Guilds where the `Admin` command group commands are available                                                                                            | DEV Team for command restrictions  | No       |
| `BOT_OWNERS`                 | Listed as the owners of the Bot for `Admin` command group command checks                                                                                 | DEV Team for command checks        | No       | 
| `BOT_TOKEN`                  | The token for your bot as found on the Discord Developer portal. See this documentation for more details: https://docs.pycord.dev/en/master/discord.html | Connections to Discord API         | **Yes**  |   
| `COMMAND_PREFIX`             | The command prefix used for this Bot's commands. For example, '>' would be the command prefix in `>rp @TestUser`. *Default is `>`*                       | Non-slash command prefix           | **Yes**  |
| `DASHBOARD_REFRESH_INTERVAL` | Refresh interval for dashboards in minutes. *Default is 15 minutes if not set.*                                                                          | `Dashboards` cog for task interval | No       |
| `DATABASE_URL`               | Full Postgres database URL. Example: `postgresql://<user>:<password>@<server>:<port>/<database>`                                                         | Connection to DB                   | **Yes**  |
| `GUILD`                      | Debug guilds for the bot. Used for non-production versions only.                                                                                         | Guild IDs for debugging            | No       |
| `ERROR_CHANNEL`              | 
| `AUTH_TOKEN`                 | Validation token for the Quart webservices                                                                                                               | Quart                               | No      |
| `PORT`                       | Port for the webserver                                                                                                                                   | Quart                               | No      |  

## Committing, Formatting, and Linting

G0-T0 uses [Black](https://black.readthedocs.io/) to format and lint its Python code.
Black is automatically run on every commit via pre-commit hook, and takes its configuration options from the `pyproject.toml` file.

The pre-commit hook is installed by by running `pre-commit install` from the repo root.
The hook's configuration is governed by the `.pre-commit-config.yaml` file.

#### Dependencies

In order to run `pre-commit` or `black`, they must be installed.
These dependencies are contained within the `tests/requirements.txt` file, and can be installed like so:

```bash
(venv) $ pip install -r tests/requirements.txt
```
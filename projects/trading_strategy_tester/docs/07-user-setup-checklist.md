# User setup checklist before coding can connect

Source reviewed:

- `docs/TWS API Documentation _ IBKR API _ IBKR Campus.pdf`

Relevant PDF sections/pages found locally:

- page 6: TWS or IB Gateway must be installed and running
- page 7: TWS API configuration settings
- pages 34-36: socket connection, `client_id`, and `nextValidId` handshake
- page 35: error `502` meaning
- page 38: localhost/trusted IP settings for remote connections
- page 43: default paper/live ports
- pages 57-60: account summary callbacks
- page 73: managed accounts callback
- pages 139-140: live/frozen/delayed/delayed-frozen market data types
- pages 141-145: historical data limitations and requests

## What You Need To Do First

1. Start TWS or IB Gateway.
2. Log into the IBKR Paper Trading account, not live.
3. In TWS, open:

```text
Edit -> Global Configuration -> API -> Settings
```

4. Enable socket clients:

```text
Enable ActiveX and Socket EClients
```

5. For future order testing, disable:

```text
Read-Only API
```

For our current smoke test, no orders are sent, but future bracket-order paper testing will need this disabled.

6. Verify socket port:

```text
TWS Paper: 7497
IB Gateway Paper: 4002
```

7. For local use, keep localhost-only connections enabled.

If connecting from another machine later, add that exact machine IP under Trusted IPs. The PDF notes Trusted IPs accepts individual IP addresses, not subnets.

8. Keep TWS unlocked.

If TWS locks or logs out, API connectivity can break. IB Gateway is usually better for long unattended sessions.

9. Run from project root:

```powershell
py scripts\check_ibkr_connection.py --config config\ibkr_config.yaml
```

For IB Gateway:

```powershell
py scripts\check_ibkr_connection.py --config config\ibkr_config.yaml --port 4002
```

10. Expected successful result:

- receives `nextValidId`
- receives current TWS time
- receives managed accounts
- selected account starts with `DU`
- receives account summary

## Connection Result

Initial local attempts against both standard paper ports returned IBKR error `502`.

That means Python cannot open a valid socket to TWS/Gateway yet.

Most likely causes:

- TWS or IB Gateway is not running
- logged into live instead of paper
- API socket clients are not enabled
- socket port is different from config
- Windows firewall or security software blocks localhost connection
- another TWS/Gateway instance is using a different port

After TWS was configured by the user, the connection passed on TWS paper port `7497`.

Gateway settings do not need to be visible in TWS. IB Gateway is a separate app. For this project, TWS on `7497` is sufficient.

## What I Can Do After You Start TWS/Gateway

Once TWS is open and API is enabled, I can run:

```powershell
py scripts\check_ibkr_connection.py --config config\ibkr_config.yaml
```

If it succeeds, the next checkpoint is:

1. verify market data type callbacks
2. request a tiny historical data sample
3. cache historical bars locally
4. keep paper trading in read-only signal mode

Completed after TWS setup:

- paper connection passed
- account summary was received
- historical sample request passed
- one `SPY` one-minute RTH bar was cached locally
- live market data probe showed missing live API subscription for `SPY`
- delayed market data probe returned delayed status and execution stayed blocked

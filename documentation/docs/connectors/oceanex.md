# OceanEx Connector

## About OceanEx

Launched by BitOcean Global in 2018, OceanEx is an AI powered digital asset
trading platform within the VeChainThor Ecosystem, offering professional
services to digital asset investors, traders and liquidity providers.

## Using the Connector

Because [OceanEx](https://oceanex.pro) is a centralized exchange, you will need to generate and provide your API key in order to trade using Hummingbot.

| Prompt |
|-----|
| `Enter your Ocean uid >>>`
| `Enter your Ocean private key file >>>`

!!! tip "Copying and pasting into Hummingbot"
    See [this page](https://docs.hummingbot.io/support/how-to/#how-do-i-copy-and-paste-in-docker-toolbox-windows) for more instructions in our Get Help section.

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

### Creating OceanEx API Keys

Follow instructions on https://api.oceanex.pro/doc/v1/#rest-authentication to create API keys.

The uid and private key file are required.

## Transaction Fees

OceanEx generally charges 0.1% on both maker and taker.
See https://oceanex.pro/en/fees for details and discounts.

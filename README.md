# Hummingbot (Oceanex Fork version) Introduction

1. [Change log](#Change-log)
2. [Introduction](#Introduction)
3. [Supported centralized exchanges](#Supported-centralized-exchanges)
4. [Getting Started](#Getting-Started)

## Change log

| Version            | Note              | date     |   
| ------------------ | ----------        | ---------|
| 0.0.1             | init version      |2020-03-10|

## Introduction 
This is a fork extended with an exchange connector for [OceanEx](https://oceanex.pro).
It is based on version 0.22.0.

Please refer to documentation inside this repo. This is the [index](documentation/docs/index.md).
The official Hummingbot documentation may contain newer information.
Refer to this [file](documentation/docs/connectors/oceanex.md) for information about the connector.

For installation, build from source using the manual option steps. Instructions for
[linux](https://docs.hummingbot.io/installation/from-source/linux/).
Don't forget to clone this repo instead of upstream Hummingbot repo.

You can use a docker image from our [repo](https://hub.docker.com/repository/docker/oceanexchange/hummingbot).
Below is a sample command.

    docker run -it --mount "type=bind,src=$(pwd)/conf,dst=/conf" --mount "type=bind,src=$(pwd)/logs,dst=/logs" --mount "type=bind,src=$(pwd)/data,dst=/data" oceanexchange/hummingbot:0.22.0


![Hummingbot](https://i.ibb.co/X5zNkKw/blacklogo-with-text.png)

----
[![Jenkins](https://jenkins-02.coinalpha.com/buildStatus/icon?job=hb_test-master_branch&subject=jenkins:master)](https://jenkins-02.coinalpha.com/job/hb_test-master_branch)
[![Jenkins](https://jenkins-02.coinalpha.com/buildStatus/icon?job=hb_test-development_branch&subject=:development)](https://jenkins-02.coinalpha.com/job/hb_test-development_branch)
[![Discord](https://img.shields.io/discord/530578568154054663.svg?color=768AD4&label=discord&logo=https%3A%2F%2Fdiscordapp.com%2Fassets%2F8c9701b98ad4372b58f13fd9f65f966e.svg)](https://discord.hummingbot.io/)
[![License](https://img.shields.io/badge/License-Apache%202.0-informational.svg)](https://github.com/CoinAlpha/hummingbot/blob/master/LICENSE)
[![Twitter Follow](https://img.shields.io/twitter/follow/hummingbot_io.svg?style=social&label=hummingbot)](https://twitter.com/hummingbot_io)

Hummingbot is an open-source project that integrates cryptocurrency trading on both **centralized exchanges** and **decentralized protocols**. It allows users to run a client that executes customized, automated trading strategies for cryptocurrencies.

We created hummingbot to promote **decentralized market-making**: enabling members of the community to contribute to the liquidity and trading efficiency in cryptocurrency markets.

## Supported centralized exchanges

| logo | id | name | ver | doc|
|:---:|:---:|:---:|:---:|:---:|
| <img src="https://i.ibb.co/m0YDQLd/Screen-Shot-2019-03-14-at-10-53-42-AM.png" alt="Binance" width="90" /> | binance | [Binance](https://www.binance.com/) | 3 | [API](https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md) | [![Build Status](https://jenkins-02.coinalpha.com/buildStatus/icon?job=hb_test-exchange_binance&subject=test)](https://jenkins-02.coinalpha.com/job/hb_test-exchange_binance/) |
| <img src="https://i.ibb.co/h9JdGDW/cbp.jpg" alt="Coinbase Pro" width="90" /> | coinbase_pro | [Coinbase Pro](https://pro.coinbase.com/) | * | [API](https://docs.pro.coinbase.com/) | [![Build Status](https://jenkins-02.coinalpha.com/buildStatus/icon?job=hb_test-exchange_coinbase&subject=test)](https://jenkins-02.coinalpha.com/job/hb_test-exchange_coinbase/) |
|<img src="documentation/docs/assets/img/huobi_logo.png" alt="Huobi Global" width="90" />| huobi | [Huobi Global](https://www.hbg.com) | 1 | [API](https://huobiapi.github.io/docs/spot/v1/en/) | [![Build Status](https://jenkins-02.coinalpha.com/buildStatus/icon?job=hb_test-exchange_huobi&subject=test)](https://jenkins-02.coinalpha.com/job/hb_test-exchange_huobi/) |
|<img src="documentation/docs/assets/img/bittrex_logo.png" alt="Bittrex Global" width="90" height="30" />| bittrex | [Bittrex Global](https://global.bittrex.com/) | 1 | [API](https://bittrex.github.io/api/v1-1) |
| <img src="documentation/docs/assets/img/liquid_logo.png" alt="Liquid" width="90" /> | liquid | [Liquid](https://www.liquid.com/) | 2 | [API](https://developers.liquid.com/) |
|<img src="documentation/docs/assets/img/oceanex.png" alt="OceanEx Global" width="90" height="30" />| oceanex | [OceanEx Global](https://oceanex.pro/en) | * | [API](https://api.oceanex.pro/doc/v1/#introduction) |

## Supported decentralized exchanges

| logo | id | name | ver | doc|
|:---:|:---:|:---:|:---:|:---:|
| <img src="documentation/docs/assets/img/radar_logo.png" alt="Radar Relay" width="90" height="30" /> | radar_relay | [Radar Relay](https://radarrelay.com/) | 2 | [API](https://developers.radarrelay.com/api/trade-api) | [![Build Status](https://jenkins-02.coinalpha.com/buildStatus/icon?job=hb_test-exchange_radar_relay&subject=test)](https://jenkins-02.coinalpha.com/job/hb_test-exchange_radar_relay/) |
| <img src="https://i.ibb.co/Lrpps2G/Screen-Shot-2019-03-14-at-10-39-23-AM.png" alt="DDEX" width="90" /> | ddex | [DDEX](https://ddex.io/) | 3 | [API](https://docs.ddex.io/) | [![Build Status](https://jenkins-02.coinalpha.com/buildStatus/icon?job=hb_test-exchange_ddex&subject=test)](https://jenkins-02.coinalpha.com/job/hb_test-exchange_ddex/) |
| <img src="documentation/docs/assets/img/idex_logo.png" alt="IDEX" width="90" /> | idex | [IDEX](https://idex.market/) | * | [API](https://docs.idex.market/) | |

## Community contributed exchange connectors

| logo | id | name | ver | doc| maintainer |
|:---:|:---:|:---:|:---:|:---:|:---:|
| <img src="https://i.ibb.co/1sPt940/Screen-Shot-2019-06-06-at-17-50-04.png" alt="Bamboo Relay" width="90" /> | bamboo_relay | [Bamboo Relay](https://bamboorelay.com/) | 3 | [API](https://sra.bamboorelay.com/) | [dex@bamboorelay.com](mailto:dex@bamboorelay.com)
|<img src="documentation/docs/assets/img/dolomite_logo.png" alt="Dolomite" width="90" />| dolomite | [Dolomite](https://dolomite.io/) | 1 | [API](https://docs.dolomite.io/) | [corey@dolomite.io](mailto:corey@dolomite.io)

## Currently available strategies

| Strategy | Test |
|--|--|
| [Pure market making](https://docs.hummingbot.io/strategies/pure-market-making/) | [![Build Status](https://jenkins-02.coinalpha.com/buildStatus/icon?job=hb_test-strategy_pure_mm&subject=test)](https://jenkins-02.coinalpha.com/job/hb_test-strategy_pure_mm/) |
| [Cross exchange market making](https://docs.hummingbot.io/strategies/cross-exchange-market-making/) | [![Build Status](https://jenkins-02.coinalpha.com/buildStatus/icon?job=hb_test-strategy_xemm&subject=test)](https://jenkins-02.coinalpha.com/job/hb_test-strategy_xemm/) |
| [Arbitrage](https://docs.hummingbot.io/strategies/arbitrage/) | [![Build Status](https://jenkins-02.coinalpha.com/buildStatus/icon?job=hb_test-strategy_arbitrage&subject=test)](https://jenkins-02.coinalpha.com/job/hb_test-strategy_arbitrage/) |
| [Discovery](https://docs.hummingbot.io/strategies/discovery/) | [![Build Status](https://jenkins-02.coinalpha.com/buildStatus/icon?job=hb_test-strategy_discovery&subject=test)](https://jenkins-02.coinalpha.com/job/hb_test-strategy_discovery/) |

## Getting Started

### Learn more about Hummingbot

- [Hummingbot website](https://hummingbot.io)
- [Documentation](https://docs.hummingbot.io)
- [Read our blog](https://www.hummingbot.io/blog)
- [Whitepaper](https://hummingbot.io/whitepaper.pdf)
- [FAQs](https://docs.hummingbot.io/faq/)
- [Roadmap](https://docs.hummingbot.io/roadmap/): including planned features

### Install Hummingbot

- [Installation guide](https://docs.hummingbot.io/installation/)
- [Installation scripts](./installation/)

### Using Hmmingbot OceanEx connector  

## Legal

- **License**: Hummingbot is licensed under [Apache 2.0](./LICENSE).
- **Data collection**: read important information regarding [Hummingbot Data Collection](DATA_COLLECTION.md).

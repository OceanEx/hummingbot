# Hummingbot OceanEx Fork Version User Guide
 <!--ts-->
 * [Introduction](#Introduction)
     * [Overview](#Overview)
     * [OceanEx Fork Version](#OceanEx-Fork-Version)
     * [Change Log](#Change-Log)
 * [API Documentation](doc/api.md)
 * [Work Flow](#Work-Flow)
     * [Create New Order](#Create-New-Order)
     * [Scan Transaction](#Deposit-Transaction)
     * [Notify Status](#Notify-Status)
     * [Collection](#Collection)
 * [Pyament Order States](#Payment-Order-States)
 * [Database Design](doc/database.md)
<!--te-->


## Introduction

### Overview

Hummingbot is an open-source project aimed to help users, traders and exchanges to build different trading strategies and run those strategies on the top of cryptocurrency exchange platforms.

The Hummingbot source code can be downloaded through Hummingbot official github project. The full details of documentation is available from Hummingbot official website.

### OceanEx Fork Version

Hummingbot supports a few number of exchanges. OceanEx was not a part of them. To enable trading through Hummingbot, OceanEx decided to fork from 0.29.0 version of Hummingbot and implemented the OceanEx connector. OceanEx published their own fork Hummingbot version at github, see the link .

### Change Log

| Version              | date       |   Author   | Description     | 
| ------------------   | ---------  | ---------- | ------------    |
| 0.1                  | 2021-03-02 | Technology | Initial version |

## Collection

When payment order is not longer active. The post deposit daemon start to collect the coins from order payment address and move them to target dest address. The dest address is definied at system_wallets.

## Payment Order States 

**active**

A order is waiting for one or mulitple transasctions to fill requested amount before it is expired. 

**expired** 

A order closed when running out of given period.

# Hummingbot OceanEx Fork Version User Guide
 <!--ts-->
 * [Introduction](#Introduction)
     * [Overview](#Overview)
     * [OceanEx Fork Version](#OceanEx-Fork-Version)
     * [Documentation History](#Documentation-History)
 * [Installation](Installation)
     * [Overview](#Overview)
     * [Docker](#Docker)
       * [Linux Installation Using Docker](#Linux-Installation-Using-Docker) 
         * [Ubuntu](#Ubuntu)
         * [Debian](#Debian)
         * [CentOS](#CentOS)
       * [MacOS Installation Using Docker](#MacOS-Installation-Using-Docker) 
       * [Windows Installation Using Docker](#Windows-Installation-Using-Docker) 
     * [Source](#Source) 
       * [Linux Source Installation](#Linux-Source-Installation) 
         * [Ubuntu](#Ubuntu)
         * [Debian](#Debian)
         * [CentOS](#CentOS)
       * [MacOS Source Installation](#MacOS-Source-Installation)
 * [Config](#Config)
     * [Create a new password](#Create-a-new-password)
 * [Run](#Run)
 * [Support](Support)
<!--te-->

## Introduction

### Overview

Hummingbot is an open-source project aimed to help users, traders and exchanges to build different trading strategies and run those strategies on the top of cryptocurrency exchange platforms.

The Hummingbot source code can be downloaded through Hummingbot official github project. The full details of documentation is available from Hummingbot official website.

### OceanEx Fork Version

Hummingbot supports a few number of exchanges. OceanEx was not a part of them. To enable trading through Hummingbot, OceanEx decided to fork from 0.29.0 version of Hummingbot and implemented the OceanEx connector. OceanEx published their own fork Hummingbot version at github, see the link .

### Documentation History

| Version              | date       |   Author   | Description     | 
| ------------------   | ---------  | ---------- | ------------    |
| 0.1                  | 2021-03-02 | Technology | Initial version |


## Installation

### Overview

Installing Hummingbot is simple. The original version of Hummingbot supports installation with executable files in .exe format for Windows and .dmg format for MacOS. Refer to the Hummingbot installation link . However, the OceanEx fork version of Hummingbot DOES NOT have Windows and MacOS installation executable files. It only supports installation via Docker and Source build.

### Docker

#### Linux Installation Using Docker

##### Ubuntu

* Step 1: Install Docker

Skip those Linux steps if you already have docker installed. Run the following commands:

```
# 1) Download Docker install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-ubuntu.sh

# 2) Enable script permissions
chmod a+x install-docker-ubuntu.sh

# 3) Run installation
./install-docker-ubuntu.sh

```
* Step 2: Install Hummingbot

Run the following commands:

```
# 1) Download Hummingbot install, start, and update script
wget https://raw.githubusercontent.com/OceanEx/hummingbot/master/installation/docker-commands/create.sh

wget https://raw.githubusercontent.com/OceanEx/hummingbot/master/installation/docker-commands/start.sh

# 2) Enable script permissions
chmod a+x *.sh

# 3) Create a hummingbot instance
./create.sh
```

##### Debian

* Step 1: Install Docker

Skip those steps if you already have docker installed. Run the following commands:

```
# 1) Download Docker install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-debian.sh

# 2) Enable script permissions
chmod a+x install-docker-debian.sh

# 3) Run installation
./install-docker-debian.sh

```
* Step 2: Install Hummingbot

Run the following commands:
```
# 1) Download Hummingbot install, start, and update script
wget https://raw.githubusercontent.com/OceanEx/hummingbot/master/installation/docker-commands/create.sh

wget https://raw.githubusercontent.com/OceanEx/hummingbot/master/installation/docker-commands/start.sh

# 2) Enable script permissions
chmod a+x *.sh

# 3) Create a hummingbot instance
./create.sh
```

##### CentOS


* Step 1: Install Docker

Skip those steps if you already have docker installed. Run the following commands:

```
# 1) Download Docker install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-centos.sh

# 2) Enable script permissions
chmod a+x install-docker-centos.sh

# 3) Run installation
./install-docker-centos.sh
```

* Step 2: Install Hummingbot

Run the following commands:
```
# 1) Download Hummingbot install, start, and update script
wget https://raw.githubusercontent.com/OceanEx/hummingbot/master/installation/docker-commands/create.sh

wget https://raw.githubusercontent.com/OceanEx/hummingbot/master/installation/docker-commands/start.sh

# 2) Enable script permissions
chmod a+x *.sh

# 3) Create a hummingbot instance
./create.sh
```

#### MacOS Installation Using Docker

* Step 1: Install Docker

Install docker from the official page.

* Step 2: Install Hummingbot

```
# 1) Download Hummingbot install script
curl https://raw.githubusercontent.com/OceanEx/hummingbot/master/installation/docker-commands/create.sh -o create.sh

# 2) Enable script permissions
chmod a+x create.sh

# 3) Run installation
./create.sh
```


#### Windows Installation Using Docker 

* Step 1: Install Docker

Install Docker Toolbox from this guide . And please only follow the guide for Step 1. Install
Docker Toolbox . Stop at Step 2 and use the guide as below.

* Step 2: Install Hummingbot

Open Docker Quickstart Terminal. Enter following commands in the terminal

```
# 1) Navigate to root folder
cd ~

# 2) Download Hummingbot install script
curl https://raw.githubusercontent.com/OceanEx/hummingbot/master/installation/docker-commands/create.sh -o create.sh

curl https://raw.githubusercontent.com/OceanEx/hummingbot/master/installation/docker-commands/start.sh -o start.sh

# 3) Enable script permissions
chmod a+x create.sh
chmod a+x start.sh

# 4) Run installation
./create.sh
```

### Source

#### Linux Source Installation

##### Ubuntu

```
# 1) Download install script
wget https://raw.githubusercontent.com/OceanEx/hummingbot/master/installation/install-from-source/install-source-ubuntu.sh

# 2) Enable script permissions
chmod a+x install-source-ubuntu.sh

# 3) Run installation
./install-source-ubuntu.sh
```

##### Debian

```
# 1) Download install script
wget https://raw.githubusercontent.com/OceanEx/hummingbot/master/installation/install-from-source/install-source-debian.sh

# 2) Enable script permissions
chmod a+x install-source-debian.sh

# 3) Run installation
./install-source-debian.sh
```

##### CentOS

```
# 1) Download install script
wget https://raw.githubusercontent.com/OceanEx/hummingbot/master/installation/install-from-source/install-source-centos.sh

# 2) Enable script permissions
chmod a+x install-source-centos.sh

# 3) Run installation
./install-source-centos.sh
```

#### MacOS Source Installation

Refer to Humingbot origin link to install env in Part 1 section.
When installing Part 2, please replaced with following scripts.

```
# 1) Download Hummingbot install script
curl https://raw.githubusercontent.com/OceanEx/hummingbot/master/installation/install-from-source/install-source-macOS.sh -o install-source-macOS.sh

# 2) Enable script permissions
chmod a+x install-source-macOS.sh

# 3) Run installation
./install-source-macOS.sh
```


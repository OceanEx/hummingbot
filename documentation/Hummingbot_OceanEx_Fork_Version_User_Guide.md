![image](https://user-images.githubusercontent.com/8203219/109872974-20321580-7c3b-11eb-8f60-4c3c042a1ee2.png)
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
         * [Ubuntu](#Ubuntu-Source)
         * [Debian](#Debian-Source)
         * [CentOS](#CentOS-Source)
       * [MacOS Source Installation](#MacOS-Source-Installation)
 * [Run Hummingbot with OceanEx Connector](#Run-Hummingbot-with-OceanEx-Connector)
    * [Create a new password](#Create-a-new-password)
    * [Menu](#Menu)
    * [Config](#Config)
    * [Connect to OceanEx](#Connect-to-OceanEx)
    * [Start](#Start)
 * [Performance and Statics](Performance-and-Statics)
 * [Support](Support)
<!--te-->

## Introduction

### Overview

Hummingbot is an open-source project aimed to help users, traders and exchanges to build different trading strategies and run those strategies on the top of cryptocurrency exchange platforms.

The Hummingbot source code can be downloaded through Hummingbot official github project. The full details of documentation is available from [Hummingbot official website](https://github.com/CoinAlpha/hummingbot).

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

##### Ubuntu Source

```
# 1) Download install script
wget https://raw.githubusercontent.com/OceanEx/hummingbot/master/installation/install-from-source/install-source-ubuntu.sh

# 2) Enable script permissions
chmod a+x install-source-ubuntu.sh

# 3) Run installation
./install-source-ubuntu.sh
```

##### Debian Source

```
# 1) Download install script
wget https://raw.githubusercontent.com/OceanEx/hummingbot/master/installation/install-from-source/install-source-debian.sh

# 2) Enable script permissions
chmod a+x install-source-debian.sh

# 3) Run installation
./install-source-debian.sh
```

##### CentOS Source

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
## Run Hummingbot with OceanEx Connector

once trigger ```create.sh``` or ```start.sh```, you will see the hummingbot panel as below.  
![image](https://user-images.githubusercontent.com/8203219/109872866-fe389300-7c3a-11eb-8492-3c7606c12fcf.png)


### Create a new password

create a new password for secruity concerns. 

![image](https://user-images.githubusercontent.com/8203219/109876147-68ebcd80-7c3f-11eb-8748-f090fbb67861.png)


### Menu 

hit 'Tab' key to see all the config options. 

![image](https://user-images.githubusercontent.com/8203219/109878124-d8fb5300-7c41-11eb-9d3a-b32b9a38b0ec.png)


### Config

chose 'create' from menu to set up a OceanEx connector. 

* Chose strategy

for more details about different kinds of strategies. please check hummingbot offical website section. 

![image](https://user-images.githubusercontent.com/8203219/109878766-b289e780-7c42-11eb-9136-3dab726c85d1.png)

let's use *pure_market_making* strategy as example, chose 'ocean' as OceanEx connector. chose markets pair.

![image](https://user-images.githubusercontent.com/8203219/109903289-9f3e4280-7c69-11eb-89e6-144e283f8a6a.png)

The Hummingbot will ask you some questions to complete configuration set up. The configuration item could be explained here. https://docs.hummingbot.io/strategies/pure-market-making/ 


### Connect to OceanEx

once you have completed the *pure_market_making* setup, you need to set up your api key infomation. You will be back to the main menu. chose 'connect'. 
![image](https://user-images.githubusercontent.com/8203219/109903912-736f8c80-7c6a-11eb-8421-bf3ef4a495fd.png)
 

type 'connect' and give 'space'. you will see exchange list comming out.

![image](https://user-images.githubusercontent.com/8203219/109904098-b893be80-7c6a-11eb-9432-e72025385b62.png)


enter your uuid and api_key path 


![image](https://user-images.githubusercontent.com/8203219/109904167-d2350600-7c6a-11eb-92af-b4e4e416c831.png)

![image](https://user-images.githubusercontent.com/8203219/109904284-fe508700-7c6a-11eb-8c9f-db0b919d28bf.png)

Where is my uid at OceanEx ?

![image](https://user-images.githubusercontent.com/8203219/109904815-d281d100-7c6b-11eb-9424-760fc9dcac8e.png)

![image](https://user-images.githubusercontent.com/8203219/109904835-d9a8df00-7c6b-11eb-8d30-ba55737eb91e.png)



Make sure copy your private api key (let’s say file name is key.pem) to
```
<path of where you run script>/hummingbot_files/hummingbot_conf directory
```
Note: hummingbot maps <path of where you run script>/hummingbot_files/hummingbot_conf to docker container /conf. The input for the
command line must be /conf .

```
Enter your Ocean Private key file >>> /conf/key.pem
```

### start 


If you pass all the configuration set up, you should see the prompt below. And simply type 'start' to turn on the trading bot.

![image](https://user-images.githubusercontent.com/8203219/109904742-ad8d5e00-7c6b-11eb-92a0-eea8a2a5e121.png)

Once started successful, you should see the logs on the right side. If it failed with errors, the error reason will both be shown at logs at right and command prompts at left.



![image](https://user-images.githubusercontent.com/8203219/109904853-e299b080-7c6b-11eb-9cec-fd0abf0984a5.png)


You could review your order at OceanEx .


![image](https://user-images.githubusercontent.com/8203219/109904904-f0e7cc80-7c6b-11eb-9012-157630688173.png)



## Performance and Statics

Please type status to check your current orders and account balance.

```
>>> status
```

![image](https://user-images.githubusercontent.com/8203219/109905267-897e4c80-7c6c-11eb-8d4c-f27aebff473e.png)


Please type history to check your performance.

```
>>> history
```
![image](https://user-images.githubusercontent.com/8203219/109905351-a31f9400-7c6c-11eb-983f-7f85b6fc0e7b.png)


## Support 

OceanEx HummingBot is a fork version of HummingBot . For more information about how to use HummingBot, please refer to HummingBot official user doc website . Please email questions or comments regarding this specification to OceanEx Support.






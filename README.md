# Project Obsidian

A fully featured & modular Minecraft Classic / Classicube Server fully reimplemented in Python!

![Minecraft Version 0.30_01c](https://img.shields.io/badge/Minecraft%20Version-0.30__01c-green)
![Protocol Version 7](https://img.shields.io/badge/Protocol%20Version-7-blue)
![Classic Server Version](https://img.shields.io/badge/Classic%20Server%20Version-1.10.1-purple)

# Features
- Full Implementation of the Minecraft Classic Protocol
- Asynchronous & Multithreaded
- Supports [CPE (Classic Protocol Extension)](https://wiki.vg/Classic_Protocol_Extension)
- Highly Customizable and Modular
- Multi-World Support
- Supports Multiple World Formats
- Fully featured plugin support

# Instructions
> Obsidian Server requires **no 3rd party libraries**, meaning that you can run this server with a stock python installation!

On linux, install `python3.10` and clone the repository.
```
sudo apt update && sudo apt upgrade -y
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa
apt-get install python3.10
git clone https://github.com/RadioactiveHydra/ProjectObsidian.git
```

> (!) Minimum of **python 3.10** is required! (!)

Then, just navigate into the directory and run `main.py`!
```
cd ProjectObsidian
python3.10 main.py
```

Once you have the server up, you can run `main.py -h` to see the available flags you can set

# Plugins
Project Obsidian comes with numerous plugins to get you started. Check them out here: [Plugins](obsidian/modules/PLUGIN.md)

# Plugin Development
For information regarding plugin development, refer to the [Plugin Development Guide](obsidian/modules/DEVELOPMENT.md) (Coming Soon).

# Getting Help
If you have any issues, feel free to join our discord server!
[https://discord.hydranet.dev/](https://discord.hydranet.dev/)

# Disclaimers
**Project Obsidian is not affiliated with (or supported by) Mojang AB, Minecraft, or Microsoft in any way.**

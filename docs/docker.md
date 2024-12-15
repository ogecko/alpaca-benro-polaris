[Home](../README.md) | [Hardware Guide](./hardware.md) | [Installation Guide](./installation.md) | [Using Stellarium](./stellarium.md) | [Using Nina](./nina.md) | [Troubleshooting](./troubleshooting.md) | [FAQ](./faq.md)

# Docker Installation Guide
Docker provides a portable way to run the application on any OS and architecture.  It's been tested on various Linux distributions and architectures, Mac OS (Apple Silicon, but should also work on Intel), and Windows 11 with WSL 2.

# Install docker
This should work with any version of docker (e.g. Docker Desktop, docker.io, docker-ce, etc.).

If you don't have docker installed and don't have a preference, then [follow the official instructions](https://docs.docker.com/get-docker/).

# Configuration
Copy `platforms/docker/config.toml.example` to `platforms/docker/config.toml` and edit it for your Benro Polaris.  

If you are running docker under WSL you may need to convert shell scripts to Linux format using these commands.
```
$ sudo apt-get update
$ sudo apt-get install dos2unix
$ find . -type f -name "*.sh" -exec dos2unix {} \;
```

# Run
To run on Windows with Alpaca, simply run the following command from a terminal, setting your local time zone using one of the `TZ identifier` options listed [here](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones). For example:  
`TIME_ZONE="America/Vancouver"`
```
./platforms/docker/run.sh -t "America/Vancouver"
```

# Build
If the image doesn't exist, then it will be built automatically.  Otherwise, if you want to rebuild it, then run the following:
```
./platforms/docker/run.sh -b -t "America/Vancouver"
```


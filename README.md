# GNS3 Automation

## What it is
This script reads a YAML configuration file and, based on that, sets up a topology in GNS3, boots the nodes, and finally applies some Day-0 configuration. It is usable in environments where the same topology has be set up numerous times; e.g. in education or for CI/CD pipelines.

## How it is working
Based on the configuration file (topology_config.yml) the deploy_topology.py Python script makes REST API calls to a GNS3 server to do the following:
1. Creates a project
2. Adds the nodes listed in the config file.
3. Connects them as described in the links section of the config file.
4. Creates an Ansible inventory file for further use, as well as saves the config file with added information.
5. Boots the nodes.

Then it launches Expect scripts to apply a simple Day-0 configuration (hostname, management IP address, default gateway for management). The reason Expect is used is because there is no other way to create a multi-vendor/multi-device solution.

Example: NX-OS supports POAP but in order to create its configuration file, we need to know its serial number. But how do we get this information for a newly created VM? We boot it, go into the console, and look up the information. But then why not configure it in that first step instead of making things complicated?

This video shows the script in action: [https://www.youtube.com/watch?v=6UnkgeiMaUs](https://www.youtube.com/watch?v=6UnkgeiMaUs)

## Requirements
- The appliances must be already imported on the GNS3 server.
- All nodes must have a serial (telnet) console.
- Have the following Python modules on your system:
  - json
  - subprocess
  - time
  - re
  - requests
  - yaml
- Make sure the device names in the links section of the config file matches your configured settings. By default GNS3 uses {name}-{0}, which is translated to the appliances' name without spaces, followed by a dash and a sequence number.

## A final note
You have to check your configuration file thoroughly, make sure there are no typos and other errors, otherwise the script will fail. Hence this tool is not for beginners. If something is not working, check the outputs, try to make similar calls with Postman; eventually you'll find the issue.
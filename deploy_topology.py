"""
This script creates a GNS3 project, adds nodes, interconnect and boots all of them, then
applies Day-0 configuration to them. It also creates an Ansible inventory that can be
used for further configuration.
"""

from __future__ import print_function
from json import dumps
from subprocess import call
from time import sleep
from re import sub
from requests import get, post, delete
from yaml import safe_dump, load

def create_project(name):
    """
    Checking if a project with a given name already exists; if yes, deleting it.
    Then the function (re)creates the project and returns the project ID.
    """

    ### Finding the project ID if a project with the given name exists.
    url = "http://%s:%s/v2/projects" % (CONFIG["gns3_server"], CONFIG["gns3_port"])
    response = get(url)
    if response.status_code == 200:
        body = response.json()
        project = next((item for item in body if item["name"] == CONFIG["project_name"]), None)
    else:
        print("Received HTTP error %d when checking if the project already exists! Exiting." % \
               response.status_code)
        exit(1)

    ### Deleting the project if it already exists.
    if project != None:
        delete_project_id = project["project_id"]
        url = "http://%s:%s/v2/projects/%s" % \
              (CONFIG["gns3_server"], CONFIG["gns3_port"], delete_project_id)
        response = delete(url)
        if response.status_code != 204:
            print("Received HTTP error %d when deleting the existing project! Exiting." \
                  % response.status_code)
            exit(1)

    ### (Re)creating the project
    url = "http://%s:%s/v2/projects" % (CONFIG["gns3_server"], CONFIG["gns3_port"])
    data = {"name": name}
    data_json = dumps(data)
    response = post(url, data=data_json)
    if response.status_code == 201:
        body = response.json()
        # Adding the project ID to the config
        CONFIG["project_id"] = body["project_id"]
    else:
        print("Received HTTP error %d when creating the project! Exiting." % response.status_code)
        exit(1)



def assign_appliance_id():
    """
    Assigning appliance IDs to the appliance names defined in the config file.
    """

    node_seq = 0
    url = "http://%s:%s/v2/appliances" % (CONFIG["gns3_server"], CONFIG["gns3_port"])
    response = get(url)

    if response.status_code == 200:
        body = response.json()
        for node in CONFIG["nodes"]:
            node_dict = next((item for item in body if item["name"] == node["appliance_name"]), None)
            node_appliance_id = node_dict["appliance_id"]
            CONFIG["nodes"][node_seq]["appliance_id"] = node_appliance_id
            node_seq += 1
    else:
        print("Received HTTP error %d when retrieving appliances! Exiting." % response.status_code)
        exit(1)



def add_nodes():
    """
    This function adds a node to the project already created.
    """

    ### Adding nodes
    for appliance in CONFIG["nodes"]:
        instance_seq = 1
        for instance in appliance["instances"]:
            ### Adding node name to the config
            instance["name"] = appliance["appliance_name"].replace(" ", "") + \
                               "-"  + str(instance_seq)

            ### Creating the node
            url = "http://%s:%s/v2/projects/%s/appliances/%s" % \
                   (CONFIG["gns3_server"], CONFIG["gns3_port"], \
                   CONFIG["project_id"], appliance["appliance_id"])
            data = {"compute_id": "local", "x": instance["x"], "y": instance["y"]}
            data_json = dumps(data)
            response = post(url, data=data_json)
            if response.status_code == 201:
                instance_seq += 1
            else:
                print("Received HTTP error %d when adding node %s! Exiting." % \
                     (response.status_code, instance["name"]))
                exit(1)

    ### Retrieving all nodes in the project, the assigning node IDs and console port numbers
    ### by searching the node's name, then appending the config with them.
    url = "http://%s:%s/v2/projects/%s/nodes" % \
           (CONFIG["gns3_server"], CONFIG["gns3_port"], CONFIG["project_id"])
    response = get(url)

    if response.status_code == 200:
        body = response.json()
        for appliance in CONFIG["nodes"]:
            for instance in appliance["instances"]:
                instance["node_id"] = next((item["node_id"] \
                                    for item in body if item["name"] == instance["name"]), None)
                instance["console"] = next((item["console"] \
                                    for item in body if item["name"] == instance["name"]), None)
    else:
        print("Received HTTP error %d when retrieving nodes! Exiting." % response.status_code)
        exit(1)



def add_links():
    """
    Creating links between the nodes and their interfaces defined in the config
    """

    for link in CONFIG["links"]:
        for member in link:
            for appliance in CONFIG["nodes"]:
                for instance in appliance["instances"]:
                    if member["name"] == instance["name"]:
                        member["node_id"] = instance["node_id"]

                        url = "http://%s:%s/v2/projects/%s/nodes/%s" % \
                            (CONFIG["gns3_server"], CONFIG["gns3_port"], \
                             CONFIG["project_id"], member["node_id"])
                        response = get(url)
                        body = response.json()

                        member["adapter_number"] = body["ports"][member["interface"]]["adapter_number"]
                        member["port_number"] = body["ports"][member["interface"]]["port_number"]

        url = "http://%s:%s/v2/projects/%s/links" % \
               (CONFIG["gns3_server"], CONFIG["gns3_port"], CONFIG["project_id"])
        data = {"nodes": [ \
               {"node_id": link[0]["node_id"], \
               "adapter_number": link[0]["adapter_number"], \
               "port_number": link[0]["port_number"]}, \
               {"node_id": link[1]["node_id"], \
               "adapter_number": link[1]["adapter_number"], \
               "port_number": link[1]["port_number"]}]}

        data_json = dumps(data)
        response = post(url, data=data_json)
        if response.status_code != 201:
            print("Error %d when creating link %s adapter %s port %s -- %s adapter %s port %s" % \
                 (response.status_code, \
                  link[0]["node_id"], link[0]["adapter_number"], link[0]["port_number"], \
                  link[1]["node_id"], link[1]["adapter_number"], link[1]["port_number"]))
            exit(1)



def start_nodes():
    """
    Booting all nodes in the topology.
    """
    url = "http://%s:%s/v2/projects/%s/nodes/start" % \
            (CONFIG["gns3_server"], CONFIG["gns3_port"], CONFIG["project_id"])
    response = post(url)
    if response.status_code == 204:
        # Wait 10s for nodes to start booting
        sleep(10)
    else:
        print("Received HTTP error %d when starting nodes! Exiting." % response.status_code)
        exit(1)



def day0_config():
    """
    Deploying Day-0 configuration
    """
    for appliance in CONFIG["nodes"]:
        if appliance["os"] != "none":
            for instance in appliance["instances"]:
                expect_cmd = ["expect", "day0-%s.exp" % appliance["os"], CONFIG["gns3_server"], \
                              str(instance["console"]), appliance["os"] + \
                              str(appliance["instances"].index(instance) + 1), \
                              instance["ip"], instance["gw"], ">/dev/null"]
                call(expect_cmd)



def build_ansible_hosts():
    """
    Creating an Ansible hosts file from the nodes
    """

    with open("hosts-%s" % CONFIG["project_name"], "w") as hosts_file:
        for appliance in CONFIG["nodes"]:
            if appliance["os"] != "none":
                # Creating inventory groups based on OS
                hosts_file.write("[%s]\n" % appliance["os"])
                for instance in appliance["instances"]:
                    # Writing the hostname and its IP address to the inventory file. The sub
                    # function reremoves the /xx or " xxx.xxx.xxx.xxx" portion of the address.
                    hosts_file.write("%s ansible_host=%s\n" % \
                                    (instance["name"], sub("/.*$| .*$", "", instance["ip"])))
                hosts_file.write("\n")





if __name__ == "__main__":

    ### Loading config file
    with open("topology_config.yml") as config_file:
        CONFIG = load(config_file)

    ### Create project and add its ID to the config
    print("Creating GNS3 project")
    create_project(CONFIG["project_name"])

    ### Add appliance IDs to the config
    print("Retrieving appliance IDs")
    assign_appliance_id()

    ### Add nodes to the topology
    print("Adding nodes")
    add_nodes()

    ### Create links between the nodes
    print("Adding links")
    add_links()

    ### Creating inventory file for Ansible
    print("Generating Ansible inventory file")
    build_ansible_hosts()

    ### Dump final config into "topology_full.yml"
    print("Saving final topology config.")
    with open("topology_full.yml", 'w+') as topology_file:
        safe_dump(CONFIG, topology_file, default_flow_style=False)

    ### Start nodes
    print("Starting nodes")
    start_nodes()

    ### Day-0 configuration
    print("Applying Day-0 configuration")
    day0_config()

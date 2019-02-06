"""
This script creates a GNS3 project, adds nodes, interconnect them, and finally boots all of them.
"""

from __future__ import print_function
import argparse
from json import dumps
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
    body = response.json()
    project = next((item for item in body if item["name"] == "test"), None)

    ### Deleting the project if it already exists.
    if project != None:
        delete_project_id = project["project_id"]
        url = "http://%s:%s/v2/projects/%s" % \
              (CONFIG["gns3_server"], CONFIG["gns3_port"], delete_project_id)
        response = delete(url)

    ### (Re)creating the project
    url = "http://%s:%s/v2/projects" % (CONFIG["gns3_server"], CONFIG["gns3_port"])
    data = {"name": name}
    data_json = dumps(data)
    response = post(url, data=data_json)
    body = response.json()

    ### Adding the project ID to the config
    CONFIG["project_id"] = body["project_id"]



def assign_appliance_id():
    """
    Assigning appliance IDs to the appliance names defined in the config file.
    """

    node_seq = 0
    url = "http://%s:%s/v2/appliances" % (CONFIG["gns3_server"], CONFIG["gns3_port"])
    response = get(url)
    body = response.json()

    for node in CONFIG["nodes"]:
        node_dict = next((item for item in body if item["name"] == node["appliance_name"]), None)
        node_appliance_id = node_dict["appliance_id"]
        CONFIG["nodes"][node_seq]["appliance_id"] = node_appliance_id
        node_seq += 1



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
            instance_seq += 1


    ### Retrieving all nodes in the project, the assigning node IDs by searching the node's name,
    ### then appending the config with them.
    url = "http://%s:%s/v2/projects/%s/nodes" % \
           (CONFIG["gns3_server"], CONFIG["gns3_port"], CONFIG["project_id"])
    response = get(url)
    body = response.json()

    for appliance in CONFIG["nodes"]:
        for instance in appliance["instances"]:
            instance["node_id"] = next((item["node_id"] \
                                  for item in body if item["name"] == instance["name"]), None)



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
        body = response.json()



def start_nodes():
    """
    Booting all nodes in the topology.
    """
    url = "http://%s:%s/v2/projects/%s/nodes/start" % \
            (CONFIG["gns3_server"], CONFIG["gns3_port"], CONFIG["project_id"])
    response = post(url)

    
if __name__ == "__main__":

    ### Checking for debug mode
    PARSER = argparse.ArgumentParser(description=\
             "Automated GNS3 topology deployment for CI/CD pipelines")
    PARSER.add_argument("--debug", action="store_true",
                        help="Debug mode that creates a YAML file with the parsed config.")
    ARGS = PARSER.parse_args()

    ### Loading config file
    with open("config.yml") as config_file:
        CONFIG = load(config_file)

    ### Create project and add its ID to the config
    create_project(CONFIG["project_name"])

    ### Add appliance IDs to the config
    assign_appliance_id()

    ### Add nodes to the topology
    add_nodes()

    ### Create links between the nodes
    add_links()

    ### Start nodes
    start_nodes()

    ### Dump final config into "topology.yml"
    if ARGS.debug is True:
        with open("topology.yml", 'w+') as topology_file:
            safe_dump(CONFIG, topology_file, default_flow_style=False)

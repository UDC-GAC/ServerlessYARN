import subprocess
import json

MAX_FOUND_TRIES = 3


class ApptainerHandler:

    def __init__(self, command="apptainer" ,privileged=False):
        self.command = command
        self.privileged = privileged

    def get_running_containers(self):
        if self.privileged:
            cmd_list = ["sudo", self.command, "instance", "list", "-j"]
        else:
            cmd_list = [self.command, "instance", "list", "-j"]
        process = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        return json.loads(stdout)

    ## CAUTION! Passwordless SSH is mandatory
    def get_remote_running_containers(self, nodes):
        containers = {}
        if self.privileged:
            cmd_list = ["ssh", "node", "sudo", self.command, "instance", "list", "-j"]
        else:
            cmd_list = ["ssh", "node", self.command, "instance", "list", "-j"]

        for node in nodes:
            cmd_list[1] = node
            process = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            containers[node] = json.loads(stdout)
        
        return containers

    def get_running_containers_list(self):
        running_containers = []
        container_info_json = self.get_running_containers()
        for instance in container_info_json['instances']:
            container = {"name": instance['instance'], "pid": instance['pid']}
            running_containers.append(container)
        return running_containers
    
    def get_remote_running_containers_list(self, nodes):
        running_containers = []
        containers = self.get_remote_running_containers(nodes)
        for node in containers:
            for instance in containers[node]['instances']:
                container = {"name": instance['instance'], "pid": instance['pid']}
                running_containers.append(container)
        
        return running_containers
    

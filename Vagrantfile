# -*- mode: ruby -*-
# vi: set ft=ruby :

## Load variables from config file
require 'yaml'
current_dir    = File.dirname(File.expand_path(__FILE__))
configs        = YAML.load_file("#{current_dir}/ansible/provisioning/config/config.yml")

## Server
SERVER_IP = configs['server_ip']
CPU_SERVER_NODE = configs['cpus_server_node']
MEMORY_SERVER_NODE = configs['memory_server_node']
WEB_INTERFACE_PORT = configs['web_interface_port']

## Client Nodes
N = configs['number_of_client_nodes']
CPUS_PER_NODE = configs['cpus_per_client_node']
MEMORY_PER_NODE = configs['memory_per_client_node']

Vagrant.configure("2") do |config|

  config.vm.box = "bento/ubuntu-20.04" 

  # hostmanager plugin
  config.hostmanager.enabled = true
  config.hostmanager.manage_host = true
  config.hostmanager.manage_guest = true
  config.hostmanager.ignore_private_ip = false

  # Server Node
  config.vm.define "server", primary: true do |server|
  	server.vm.host_name = "sc-server"
  	server.vm.provision "shell", path: "provision/server.sh"
  	server.vm.network "private_network", ip: SERVER_IP	
  	server.vm.network "forwarded_port", guest: WEB_INTERFACE_PORT, host: WEB_INTERFACE_PORT, host_ip: "127.0.0.1"
  	server.vm.provider "virtualbox" do |vb|
		vb.name = "Server - ServerlessContainers"
  		vb.cpus = CPU_SERVER_NODE
  		vb.memory = MEMORY_SERVER_NODE
  	end
  end	


  server_ip_to_number = SERVER_IP.split(".").map(&:to_i).pack('CCCC').unpack('N')[0]

  ## N Client Nodes
  (0..N-1).each do |i|
    config.vm.define "node#{i}" do |node|
	node.vm.hostname = "host#{i}"
	node.vm.provision "shell", path: "provision/nodes.sh"

	## Uncomment to provision nodes with cgroups v2 enabled
	#node.vm.provision "shell", path: "provision/cgroupsv2.sh"
	#node.vm.provision :reload

	number_to_ip = [server_ip_to_number + 1 + i].pack('N').unpack('CCCC').join('.')
	node.vm.network :private_network, ip: number_to_ip

	node.vm.provider "virtualbox" do |vb|
		vb.name = "Node#{i} - ServerlessContainers"
  		vb.cpus = CPUS_PER_NODE
  		vb.memory = MEMORY_PER_NODE
  	end
    end
  end

end

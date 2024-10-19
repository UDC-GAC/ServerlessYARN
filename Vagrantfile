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

## Hosts
N = configs['number_of_hosts']
CPUS_PER_NODE = configs['cpus_per_host']
MEMORY_PER_NODE = configs['memory_per_host']

CGROUPS_VERSION = configs['cgroups_version']

Vagrant.configure("2") do |config|

  config.vm.box = "bento/ubuntu-22.04" 
  config.vm.box_version = "202407.23.0"
  config.vm.box_check_update = false

  # hostmanager and vbguest plugins
  config.hostmanager.enabled = true
  config.hostmanager.manage_host = true
  config.hostmanager.manage_guest = true
  config.hostmanager.ignore_private_ip = false
  config.vbguest.auto_update = false

  # Master Node aka Server
  config.vm.define "server", primary: true do |server|
  	server.vm.hostname = "server"
  	server.vm.provision "shell", path: "provision/server.sh"
  	server.vm.network "private_network", ip: SERVER_IP	
  	server.vm.network "forwarded_port", guest: WEB_INTERFACE_PORT, host: WEB_INTERFACE_PORT, host_ip: "127.0.0.1"

  	server.vm.provider "virtualbox" do |vb|
		vb.name = "ServerlessYARN-Server"
		vb.customize ["modifyvm", :id, "--groups", "/ServerlessYARN"]
  		vb.cpus = CPU_SERVER_NODE
  		vb.memory = MEMORY_SERVER_NODE
		vb.gui = false
		vb.linked_clone = false
  	end
  end	


  server_ip_to_number = SERVER_IP.split(".").map(&:to_i).pack('CCCC').unpack('N')[0]

  ## N Worker Nodes aka Hosts
  (0..N-1).each do |i|
    config.vm.define "host#{i}" do |node|
		node.vm.hostname = "host#{i}"
		node.vm.provision "shell", path: "provision/nodes.sh"

		node.vm.provision "shell", path: "provision/cgroups_setup.sh", args: CGROUPS_VERSION
		node.vm.provision :reload

		number_to_ip = [server_ip_to_number + 1 + i].pack('N').unpack('CCCC').join('.')
		node.vm.network :private_network, ip: number_to_ip

		node.vm.provider "virtualbox" do |vb|
			vb.name = "ServerlessYARN-Host#{i}"
			vb.customize ["modifyvm", :id, "--groups", "/ServerlessYARN"]
			vb.cpus = CPUS_PER_NODE
			vb.memory = MEMORY_PER_NODE
			vb.gui = false
			vb.linked_clone = false
		end
    end
  end

end

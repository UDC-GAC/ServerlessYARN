# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|

  #config.vm.box = "hashicorp/bionic64"
  config.vm.box = "bento/ubuntu-20.04" 

  # hostmanager plugin
  config.hostmanager.enabled = true
  config.hostmanager.manage_host = true
  config.hostmanager.manage_quest = true
  config.hostmanager.ignore_private_ip = false

  # Server Node
  config.vm.define "server", primary: true do |server|
  	server.vm.host_name = "sc-server"
  	server.vm.provision "shell", path: "provision/server.sh"
  	server.vm.network "private_network", ip: "192.168.56.100"	
  	server.vm.network "forwarded_port", guest: 9000, host: 9000, host_ip: "127.0.0.1"
  	server.vm.provider "virtualbox" do |vb|
  	  	vb.name = "Server - ServerlessContainers"
  		vb.cpus = 2
  		vb.memory = "4096"
  	end
  end	


  ## N Client Nodes
  N = 1
  CPUS_PER_NODE = 4
  MEMORY_PER_NODE = 4096

  (0..N-1).each do |i|
    config.vm.define "node#{i}" do |node|
	node.vm.hostname = "host#{i}"
	node.vm.provision "shell", path: "provision/nodes.sh"
	node.vm.network :private_network, ip: "192.168.56.#{101+i}"
	node.vm.provider "virtualbox" do |vb|
  	  	vb.name = "Node#{i} - ServerlessContainers"
  		vb.cpus = CPUS_PER_NODE
  		vb.memory = MEMORY_PER_NODE
  	end
    end
  end

end

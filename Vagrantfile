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
  	server.vm.provider "virtualbox" do |vb|
  	  	vb.name = "Server - ServerlessContainers"
  		vb.cpus = 2
  		vb.memory = "4096"
  	end
  end	

  # Client Node
  config.vm.define "node1", primary: true do |node1|
  	node1.vm.host_name = "host0"
  	node1.vm.provision "shell", path: "provision/nodes.sh"
  	node1.vm.network "private_network", ip: "192.168.56.101"
    	node1.vm.provider "virtualbox" do |vb|
  	  	vb.name = "Node1 - ServerlessContainers"
  		vb.cpus = 4
  		vb.memory = "4096"
  	end		
  end	
  
end

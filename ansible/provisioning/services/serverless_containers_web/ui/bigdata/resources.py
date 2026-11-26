from django.conf import settings

from ui.domain.container_resources import get_app_cores

## Resources calculation for Hadoop clusters (HDFS + YARN)

def get_node_reserved_memory(node_memory):
    reserved_memory = 0

    # It will be probably interesting to lower the reserved_memory since the containers do not need that many extra resources

    # < 8 GB
    if node_memory < 8192:
        #reserved_memory = 1024
        reserved_memory = 512
    # 8 GB - 16 GB
    elif node_memory <= 16384:
        reserved_memory = 2048
    # 24 GB
    elif node_memory <= 24576:
        reserved_memory = 4096
    # 48 GB
    elif node_memory <= 49152:
        reserved_memory = 6144
    # 64 GB - 72 GB
    elif node_memory <= 73728:
        reserved_memory = 8192
    # 96 GB
    elif node_memory <= 98304:
        reserved_memory = 12288
    # 128 GB
    elif node_memory <= 131072:
        reserved_memory = 24576
    # > 128 GB
    else:
        reserved_memory = int(node_memory/8)

    return reserved_memory

def get_min_container_size(node_memory):
    min_container_size = 0

    # < 4 GB
    if node_memory < 4096:
        min_container_size = 256
    # 4 GB - 8 GB
    elif node_memory <= 8192:
        min_container_size = 512
    # 8 GB - 24 GB
    elif node_memory <= 24576:
        min_container_size = 1024
    # > 24 GB
    else:
        min_container_size = 2048

    return min_container_size

def set_hadoop_resources(container_resources, virtual_cluster, number_of_workers, replication_factor=settings.PLATFORM_CONFIG['default_hdfs_replication']):

    hadoop_resources = {}

    total_cores = max(int(container_resources["cpu_max"])//100,1)
    min_cores = max(int(container_resources["cpu_min"])//100,1)
    total_memory = int(container_resources["mem_max"])
    total_disks = 1
    heapsize_factor = 0.9

    ## 'Classic' way of calculating resources:
    #reserved_memory = get_node_reserved_memory(total_memory)
    #available_memory = total_memory - reserved_memory
    #min_container_size = get_min_container_size(total_memory)

    #number_of_hadoop_containers = int(min(2*total_cores, 1.8*total_disks, available_memory/min_container_size))
    # mem_per_container = max(min_container_size, available_memory/number_of_hadoop_containers)

    # scheduler_maximum_memory = int(number_of_hadoop_containers * mem_per_container)
    # scheduler_minimum_memory = int(mem_per_container)
    # nodemanager_memory = scheduler_maximum_memory
    # map_memory = scheduler_minimum_memory
    # reduce_memory = int(min(2*mem_per_container, available_memory))
    # mapreduce_am_memory = reduce_memory


    ## 'BDEv' way of calculating resources:
    #number_of_hadoop_containers = int(min(2*total_cores, available_memory/min_container_size))

    if virtual_cluster:
        ## Virtual cluster config (test environment with low resources)
        app_master_heapsize = 128
        datanode_heapsize = 128
        nodemanager_heapsize = 128
    else:
        ## Physical cluster config (real environment with (presumably) high resources)
        app_master_heapsize = 1024
        datanode_heapsize = 1024
        nodemanager_heapsize = 1024

    ## Adjust vcores to the SMT mode (in 'hybrid' mode, vcores are restricted to the physical cores)
    total_cores = get_app_cores(total_cores)
    min_cores = get_app_cores(min_cores)

    app_master_memory_overhead = int(app_master_heapsize * 0.1)
    if app_master_memory_overhead < 384:
        app_master_memory_overhead = 384
    mapreduce_am_memory = app_master_heapsize + app_master_memory_overhead

    memory_per_container_factor = 0.95
    available_memory = int(total_memory * memory_per_container_factor)
    nodemanager_memory = available_memory - nodemanager_heapsize - datanode_heapsize

    mem_per_container = int((nodemanager_memory - mapreduce_am_memory) / total_cores)

    map_memory_ratio = 1
    reduce_memory_ratio = 1
    map_memory = int(min(mem_per_container * map_memory_ratio, available_memory))
    reduce_memory = int(min(mem_per_container * reduce_memory_ratio, available_memory))

    scheduler_maximum_memory = nodemanager_memory
    #scheduler_minimum_memory = int(mem_per_container)
    scheduler_minimum_memory = 256

    # total_available_memory = 0
    # for host in new_containers:
    #     if container_type in new_containers[host]:
    #         total_available_memory += available_memory * new_containers[host][container_type]
    total_available_memory = available_memory * number_of_workers

    if total_available_memory < map_memory + reduce_memory + mapreduce_am_memory:
        memory_slice = nodemanager_memory/3.5
        scheduler_minimum_memory = int(memory_slice)
        map_memory = scheduler_minimum_memory
        reduce_memory = scheduler_minimum_memory
        mapreduce_am_memory = int(1.5 * memory_slice)

    map_memory_java_opts = int(heapsize_factor * map_memory)
    reduce_memory_java_opts = int(heapsize_factor * reduce_memory)
    #mapreduce_am_memory_java_opts = int(heapsize_factor * mapreduce_am_memory)
    mapreduce_am_memory_java_opts = app_master_heapsize

    hadoop_resources = {
        "vcores": str(total_cores),
        "min_vcores": str(min_cores), ## deprecated parameter that was used in older versions of the yarn-site.yml template
        "scheduler_maximum_memory": str(scheduler_maximum_memory),
        "scheduler_minimum_memory": str(scheduler_minimum_memory),
        "nodemanager_memory": str(nodemanager_memory),
        "map_memory": str(map_memory),
        "map_memory_java_opts": str(map_memory_java_opts),
        "reduce_memory": str(reduce_memory),
        "reduce_memory_java_opts": str(reduce_memory_java_opts),
        "mapreduce_am_memory": str(mapreduce_am_memory),
        "mapreduce_am_memory_java_opts": str(mapreduce_am_memory_java_opts),
        "datanode_heapsize": str(datanode_heapsize),
        "nodemanager_heapsize": str(nodemanager_heapsize),
        "hdfs_replication": str(replication_factor),
    }

    # Check assigned resources are valid
    for resource in hadoop_resources:
        value = int(hadoop_resources[resource])
        if value <= 0:
            bottleneck_resource = "CPU" if resource in ["vcores", "min_vcores"] else "memory"
            raise Exception("Error allocating resources for containers in Hadoop application. "
                            "Value for '{0}' is negative ({1}). The application may have been assigned "
                            "too low {2} values.".format(resource, value, bottleneck_resource))

    return hadoop_resources

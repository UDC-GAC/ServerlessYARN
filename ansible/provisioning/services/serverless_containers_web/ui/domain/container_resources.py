## Sizing of the containers of an app from its resources, limits and number of containers
from django.conf import settings

from ui.utils import DEFAULT_LIMIT_VALUES


def get_app_cores(cores):
    """Number of cores an app should size its own parameters to, given the cores allocated to one of its containers.

    It depends on the SMT mode actually applied by the platform ('effective_smt_mode', set during Vagrant or SLURM startup):
     - 'disabled' or 'enabled': apps use all the cores allocated to the container
     - 'hybrid': the container is allocated logical cores, but apps size their parameters to the physical ones
       (assuming 2 threads per core). E.g., Hadoop/Spark vcores, whose JVM background threads (GC, JIT, shuffle...)
       may then take advantage of the SMT siblings
    """
    if settings.PLATFORM_CONFIG.get('effective_smt_mode', 'disabled') == 'hybrid':
        return max(1, cores // 2)
    return cores


def getContainerResourcesForApp(number_of_containers, app_resources, app_limits, benevolence, is_hadoop_app):
    container_resources = {}
    container_resources['regular'] = {}
    container_resources['regular']['cpu_max'] = (app_resources['cpu']['max'] - app_resources['cpu']['current']) / number_of_containers
    irregular_type = None

    # CPU MAX SHARES ALLOCATION
    # We will try to allocate shares in multiples of 100, then if cpu_max is not a multiple of 100 we will run n-1
    # regular containers whose cpu_max will be adjusted to a multiple of 100 and 1 irregular container that compensates
    # the increase or decrease of the regular containers cpu_max. There are two cases:
    #
    # CASE 1: Creating a "bigger" container:
    # - If `cpu_max` is closer to a lower multiple of 100 (i.e., modulo < 50), we adjust the `cpu_max` of regular
    #   containers to that multiple (regular -= cpu_modulo). Then a bigger container must be created to compensate for
    #   the CPU decrease of the n - 1 regular containers (cpu_modulo * (number_of_containers - 1))
    #
    # CASE 2: Creating a "smaller" container:
    # - If `cpu_max` is closer to the next higher multiple of 100 (i.e., modulo >= 50), we adjust the `cpu_max` of
    #   regular containers up to this multiple (regular += 100 - cpu_modulo). Then a smaller container must be created
    #   to compensate for the extra CPU allocated to each of the n - 1 regular containers ((100 - cpu_modulo) * (number_of_containers - 1))
    # - To avoid undersized containers, this smaller container must have at least 10 CPU shares.
    correctly_allocated = False
    cpu_modulo = container_resources['regular']['cpu_max'] % 100
    # Hadoop apps avoid irregular containers since YARN limits all workers to the smallest container's resources
    if cpu_modulo == 0 or is_hadoop_app:
        # we don't have to do anything
        correctly_allocated = True
    else:
        # CASE 1: Creating a "bigger" container
        if cpu_modulo < 50:
            # Check that it is actually possible for the containers to give shares
            if container_resources['regular']['cpu_max'] > 100:
                irregular_type = 'bigger'
                container_resources['bigger'] = container_resources['regular'].copy()
                container_resources['bigger']['cpu_max'] = container_resources['regular']['cpu_max'] + cpu_modulo*(number_of_containers - 1)
                container_resources['regular']['cpu_max'] -= cpu_modulo
                correctly_allocated = True
        # CASE 2: Creating a "smaller" container
        else:
            smaller_resources = container_resources['regular']['cpu_max'] - ((100 - cpu_modulo) * (number_of_containers - 1))
            # Check that the smaller container is not too small
            if smaller_resources >= 10:
                irregular_type = 'smaller'
                container_resources['smaller'] = container_resources['regular'].copy()
                container_resources['smaller']['cpu_max'] = smaller_resources
                container_resources['regular']['cpu_max'] += (100 - cpu_modulo)
                correctly_allocated = True

    # CPU min and other resources allocation
    if irregular_type:
        # We will scale resources mantaining the original ratio with cpu_max
        # example: 400/100 max/min shares between 3 containers -> 133.333/33.333 shares each -> modified to 200/50 bigger container and 100/25 regular
        for resource in app_resources:
            for limit in ['max', 'min']:
                key = "{0}_{1}".format(resource, limit)
                if key == "cpu_max":
                    continue
                resource_ratio = app_resources['cpu']['max'] / app_resources[resource][limit]

                for container_type in ['regular', irregular_type]:
                    container_resources[container_type][key] = container_resources[container_type]['cpu_max'] / resource_ratio

        # Adjust resource values to integer
        for resource in app_resources:
            for limit in ['max', 'min']:
                key = "{0}_{1}".format(resource, limit)
                if key == "cpu_max":
                    continue

                resource_modulo = container_resources['regular'][key] % 1
                if resource_modulo < 0.5:
                    if container_resources['regular'][key] >= 1:
                        container_resources[irregular_type][key] = round(container_resources[irregular_type][key] + (resource_modulo * (number_of_containers - 1)))
                        container_resources['regular'][key] = int(container_resources['regular'][key])
                else:
                    smaller_resources = container_resources[irregular_type][key] - ((1 - resource_modulo) * (number_of_containers - 1))
                    if smaller_resources >= 1:
                        container_resources[irregular_type][key] = round(smaller_resources)
                        container_resources['regular'][key] = round(container_resources['regular'][key])
    else:
        for resource in app_resources:
            # MIN
            container_resources['regular']['{0}_min'.format(resource)] = int(app_resources[resource]['min'] / number_of_containers)

            # MAX
            if resource == 'cpu':
                continue
            container_resources['regular']['{0}_max'.format(resource)] = int((app_resources[resource]['max'] - app_resources[resource]['current']) / number_of_containers)

    # BOUNDARIES ALLOCATION
    # 2 options:
    #
    # - Manual allocation: Keep the app boundary and boundary_type for all the containers on the app
    #
    # - Automatic allocation: Boundaries for each container are assigned based on resource max and min values
    #   and the benevolence policy as follows: boundary = (max - min) / (2 ** (benevolence + 1))
    #   Example: For 200/100 max/min cpu and a low benevolence value (1 or 'lax' limits):
    #   boundary = (200 - 100) / 4 = 25 -> actual minimum cpu = minimum + 2 * boundary = 100 + 25 * 2 = 150
    #   Then boundaries are converted to a percentage of max, as this is how ServerlessContainers processes them if we
    #   use the default boundary type (percentage_of_max) -> boundary = (boundary / max) * 100
    container_types = {'regular'} if not irregular_type else {'regular', irregular_type}
    if benevolence == -1:
        # Manual allocation
        for resource in app_resources:
            boundary_key = '{0}_boundary'.format(resource)
            boundary_type_key = '{0}_boundary_type'.format(resource)
            for c_type in container_types:
                container_resources[c_type][boundary_key] = app_limits[resource]["boundary"]
                container_resources[c_type][boundary_type_key] = app_limits[resource]["boundary_type"]
    else:
        # Automatic allocation
        divider = 2 ** (benevolence + 1)  # benevolence=1 divider=4, benevolence=2 divider=8,...
        for resource in app_resources:
            boundary_key,boundary_type_key = '{0}_boundary'.format(resource),'{0}_boundary_type'.format(resource)
            max_key, min_key = '{0}_max'.format(resource),'{0}_min'.format(resource)
            for c_type in container_types:
                container_resources[c_type][boundary_key] = round(
                    ((container_resources[c_type][max_key] - container_resources[c_type][min_key]) * 100) /
                    (divider * container_resources[c_type][max_key]))
                container_resources[c_type][boundary_type_key] = DEFAULT_LIMIT_VALUES["boundary_type"]

    if not correctly_allocated:
        # use original resource allocation
        pass

    # Round cpu max to integer
    for c_type in container_types:
        container_resources[c_type]["cpu_max"] = round(container_resources[c_type]["cpu_max"])

    # Weights
    for resource in app_resources:
        weight_key = '{0}_weight'.format(resource)
        for c_type in container_types:
            container_resources[c_type][weight_key] = app_resources[resource]['weight']

    return container_resources

import math
from ansible.module_utils.basic import AnsibleModule

DEFAULT_BLOCKS_PER_CHUNKS = 0

def get_mappers(blocks, files, datanodes, mode):

    """
    Args:
        blocks (int): total number of block of the path to transfer
        files (int): total number of files inside the path to transfer
        datanodes (int): total number of datanodes that will run the transfer
        mode (string): mode of modulating the algorithm

    Returns:
        slicing (int): blocks per chunk into which the files in the path to transfer will be sliced

    Algorithm explanation:
        1. Edge cases:
            - If no files or blocks are provided return the default distcp slicing (which produces no slicing -> 1 mapper per file)
            - If there are less or an equal number of blocks that datanodes return 1 (the lowest slicing --> 1 mapper per block);

        2. Mode-specific behaviour
            - distcp-default: always return the default distcp slicing
            - mapred-default: always return 1
            - datanode-mapping: always try to approximate the number of mappers to the number of datanodes
            - best-effort: try to provide the best solution
                - if there are less files than datanodes: run the datanode-mapping algorithm
                - otherwise: return the default distcp slicing

        3. Details on the datanode-mapping algorithm:
            - The number of mappers obtained by the slicing is approximated by its best-case scenario, when the blocks are evenly distributed among the files
            - The exact number of mappers could be obtained knowing the number of blocks of each file, but it can be very costly to get all of them
            - If the amount of datanodes and files is the same: return the default distcp slicing
            - If there are less files than datanodes: try to generate the lowest amount of mappers that are equal or greater than the amount of datanodes
                - e.g., with 4 files, 30 blocks and 10 DNs:
                    - an average of 7.5 blocks per file is estimated, thus the algorithm tries until 8 blocks per file max
                    - with no slicing:       4 mappers --> 4 < 10 -> not enough mappers for the DNs
                    - with 1 blockperchunk:  30 mappers
                    - with 2 blocksperchunk: 16 mappers
                    - with 3 blocksperchunk: 12 mappers
                    - with 4 blocksperchunk: 8 mappers --> the algorithm would stop here and choose the previous slicing
                    - with 5 blocksperchunk: 8 mappers
                    - with 6 blocksperchunk: 8 mappers
                    - with 7 blocksperchunk: 6 mappers
                    - with 8 blocksperchunk: 4 mappers

            - If there are more files than datanodes: try to generate an amount of mappers that are as close as possible to a multiple of the number of datanodes
                - e.g., with 12 files, 57 blocks and 5 DNs:
                    - an average of 5 blocks per file is estimated, thus the algorithm tries until 5 blocks per file max
                    - with no slicing:       12 mappers --> 12/5 -> 2 mappers remaining
                    - with 1 blockperchunk:  57 mappers --> 57/5 -> 2 mappers remaining
                    - with 2 blocksperchunk: 33 mappers --> 33/5 -> 3 mappers remaining
                    - with 3 blocksperchunk: 24 mappers --> 24/5 -> 4 mappers remaining
                    - with 4 blocksperchunk: 21 mappers --> 21/5 -> 1 mappers remaining
                    - with 5 blocksperchunk: 12 mappers --> 12/5 -> 2 mappers remaining
                    --> the algorithm would stop here and choose 3 blocksperchunk, since with 4 remaining mappers only 1 DN would be idle
    """

    if files <= 0: return DEFAULT_BLOCKS_PER_CHUNKS
    if blocks <= 0: return DEFAULT_BLOCKS_PER_CHUNKS

    proportional_approximation = False
    match mode:
        case 'distcp-default': return DEFAULT_BLOCKS_PER_CHUNKS
        case 'mapred-default': return 1
        case 'best-effort':
            if files >= datanodes: return DEFAULT_BLOCKS_PER_CHUNKS
        case 'datanode-mapping':
            if files == datanodes: return DEFAULT_BLOCKS_PER_CHUNKS
            elif files > datanodes: proportional_approximation = True

    if blocks <= datanodes: return 1

    avg_blocks = blocks / files

    ## Base slicing
    best_slicing = 1
    best_estimated_mappers = blocks
    best_diff = blocks - datanodes
    best_remaining = best_estimated_mappers % datanodes

    ## Check if base is the best solution already when files > datanodes
    if proportional_approximation and best_remaining == 0:
        print("Chosen distribution: {0} blocks per chunk --> {1} mappers minimum".format(best_slicing, best_estimated_mappers))
        return best_slicing

    ## we will try to predict best-case scenario: most even distribution --> all files have floor(avg) blocks, and 'blocks' % 'files' files have an extra block
    best_distribution_extra_blocks = blocks % files

    for slicing in range(2, math.ceil(avg_blocks) + 1):

        estimated_mappers = (files-best_distribution_extra_blocks) * math.ceil(math.floor(avg_blocks) / slicing) + best_distribution_extra_blocks * math.ceil(math.ceil(avg_blocks) / slicing)

        print("{0} blocks per chunk generate at least {1} mappers".format(slicing, estimated_mappers))

        if not proportional_approximation:
            ## Approximate estimated mappers to be as close as datanodes
            diff = estimated_mappers - datanodes
            if diff == 0 or (diff > 0 and diff < best_diff):
                best_slicing = slicing
                best_estimated_mappers = estimated_mappers
                best_diff = diff

            if diff <= 0:
                break

        else:
            ## Approximate estimated mappers to be as close as a multiple of datanodes
            remaining = estimated_mappers % datanodes
            if remaining == 0 or (remaining > best_remaining):
                best_slicing = slicing
                best_estimated_mappers = estimated_mappers
                best_remaining = remaining
            
            if remaining == 0:
                break

    print("Chosen distribution: {0} blocks per chunk --> {1} mappers minimum".format(best_slicing, best_estimated_mappers))

    return best_slicing

def main():
    module_args = dict(
        number_of_blocks=dict(type='int', required=True),
        number_of_files=dict(type='int', required=True),
        number_of_datanodes=dict(type='int', required=True),
        mode=dict(type='str', required=True),
    )

    module = AnsibleModule(argument_spec=module_args)
    number_of_blocks = module.params['number_of_blocks']
    number_of_files = module.params['number_of_files']
    number_of_datanodes = module.params['number_of_datanodes']
    mode = module.params['mode']

    result = get_mappers(number_of_blocks, number_of_files, number_of_datanodes, mode)

    module.exit_json(changed=False, mappers=result)

if __name__ == '__main__':
    main()

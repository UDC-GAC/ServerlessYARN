import math
import sys
from ansible.module_utils.basic import AnsibleModule

DEFAULT_BLOCKS_PER_CHUNKS = 0

def get_mappers(blocks, files, max_mappers, mode):

    """
    Args:
        blocks (int): total number of block of the path to transfer
        files (int): total number of files inside the path to transfer
        max_mappers (int): max number of concurrent mappers that will run the transfer
        mode (string): mode of modulating the algorithm

    Returns:
        slicing (int): blocks per chunk into which the files in the path to transfer will be sliced

    Algorithm explanation:
        1. Edge cases:
            - If no files or blocks are provided return the default distcp slicing (which produces no slicing -> 1 mapper per file)
            - If there are less or an equal number of blocks than max_mappers return 1 (the lowest slicing --> 1 mapper per block);

        2. Mode-specific behaviour
            - distcp-default: always return the default distcp slicing
            - mapred-default: always return 1
            - nearest-multiple: try to approximate the number of mappers to a multiple of max_mappers
            - best-effort: try to provide the best solution
                - if there are less files than max_mappers: run the nearest-multiple algorithm
                - otherwise: return the default distcp slicing

        3. Details on the nearest-multiple algorithm:
            - The number of mappers obtained by the slicing is approximated by its best-case scenario, when the blocks are evenly distributed among the files
            - The exact number of mappers could be obtained knowing the number of blocks of each file, but it can be very costly to get all of them
            - If the amount of max_mappers and files is the same: return the default distcp slicing
            - If there are less files than max_mappers: try to generate the lowest amount of mappers that are equal or greater than the amount of max_mappers
                - e.g., with 4 files, 30 blocks and 10 max_mappers:
                    - an average of 7.5 blocks per file is estimated, thus the algorithm tries until 8 blocks per file max
                    - with no slicing:       4 mappers --> 4 < 10 -> not enough mappers
                    - with 1 blockperchunk:  30 mappers
                    - with 2 blocksperchunk: 16 mappers
                    - with 3 blocksperchunk: 12 mappers
                    - with 4 blocksperchunk: 8 mappers --> the algorithm would stop here and choose the previous slicing
                    - with 5 blocksperchunk: 8 mappers
                    - with 6 blocksperchunk: 8 mappers
                    - with 7 blocksperchunk: 6 mappers
                    - with 8 blocksperchunk: 4 mappers

            - If there are more files than max_mappers: try to generate an amount of mappers that are as close as possible to a multiple of the number of max_mappers
                - e.g., with 12 files, 57 blocks and 5 max_mappers:
                    - an average of 5 blocks per file is estimated, thus the algorithm tries until 5 blocks per file max
                    - with no slicing:       12 mappers --> 12/5 -> 2 mappers remaining
                    - with 1 blockperchunk:  57 mappers --> 57/5 -> 2 mappers remaining
                    - with 2 blocksperchunk: 33 mappers --> 33/5 -> 3 mappers remaining
                    - with 3 blocksperchunk: 24 mappers --> 24/5 -> 4 mappers remaining
                    - with 4 blocksperchunk: 21 mappers --> 21/5 -> 1 mappers remaining
                    - with 5 blocksperchunk: 12 mappers --> 12/5 -> 2 mappers remaining
                    --> the algorithm would stop here and choose 3 blocksperchunk, since with 4 remaining mappers only 1 mapper would be idle
    """

    if files <= 0: return DEFAULT_BLOCKS_PER_CHUNKS
    if blocks <= 0: return DEFAULT_BLOCKS_PER_CHUNKS

    proportional_approximation = False
    if mode   == 'distcp-default': return DEFAULT_BLOCKS_PER_CHUNKS
    elif mode == 'mapred-default': return 1
    elif mode == 'best-effort' and files >= max_mappers: return DEFAULT_BLOCKS_PER_CHUNKS
    elif mode == 'nearest-multiple':
        if files == max_mappers: return DEFAULT_BLOCKS_PER_CHUNKS
        elif files > max_mappers: proportional_approximation = True

    if blocks <= max_mappers: return 1

    avg_blocks = blocks / files

    ## Base slicing
    best_slicing = 1
    best_estimated_mappers = blocks
    best_diff = blocks - max_mappers
    best_remaining = best_estimated_mappers % max_mappers

    ## Check if base is the best solution already when files > max_mappers
    if proportional_approximation and best_remaining == 0:
        print("Chosen distribution: {0} blocks per chunk --> {1} mappers minimum".format(best_slicing, best_estimated_mappers))
        return best_slicing

    ## we will try to predict best-case scenario: most even distribution --> all files have floor(avg) blocks, and 'blocks' % 'files' files have an extra block
    best_distribution_extra_blocks = blocks % files

    for slicing in range(2, math.ceil(avg_blocks) + 1):

        estimated_mappers = (files-best_distribution_extra_blocks) * math.ceil(math.floor(avg_blocks) / slicing) + best_distribution_extra_blocks * math.ceil(math.ceil(avg_blocks) / slicing)

        print("{0} blocks per chunk generate at least {1} mappers".format(slicing, estimated_mappers))

        if not proportional_approximation:
            ## Approximate estimated mappers to be as close as max_mappers
            diff = estimated_mappers - max_mappers
            if diff == 0 or (diff > 0 and diff < best_diff):
                best_slicing = slicing
                best_estimated_mappers = estimated_mappers
                best_diff = diff

            if diff <= 0:
                break

        else:
            ## Approximate estimated mappers to be as close as a multiple of max_mappers
            remaining = estimated_mappers % max_mappers
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
        max_mappers=dict(type='int', required=True),
        mode=dict(type='str', required=True),
    )

    module = AnsibleModule(argument_spec=module_args)
    number_of_blocks = module.params['number_of_blocks']
    number_of_files = module.params['number_of_files']
    max_mappers = module.params['max_mappers']
    mode = module.params['mode']

    result = get_mappers(number_of_blocks, number_of_files, max_mappers, mode)

    module.exit_json(changed=False, mappers=result)

def main_cmd():
    number_of_blocks = int(sys.argv[1])
    number_of_files  = int(sys.argv[2])
    max_mappers      = int(sys.argv[3])
    mode             = sys.argv[4]

    result = get_mappers(number_of_blocks, number_of_files, max_mappers, mode)
    print(f"Result: {result} ")

if __name__ == '__main__':
    main()
    #main_cmd() ## useful for testing without Ansible
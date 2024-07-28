/*
 *  Copyright (c) 2018, INRIA
 *  Copyright (c) 2018, University of Lille
 *  All rights reserved.
 *
 *  Redistribution and use in source and binary forms, with or without
 *  modification, are permitted provided that the following conditions are met:
 *
 *  * Redistributions of source code must retain the above copyright notice, this
 *    list of conditions and the following disclaimer.
 *
 *  * Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions and the following disclaimer in the documentation
 *    and/or other materials provided with the distribution.
 *
 *  * Neither the name of the copyright holder nor the names of its
 *    contributors may be used to endorse or promote products derived from
 *    this software without specific prior written permission.
 *
 *  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 *  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 *  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 *  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
 *  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 *  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 *  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 *  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 *  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 *  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <regex.h>

#include "target.h"
#include "target_apptainer.h"

/*
 * CONTAINER_ID_REGEX is the regex used to extract the Apptainer container id from the cgroup path.
 * CONTAINER_ID_REGEX_EXPECTED_MATCHES is the number of expected matches from the regex. (num groups + 1)
 */
#define CONTAINER_ID_REGEX "perf_event/system.slice/apptainer-([0-9]+)\\.scope"
#define CONTAINER_ID_REGEX_EXPECTED_MATCHES 2


char *
target_apptainer_resolve_name(struct target *target)
{
    regex_t re;
    regmatch_t matches[CONTAINER_ID_REGEX_EXPECTED_MATCHES];
    char *target_id = NULL;
    char *target_name = NULL;
    size_t target_name_size;


    if (!regcomp(&re, CONTAINER_ID_REGEX, REG_EXTENDED | REG_NEWLINE)) {
        if (!regexec(&re, target->cgroup_path, CONTAINER_ID_REGEX_EXPECTED_MATCHES, matches, 0)) {
            target_id = strndup(target->cgroup_path + matches[1].rm_so, matches[1].rm_eo - matches[1].rm_so);
            if (target_id != NULL) {
                target_name_size = strlen("apptainer-") + strlen(target_id) + 1;
                target_name = (char *)malloc(target_name_size * sizeof(char));
                snprintf(target_name, target_name_size, "apptainer-%s", target_id);
                free(target_id);
            }
        }
        regfree(&re);
    }

    return target_name;
}

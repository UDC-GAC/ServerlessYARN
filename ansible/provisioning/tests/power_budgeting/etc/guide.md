The paramaters indicated for each experiment in `experiments.json` for each experiment are:

- **NUM_THREADS**: Currently used only for NPB applications where number of threads are specified through
  an environment file.

- **NPB_KERNEL**: Currently used only for NPB applications where NPB kernel is specified through an enviroment file.

- **DYNAMIC_SHARES_PER_WATT**: Value used as the ratio between watts and shares for power budgeting. Usually computed as:
  ```
  cpu_max_shares / (max_energy - min_energy) = (num_threads * 100) / (tdp - min_measured_energy)
  ```

- **STATIC_MODEL**: Static power model (without support for online learning) used to do power budgeting.

- **DYNAMIC_MODEL**: Dynamic power model (with support for online learning) used to do power budgeting.

- **STATIC_MODEL**: HW aware model (with support to take into account the underlying architecture) used to
  do power budgeting.

*NOTE: In Pluton we are assuming 250W for Intel Xeon Silver 4216 (specification indicates 200W). Then DYNAMIC_SHARES_PER_WATT is `(64 * 100) / (250 - 20) = 27.83`.*


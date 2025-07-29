# Experiment configuration
This file describes the configuration you must specify to build your automated tests. 

### Experiment parameters
The paramaters indicated for each experiment in `experiments.json` are:

- **name**: Name of the experiment.

- **app_dir**: The directory containing the app software, use a relative path to `ansible/provisioning/apps`.

- **app_config**: Name of the file containing the app configuration to deploy in the platform. The file must be stored in `etc/apps`.

- **rules_file**: Name of the file defining the platform rules for this experiment. The file must be stored in `etc/rules`.

- **setup_file**: File to configure the platform and set environment variables before experiment execution. The file must be stored in `etc/setup`.

- **entrypoint_file**: File to execute the experiment. The file must be stored in `etc/entrypoint`.

- **plots_config_file**: JSON file with the configuration of the plots for this experiment. The file must be stored in `etc/plots`.

*NOTE: Paths starting with `etc/` are relative to the directory containing this README.md, while paths like `ansible/provisioning/apps` are relative to the project root.*


### Plot options

In the JSON file with the plots configuration you can specify:

- **FONTSIZE**: Fontsize used in labels, ticks and legend. Default: 20.
- **SEPARATE_AXES**: Set true to separate axes between CPU and energy. It will be generalised to any resource. Default: false.
- **PLOT_LEGEND**: Set true to plot a legend. Default: false.
- **PLOT_CONVERGENCE_POINT**: Set true to plot convergence point. Only useful for energy plots (convergence is achieved if energy is within +-5% range of the power budget). Default: false.
- **X_TICKS_FREQUENCY**: Frequency of the ticks on the X axis. By default the axis will be divided in 10 ticks.
- **\<resource\>\_TICKS_FREQUENCY**: Frequency of the ticks on the Y axis used by a specific resource. By default the axis will be divided in 10 ticks.
- **MARKER_FREQUENCY**: Frequency of the markers. By default every point will be plotted (matplotlib default behaviour).
- **HARD_X_LIMIT**: Hard limit for the X axis. If this value is not specified the axis will adapt to the length of the execution.
- **HARD\_\<resource\>\_LIMIT**: Hard limit for the Y axis used by a specific resource. If this value is not specified the axis will adapt to the range of values covered by the resource. 
- **CUSTOM_X_AXIS_VALUES**: Specific values to set ticks on the X axis. This value overwrites the behaviour specified in X_TICKS_FREQUENCY and HARD_X_LIMIT.
- **CUSTOM_X_AXIS_FUNCTIONS**: Function to customise the X axis (e.g., use "sqrt" to apply a square-root transformation, expanding earlier values and compressing later ones). Supported values: ["sqrt", "square"]


### Sample app
You can check the sample app provided for this tests.  Take into account that the app start script was modified to log the start and end of the app execution in a file named `results.log`. This is because the profiler expects this file as part of the application output. You can simply achieve this by modifying the `start.sh` file inside `ansible/provisioning/apps/samples/sample_app`. Add the following instruction before and after the execution of stress tests:
```
echo "[$(date -u "+%Y-%m-%d %H:%M:%S%z")] " >> $OUTPUT_DIR/results.log
```
Make sure these logs are generated if you use another app (or add them manually after app execution to use the profiler).
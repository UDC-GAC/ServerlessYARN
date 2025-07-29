import os
import pandas as pd


class ResultsWriter:

    def __init__(self, output_dir=None):
        self._output_dir = output_dir

    def set_output_dir(self, d):
        if os.path.isdir(d) and os.path.exists(d):
            self._output_dir = d

    @staticmethod
    def write_latex(results_df, out_dir):
        # Configurable parameters
        include_borders = False
        caption = "Experiments"
        label = "tab:experiments"

        # Pre-processing
        # Avoid errors with percentage and underscore symbols
        columns = [col.replace('%', '\\%').replace('_', '\\_') for col in results_df.columns]
        # Set all columns centered (c) and include borders (|) if specified
        column_format = "|".join(["c" for _ in range(len(columns))])
        if include_borders:
            column_format = "|" + column_format + "|"

        # Get LaTeX from DataFrame
        latex_str = results_df.to_latex(index=False,
                                        float_format="%.2f",
                                        header=columns,
                                        column_format=column_format,
                                        label=label,
                                        caption=caption)

        # Post-processing
        # Top-rule: Upper border of the table
        latex_str = latex_str.replace("\\toprule", "\\hline")
        # Mid-rule: Between the headers and the values
        latex_str = latex_str.replace("\\midrule", "\\hline")
        # Bottom-rule: Lower border of the table
        latex_str = latex_str.replace("\\bottomrule", "\\hline" if include_borders else "\\_")
        # Avoid errors with percentage and underscore symbols
        latex_str = latex_str.replace('%', '\\%').replace('_', '\\%')

        # Write latex to .tex file
        with open(f"{out_dir}/global_stats.tex", "w") as f:
            f.write(latex_str)

    def write_experiment_results(self, exp_name, exp_df, exp_times, convergence_point):
        results_file = f"{self._output_dir}/stats"
        execution_time = exp_times["end_app_s"] - exp_times["start_app_s"]
        app_df = exp_df.loc[(exp_df['elapsed_seconds'] >= exp_times["start_app_s"]) &
                            (exp_df['elapsed_seconds'] <= exp_times["end_app_s"])]
        cpu_limit_df = app_df.loc[app_df['metric'] == "structure.cpu.current"]
        power_df = app_df.loc[app_df['metric'] == "structure.energy.usage"]
        power_budget = app_df.loc[app_df['metric'] == "structure.energy.max"]["value"].mean()
        avg_power = power_df["value"].mean()
        results = {
            "Execution time (s)": execution_time,
            "Minimum CPU limit (shares)": cpu_limit_df['value'].min(),
            "Maximum CPU limit (shares)": cpu_limit_df['value'].max(),
            "Error percentage (%)": abs((avg_power - power_budget) / power_budget) * 100,
            "Average power * Execution time (J)": avg_power * execution_time,
            "Total energy checksum (J)": power_df['value'].sum() * 5,  # Energy is 5s-averaged
            "Average power consumption (W)": avg_power,
        }

        if convergence_point:
            results["Convergence time (s)"] = max(convergence_point["time"] - exp_times["start_app_s"], 0)
            results["Needed scalings"] = convergence_point["needed_scalings"]
            results["Average Scaling Power (ASP)"] = convergence_point["value"]
            results["Power budget respected (%)"] = ((exp_times["end_app_s"] - convergence_point["time"]) / execution_time) * 100
            results["Convergence CPU limit (shares)"] = convergence_point["cpu_limit"]
        else:
            results["Convergence time (s)"] = "N/A"
            results["Needed scalings"] = "N/A"
            results["Average Scaling Power (ASP)"] = "N/A"
            results["Power budget respected (%)"] = 0
            results["Convergence CPU limit (shares)"] = "N/A"

        with open(results_file, "w") as f:
            for name, value in results.items():
                f.write(f"{name}: {value}\n")
                print(f"[{exp_name}] {name}: {value}")

        return results

    def write_global_results(self, results_dict):
        if results_dict:
            # Create a DataFrame from dictionary containing the results
            results_df = pd.DataFrame.from_dict(results_dict, orient='index').reset_index(names="Experiment")

            # Export the results to many different formats
            ResultsWriter.write_latex(results_df, self._output_dir)
            results_df.to_markdown(f"{self._output_dir}/global_stats.md", index=False)
            results_df.to_csv(f"{self._output_dir}/global_stats.csv", index=False)
            results_df.to_excel(f"{self._output_dir}/global_stats.xlsx", index=False)
            results_df.to_html(f"{self._output_dir}/global_stats.html", index=False)
            results_df.to_json(f"{self._output_dir}/global_stats.json")

# Copyright (C) 2018  INRIA
# Copyright (C) 2018  University of Lille
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
from collections import OrderedDict, defaultdict
from datetime import datetime
from itertools import compress
from math import ldexp, fabs
from statistics import median
from typing import Dict, List

from powerapi.handler import Handler
from powerapi.message import UnknowMessageTypeException
from powerapi.report import HWPCReport, PowerReport, FormulaReport, ControlReport
from sklearn.exceptions import NotFittedError
from sklearn.feature_selection import RFECV

from selfwatts.context import SelfWattsFormulaState
from selfwatts.formula import SelfWattsFormula, PowerModel


class ReportHandler(Handler):
    """
    This reports handler process the HWPC reports to compute a per-target power estimation.
    """

    def __init__(self, state: SelfWattsFormulaState):
        """
        Initialize a new report handler.
        :param state: State of the actor
        """
        Handler.__init__(self, state)
        self.state = state
        self.ticks = OrderedDict()
        self.formula = SelfWattsFormula(state.config.cpu_topology, state.config.history_window_size)
        self.hostname = self.state.sensor[7:]

    def _gen_rapl_events_group(self, system_report: HWPCReport) -> Dict[str, float]:
        """
        Generate an events group with the RAPL reference event converted in Watts for the current socket.
        :param system_report: The HWPC report of the System target
        :return: A dictionary containing the RAPL reference event with its value converted in Watts
        """
        cpu_events = next(iter(system_report.groups['rapl'][self.state.socket].values()))
        energy = ldexp(cpu_events[self.state.config.rapl_event], -32) / (self.state.config.reports_frequency / 1000)
        return {self.state.config.rapl_event: energy}

    def _gen_msr_events_group(self, system_report: HWPCReport) -> Dict[str, int]:
        """
        Generate an events group with the average of the MSR counters for the current socket.
        :param system_report: The HWPC report of the System target
        :return: A dictionary containing the average of the MSR counters
        """
        msr_events_group = defaultdict(int)
        msr_events_count = defaultdict(int)
        for _, cpu_events in system_report.groups['msr'][self.state.socket].items():
            for event_name, event_value in {k: v for k, v in cpu_events.items() if not k.startswith('time_')}.items():
                msr_events_group[event_name] += event_value
                msr_events_count[event_name] += 1

        return {k: (v / msr_events_count[k]) for k, v in msr_events_group.items()}

    def _gen_core_events_group(self, report: HWPCReport) -> Dict[str, int]:
        """
        Generate an events group with Core events for the current socket.
        The events value are the sum of the value for each CPU.
        :param report: The HWPC report of any target
        :return: A dictionary containing the Core events of the current socket
        """
        core_events_group = defaultdict(int)
        for _, cpu_events in report.groups['core'][self.state.socket].items():
            for event_name, event_value in {k: v for k, v in cpu_events.items() if not k.startswith('time_')}.items():
                core_events_group[event_name] += event_value

        return core_events_group

    def _gen_agg_core_report_from_running_targets(self, targets_report: Dict[str, HWPCReport]) -> Dict[str, int]:
        """
        Generate an aggregate Core events group of the running targets for the current socket.
        :param targets_report: List of Core events group of the running targets
        :return: A dictionary containing an aggregate of the Core events for the running targets of the current socket
        """
        agg_core_events_group = defaultdict(int)
        for _, target_report in targets_report.items():
            for event_name, event_value in self._gen_core_events_group(target_report).items():
                agg_core_events_group[event_name] += event_value

        return agg_core_events_group

    def _gen_agg_core_events_group_multiplexing_ratio(self, targets_report: Dict[str, HWPCReport]) -> float:
        """
        Compute the multiplexing ratio for the core events group.
        :param targets_report: HwPC report of the target
        :return: Multiplexing ratio of the events for the given report
        """
        time_running = 0
        time_enabled = 0

        for target_report in targets_report.values():
            time_running += target_report.groups['core'][self.state.socket]['time_running']
            time_enabled += target_report.groups['core'][self.state.socket]['time_enabled']

        return time_running / time_enabled if time_enabled > 0 else 0.0

    def _gen_power_report(self, timestamp: datetime, target: str, formula: str, raw_power: float, power: float, ratio: float) -> PowerReport:
        """
        Generate a power report using the given parameters.
        :param timestamp: Timestamp of the measurements
        :param target: Target name
        :param formula: Formula identifier
        :param power: Power estimation
        :return: Power report filled with the given parameters
        """
        metadata = {
            'scope': self.state.config.scope.value,
            'formula': formula,
            'ratio': ratio,
            'predict': raw_power,
        }
        return PowerReport(timestamp, self.state.sensor, target, int(self.state.socket), power, metadata)

    def _gen_formula_report(self, timestamp: datetime, pkg_frequency: float, model: PowerModel, error: float, events: List[str]) -> FormulaReport:
        """
        Generate a formula report using the given parameters.
        :param timestamp: Timestamp of the measurements
        :param pkg_frequency: Package average frequency
        :param model: Power model used for the estimation
        :param error: Error rate of the model
        :return: Formula report filled with the given parameters
        """
        metadata = {
            'scope': self.state.config.scope.value,
            'socket': self.state.socket,
            'layer_frequency': model.frequency,
            'pkg_frequency': pkg_frequency,
            'samples': len(model.history),
            'id': model.id,
            'error': error,
            'intercept': model.model.intercept_,
            'coef': list(model.model.coef_),
            'events': events,
        }
        return FormulaReport(timestamp, self.state.sensor, model.hash, metadata)

    def _gen_control_report(self, timestamp: datetime, events: List[str]) -> ControlReport:
        """
        Generate a control report using the given parameters.
        :param timestamp: Timestamp of the report
        :param events: List of events to send to the controller
        :return: Control report filled with the given parameters
        """
        return ControlReport(timestamp, self.state.sensor, 'selfwatts-controller', 'change-events', events)

    def _process_oldest_tick(self) -> (List[PowerReport], List[FormulaReport], List[ControlReport]):
        """
        Process the oldest tick stored in the stack and generate power reports for the running target(s).
        :return: Power reports of the running target(s)
        """
        timestamp, hwpc_reports = self.ticks.popitem(last=False)

        # logging.debug('MY HWPC REPORTS ARE: {0}'.format(hwpc_reports))

        # reports of the current tick
        power_reports = []
        formula_reports = []
        control_reports = []

        # prepare required events group of Global target
        try:
            global_report = hwpc_reports.pop('all')
        except KeyError:
            # cannot process this tick without the reference measurements
            return power_reports, formula_reports, control_reports

        # Added to avoid computing multiplexing ratio for no reports
        if len(hwpc_reports) == 0:
            return power_reports, formula_reports, control_reports

        # check if the current events set have multiplexing
        # if self._gen_agg_core_events_group_multiplexing_ratio(hwpc_reports) != 0.0:
        #    control_reports.append(self._gen_control_report(timestamp, []))
        #    self.formula.flush_power_models()
        #    logging.warning('there is multiplexing for the core events group, changing events set and flushing power models')
        #    return power_reports, formula_reports, control_reports

        rapl = self._gen_rapl_events_group(global_report)
        avg_msr = self._gen_msr_events_group(global_report)
        global_core = self._gen_agg_core_report_from_running_targets(hwpc_reports)

        #logging.debug('RAPL FROM GLOBAL REPORT IS: {0}'.format(rapl))
        #logging.debug('AVG MSR FROM GLOBAL REPORT IS: {0}'.format(avg_msr))
        #logging.debug('GLOBAL CORE FROM GLOBAL REPORT IS: {0}'.format(global_core))
        #logging.debug('SUPPORTED FREQUENCIES ARE: {0}'.format(self.formula.cpu_topology.get_supported_frequencies()))

        # check if the core events group changed since last tick
        core_events = sorted(global_core.keys())
        if core_events != self.state.core_events:
            self.formula.flush_power_models()
            self.state.core_events = core_events
            logging.debug('the core events set is different from previous ticks, flushing power models')

        # compute RAPL power report
        rapl_power = rapl[self.state.config.rapl_event]
        power_reports.append(self._gen_power_report(timestamp, f'{self.hostname}-rapl', self.state.config.rapl_event, 0.0, rapl_power, 1.0))

        # fetch power model to use
        pkg_frequency = self.formula.compute_pkg_frequency(avg_msr)
        model = self.formula.get_power_model(avg_msr)

        # compute Global target power report
        try:
            raw_global_power = model.compute_power_estimation(global_core)
            power_reports.append(self._gen_power_report(timestamp, f'{self.hostname}-global', model.hash, raw_global_power, raw_global_power, 1.0))
        except NotFittedError:
            model.store_report_in_history(rapl_power, global_core)
            model.learn_power_model(self.state.config.min_samples_required, 0.0, self.state.config.cpu_topology.tdp)
            return power_reports, formula_reports, control_reports

        # compute per-target power report
        total_targets_power = 0.0
        for target_name, target_report in hwpc_reports.items():
            target_core = self._gen_core_events_group(target_report)
            raw_target_power = model.compute_power_estimation(target_core)
            target_power, target_ratio = model.cap_power_estimation(raw_target_power, raw_global_power)
            target_power = model.apply_intercept_share(target_power, target_ratio)
            total_targets_power += target_power
            power_reports.append(self._gen_power_report(timestamp, target_name, model.hash, raw_target_power, target_power, target_ratio))

        # compute power model error from reference
        model_error = fabs(rapl_power - total_targets_power)

        # store power model error
        self.state.error_window[model.frequency].append(model_error)

        # store global report
        model.store_report_in_history(rapl_power, global_core)

        # store information about the power model used for this tick
        formula_reports.append(self._gen_formula_report(timestamp, pkg_frequency, model, model_error, list(global_core.keys())))

        # learn new power model if mean of error window exceeds the error threshold
        error_window_median = median(self.state.error_window[model.frequency])
        if error_window_median > self.state.config.error_threshold:
            model.learn_power_model(self.state.config.min_samples_required, 0.0, self.state.config.cpu_topology.tdp)
            logging.debug('---- ---- ---- ---- median error ({}) in layer {} exceeded for tick {}'.format(error_window_median, model.frequency, timestamp))

            # check events relevance if the layer have enough data
            if self.state.is_master:
                if len(model.history) == self.state.config.history_window_size:
                    if self.state.wait_counter[model.frequency] == 0:
                        selector = RFECV(model.generate_unfitted_model(), min_features_to_select=self.state.config.cpu_topology.fixed_counters).fit(model.history.X, model.history.y)
                        useful_events_mask = selector.get_support()

                        logging.debug('---- ---- checking events relevance for tick {}'.format(timestamp))
                        logging.debug('current layer = {}'.format(model.frequency))
                        logging.debug('current events = {}'.format(core_events))
                        logging.debug('current coefs = {}'.format(list(model.model.coef_)))
                        logging.debug('current corr = {}'.format(model.history.generate_pearson_coef()))
                        logging.debug('useful events mask = {}'.format(useful_events_mask))

                        if False in useful_events_mask:
                            selected_events = [event for event in compress(core_events, useful_events_mask) if event not in self.state.config.fixed_events]

                            if set([event for event in core_events if event not in self.state.config.fixed_events]) != set(selected_events):
                                control_reports.append(self._gen_control_report(timestamp, selected_events))
                                self.formula.flush_power_models()

                                logging.debug('changing current events set, clearing existing models')
                                logging.debug('selected events = {}'.format(selected_events))
                            else:
                                self.state.wait_counter.pop(model.frequency)
                                logging.debug('noop, the current events is the same as the current')
                        else:
                            self.state.wait_counter.pop(model.frequency)
                            logging.debug('all events are relevant, keeping current events set')
                    else:
                        self.state.wait_counter[model.frequency] -= 1

        return power_reports, formula_reports, control_reports

    def _process_report(self, report) -> None:
        """
        Process the received report and trigger the processing of the old ticks.
        :param report: HWPC report of a target
        """
        self.ticks.setdefault(report.timestamp, {}).update({report.target: report})

        # we wait before processing the ticks in order to mitigate the possible delay of the sensor/database.
        if len(self.ticks) > 2:
            power_reports, formula_reports, control_reports = self._process_oldest_tick()

            for report in [*power_reports, *formula_reports, *control_reports]:
                for _, pusher in self.state.pushers.items():
                    if isinstance(report, pusher.state.report_model.get_type()):
                        pusher.send_data(report)

    def handle(self, msg):
        """
        Process a report and send the result(s) to a pusher actor.
        :param msg: Received message
        :return: New actor state
        :raise: UnknowMessageTypeException when the given message is not an HWPCReport
        """
        if not isinstance(msg, HWPCReport):
            raise UnknowMessageTypeException(type(msg))

        self._process_report(msg)

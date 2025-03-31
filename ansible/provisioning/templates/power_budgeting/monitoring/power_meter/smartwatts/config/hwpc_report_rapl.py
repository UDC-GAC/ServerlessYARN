# BSD 3-Clause License
#
# Copyright (c) 2022, Inria
# Copyright (c) 2022, University of Lille
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
import datetime
import itertools
import logging
from collections import OrderedDict, defaultdict
from math import ldexp, fabs
from typing import Any

from powerapi.handler import Handler
from powerapi.report import PowerReport, HWPCReport, FormulaReport
from sklearn.exceptions import NotFittedError

from smartwatts.model import FrequencyLayer


class HwPCReportHandler(Handler):
    """
    HwPC reports handler.
    """

    def __init__(self, state):
        Handler.__init__(self, state)
        self.ticks: OrderedDict[datetime.datetime, dict[str, HWPCReport]] = OrderedDict()
        self.hostname = self.state.sensor[7:]

    def handle(self, msg: HWPCReport) -> None:
        """
        Process a HWPC report and send the result(s) to a pusher actor.
        :param msg: Received HWPC report
        """
        logging.debug('received message: %s', msg)
        self.ticks.setdefault(msg.timestamp, {}).update({msg.target: msg})

        # Start to process the oldest tick only after receiving at least 5 ticks.
        # We wait before processing the ticks in order to mitigate the possible delay between the sensor/database.
        if len(self.ticks) > 5:
            power_reports, formula_reports = self._process_oldest_tick()
            for report in itertools.chain(power_reports, formula_reports):
                for name, pusher in self.state.pushers.items():
                    if isinstance(report, pusher.state.report_model):
                        pusher.send_data(report)
                        logging.debug('sent report: %s to %s', report, name)

    def _process_oldest_tick(self) -> tuple[list[PowerReport], list[FormulaReport]]:
        """
        Process the oldest tick stored in the stack and generate power reports for the running target(s).
        :return: Power reports of the running target(s)
        """
        timestamp, hwpc_reports = self.ticks.popitem(last=False)
        power_reports = []
        formula_reports = []

        try:
            global_report = hwpc_reports.pop('all')
        except KeyError:
            # cannot process this tick without the reference measurements
            logging.error('Failed to process tick %s: missing global report', timestamp)
            return power_reports, formula_reports

        # Don't continue if there is no reports available.
        # Can happen when reports are dropped by a pre-processor.
        if len(hwpc_reports) == 0:
            return power_reports, formula_reports

        rapl = self._gen_rapl_events_group(global_report)
        rapl_power = rapl[self.state.config.rapl_event]
        power_reports.append(self._gen_power_report(timestamp, f'{self.hostname}-rapl', self.state.config.rapl_event, rapl_power, 1.0, global_report.metadata))

        # Just send RAPL power as target power
        for target_name, target_report in hwpc_reports.items():
            power_reports.append(self._gen_power_report(timestamp, target_name, self.state.config.rapl_event, rapl_power, 1.0, target_report.metadata))

        return power_reports, formula_reports

    def _gen_power_report(self, timestamp: datetime, target: str, formula: str, power: float, ratio: float, metadata: dict[str, Any]) -> PowerReport:
        """
        Generate a power report using the given parameters.
        :param timestamp: Timestamp of the measurements
        :param target: Target name
        :param formula: Formula identifier
        :param power: Power estimation
        :return: Power report filled with the given parameters
        """
        report_metadata = metadata | {
            'scope': self.state.config.scope.value,
            'socket': self.state.socket,
            'formula': formula,
            'ratio': ratio,
        }
        return PowerReport(timestamp, self.state.sensor, target, power, report_metadata)

    def _gen_rapl_events_group(self, system_report) -> dict[str, float]:
        """
        Generate an events group with the RAPL reference event converted in Watts for the current socket.
        :param system_report: The HWPC report of the System target
        :return: A dictionary containing the RAPL reference event with its value converted in Watts
        """
        cpu_events = next(iter(system_report.groups['rapl'][str(self.state.socket)].values()))
        energy = ldexp(cpu_events[self.state.config.rapl_event], -32) / (self.state.config.reports_frequency / 1000)
        return {self.state.config.rapl_event: energy}

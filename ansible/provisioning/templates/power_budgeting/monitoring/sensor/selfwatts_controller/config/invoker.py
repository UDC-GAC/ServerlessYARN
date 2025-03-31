import logging
from typing import List, Dict
from subprocess import Popen


class HwpcSensorInvoker:
    """
    HwPC-sensor invoker class.
    """

    def __init__(self, hostname: str, frequency: int, uri: str, database: str, collection: str):
        self.hostname = hostname
        self.frequency = frequency
        self.uri = uri
        self.database = database
        self.collection = collection
        self.process = None

    def _generate_cmdline(self, events: List[str]) -> List[str]:
        """
        Generate the command line arguments to start the sensor.
        """
        cmdline = ['/usr/bin/hwpc-sensor']
        cmdline += ['-p', '/sys/fs/cgroup/perf_event', '-n', self.hostname, '-f', str(self.frequency)]
        cmdline += ['-r', 'mongodb', '-U', self.uri, '-D', self.database, '-C', '{{ mongodb_hwpc_collection }}']
        cmdline += ['-s', 'rapl', '-e', 'RAPL_ENERGY_PKG']
        cmdline += ['-s', 'msr', '-e', 'TSC', '-e', 'APERF', '-e', 'MPERF']
        cmdline += ['-c', 'core'] + [arg for event in events for arg in ('-e', event)]
        return cmdline

    def start(self, events: List[str]) -> None:
        """
        Start the sensor process.
        """
        if len(events) > 0:
            logging.info('starting hwpc-sensor with events: {!r}'.format(events))
            self.process = Popen(self._generate_cmdline(events))

    def stop(self) -> None:
        """
        Stop the sensor process.
        """
        if self.process is not None:
            logging.info('stopping hwpc-sensor...')
            self.process.terminate()
            self.process.wait()
            self.process = None


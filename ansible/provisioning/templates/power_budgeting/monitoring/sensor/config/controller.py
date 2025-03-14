import logging
from typing import List
from random import shuffle

from selfwatts.controller.database import DatabaseAdapter
from selfwatts.controller.invoker import HwpcSensorInvoker
from selfwatts.controller.libpfm_wrapper import get_available_perf_counters, get_available_events_for_pmu


class SelfWattsController:
    """
    SelfWatts controller.
    """

    def __init__(self, hostname: str, pmu: str, fixed_events: List[str], db: DatabaseAdapter, sensor: HwpcSensorInvoker):
        self.hostname = hostname
        self.db = db
        self.pmu = pmu
        self.fixed_events = fixed_events
        self.sensor = sensor
        self.fixed_perf_counters, self.general_perf_counters = get_available_perf_counters()

    def _get_available_events(self, pmu: str) -> List[str]:
        """
        Filter the list of available events.
        """
        def is_event_excluded(event: str) -> bool:
            """
            Returns True if the event is excluded, False otherwise.
            """
            if 'OFFCORE_RESPONSE' in event:
                return True
            if 'UOPS_DISPATCHED_PORT' in event:
                return True

            return False

        available_events = [event for event in get_available_events_for_pmu(pmu) if not is_event_excluded(event) and event not in self.fixed_events]
        shuffle(available_events)
        return available_events

    def _generate_events_list(self, available_events: List[str], selected_events: List[str]) -> List[str]:
        """
        Generate the events list to be monitored by the sensor.
        """
        available_slots = self.general_perf_counters - selected_events.count(None)
        events = [event for event in selected_events if event is not None]

        for _ in range(len(events), available_slots):
            if len(available_events) > 0:
                events.append(available_events.pop())

        for fixed_event in self.fixed_events:
            events.insert(0, fixed_event)

        return events

    def handle_control_events(self) -> None:
        """
        Handle the control events from the database.
        """
        available_events = self._get_available_events(self.pmu)

        logging.info('there is {} events and {} fixed {} general performance counters for {} PMU'.format(len(available_events), self.fixed_perf_counters, self.general_perf_counters, self.pmu))
        logging.info('Available events: {0}'.format(available_events))

        # Added initialisation for the sensor
        current_events = self._generate_events_list(available_events, [])
        logging.info('Initialising sensor with events set {!r}'.format(current_events))
        self.sensor.start(current_events)

        logging.info('watching for control events from database...')
        while True:
            control_event = self.db.watch_control_event(self.hostname)
            logging.debug('received control event: {!r}'.format(control_event))

            new_events = self._generate_events_list(available_events, control_event.parameters)
            logging.info('new events set for sensor: {!r}'.format(new_events))
            logging.info('there is {} available events remaining'.format(len(available_events)))

            if set(current_events) != set(new_events):
                self.sensor.stop()
                self.sensor.start(new_events)
                current_events = new_events[:]
            else:
                logging.debug('current events set match new events set, this control event is ignored')


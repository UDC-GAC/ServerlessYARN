from ui.forms import DBSnapshoterForm, GuardianForm, ScalerForm, StructuresSnapshoterForm, SanityCheckerForm, RefeederForm, ReBalancerForm, EnergyControllerForm, WattTrainerForm

SERVICES_OPTIONS = {
    "database_snapshoter": ["debug","documents_persisted","polling_frequency"],
    "guardian": ["debug", "event_timeout","guardable_resources","structure_guarded","window_delay","window_timelapse"],
    "scaler": ["check_core_map","debug","polling_frequency","request_timeout"],
    "structures_snapshoter": ["polling_frequency","debug","structures_persisted","resources_persisted"],
    "sanity_checker": ["debug","delay"],
    "refeeder": ["debug","structures_refeeded","generated_metrics","window_delay","window_timelapse"],
    "rebalancer": ["debug","diff_percentage","stolen_percentage","window_delay","window_timelapse","resources_balanced","structures_balanced","containers_scope","balancing_policy","balancing_method","only_running"],
    "energy_controller": ["polling_frequency", "event_timeout", "window_timelapse", "window_delay", "debug", "structure_guarded", "control_policy", "power_model"],
    "watt_trainer": ["window_timelapse", "window_delay", "generated_metrics", "models_to_train", "debug"]
}

SERVICES_FORMS = {
    "database_snapshoter": lambda **kwargs: DBSnapshoterForm(**kwargs),
    "guardian": lambda **kwargs: GuardianForm(**kwargs),
    "scaler": lambda **kwargs: ScalerForm(**kwargs),
    "structures_snapshoter": lambda **kwargs: StructuresSnapshoterForm(**kwargs),
    "sanity_checker": lambda **kwargs: SanityCheckerForm(**kwargs),
    "refeeder": lambda **kwargs: RefeederForm(**kwargs),
    "rebalancer": lambda **kwargs: ReBalancerForm(**kwargs),
    "energy_controller": lambda **kwargs: EnergyControllerForm(**kwargs),
    "watt_trainer": lambda **kwargs: WattTrainerForm(**kwargs)
}

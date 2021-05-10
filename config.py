from skabenclient.config import DeviceConfig

ESSENTIAL = {
    'closed': True,
    'sound': True,
    'blocked': False,
    'acl': [],
}


class LockConfig(DeviceConfig):

    def __init__(self, config_path: str):
        self.parsed_acl = self.gen_access_list()
        self.minimal_essential_conf = ESSENTIAL
        super().__init__(config_path)

    @property
    def access_list(self) -> list:
        if not self.parsed_acl:
            self.parsed_acl = self.gen_access_list()
        return self.parsed_acl

    def gen_access_list(self) -> list:
        result = []
        not_parsed = self.get('acl', {})
        current_alert = int(self.get('alert', '0'))
        # get unique state ids list like [1, 2, ..., 5]
        unique_states = list(set(sum(list(not_parsed.values()), [])))
        if current_alert not in unique_states:
            # no access codes configured for current alert level
            return result

        for code, state_list in not_parsed.items():
            state_list = [int(state) for state in state_list]
            if current_alert in state_list:
                result.append(code)

        return result

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.gen_access_list()

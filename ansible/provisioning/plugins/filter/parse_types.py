import ast

class FilterModule(object):
    def filters(self):
        return {
            'parse_types': self.parse_types
        }

    def parse_types(self, data):
        if isinstance(data, dict):
            return {k: self.parse_types(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.parse_types(item) for item in data]
        elif isinstance(data, str):
            try:
                # Safely evaluate strings into their native Python types
                return ast.literal_eval(data)
            except (ValueError, SyntaxError):
                return data
        return data

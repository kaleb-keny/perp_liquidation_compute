import yaml

def parse_yaml(path):
    with open(path, 'r') as stream:
        return  yaml.load(stream, Loader=yaml.FullLoader)
import dictconfig
from ruamel.yaml import YAML

yaml = YAML()

with open("testing.yaml") as fileobj:
    data = yaml.load(fileobj)


schema = {
    "type": "dict",
    "required_keys": {
        "foo": {
            "type": "dict",
            "required_keys": {
                "bar": {"type": "integer"},
                "baz": {
                    "type": "dict",
                    "required_keys": {
                        "ready": {"type": "boolean"}
                    }
                }
            }
        },
        "something": {"type": "list", "element_schema": {"type": "integer"}}
    }
}

import copy
output = copy.deepcopy(data)


def is_leaf(x):
    return not isinstance(x, dict) and not isinstance(x, list)


def copy_into(dst, src):
    if isinstance(dst, dict):
        keys = dst.keys()
    elif isinstance(dst, list):
        keys = range(len(dst))
    else:
        raise ValueError("no!")

    for key in keys:
        x = src[key]
        if is_leaf(x):
            dst[key] = src[key]
        else:
            copy_into(dst[key], src[key])

resolved = dictconfig.resolve(data, schema)

copy_into(output, resolved)


with open("testing_new.yaml", "w") as fileobj:
    yaml.dump(output, fileobj)

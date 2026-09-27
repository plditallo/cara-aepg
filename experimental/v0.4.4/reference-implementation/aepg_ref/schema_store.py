import json
from pathlib import Path
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

class SchemaStore:
    def __init__(self, schema_dir):
        self.schema_dir = Path(schema_dir)
        self.schemas = {}
        resources = []
        for p in self.schema_dir.glob("*.schema.json"):
            s = json.loads(p.read_text())
            Draft202012Validator.check_schema(s)
            self.schemas[p.stem.replace(".schema","")] = s
            resources.append((s["$id"], Resource.from_contents(s)))
        self.registry = Registry().with_resources(resources)

    def validate(self, schema_name, instance):
        schema = self.schemas[schema_name]
        validator = Draft202012Validator(schema, registry=self.registry)
        errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
        return errors

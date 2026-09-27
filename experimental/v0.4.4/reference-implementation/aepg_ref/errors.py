class AEPGError(Exception):
    pass

class SchemaValidationError(AEPGError):
    pass

class SemanticValidationError(AEPGError):
    pass

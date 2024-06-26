from marshmallow import Schema, fields


class MaterialSchema(Schema):
    id = fields.Number()
    name = fields.Str(required=True)
    description = fields.Str()
    category = fields.Str()
    materialJson = fields.Str()
    materialMetadataJson = fields.Str()
    defaultAbsorption = fields.Number()
    defaultScattering = fields.Str()
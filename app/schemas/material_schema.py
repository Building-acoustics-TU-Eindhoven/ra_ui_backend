from marshmallow import Schema, fields


class MaterialCreateSchema(Schema):
    name = fields.String(required=True)
    category = fields.String(required=True)
    description = fields.String(allow_none=True)
    absorptionCoefficients = fields.List(fields.Float())


class MaterialSchema(MaterialCreateSchema):
    id = fields.Number()
    createdAt = fields.String()
    updatedAt = fields.String()

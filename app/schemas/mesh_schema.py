from marshmallow import Schema, fields, post_load
from app.services import file_service
from app.schemas.task_schema import TaskSchema


# class ProjectSchemaInMesh(Schema):
#     id = fields.Integer(data_key="projectId")
#     name = fields.Str(required=True, data_key="projectName")
#     group = fields.Str(required=True, data_key="projectTag")
#

class MeshSchema(Schema):
    id = fields.Number()
    modelId = fields.Integer()
    taskId = fields.Integer()

    createdAt = fields.Str()
    updatedAt = fields.Str()


class MeshWithTaskSchema(MeshSchema):
    task = fields.Nested(TaskSchema, many=False)


class MeshQuerySchema(Schema):
    modelId = fields.Integer(required=True)


class MeshUpdateSchema(Schema):
    name = fields.Str(required=True)
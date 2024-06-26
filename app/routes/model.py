from flask.views import MethodView
from flask_smorest import Blueprint
from flask_smorest import abort

from app.schemas.model_schema import ModelCreateSchema, ModelSchema, ModelUpdateSchema
from app.services import model_service

blp = Blueprint("Model", __name__, description="Model API")


@blp.route("/models")
class ModelList(MethodView):

    @blp.arguments(ModelCreateSchema, location='query')
    @blp.response(200, ModelSchema)
    def post(self, query_data):
        result = model_service.create_new_model(query_data)
        return result


@blp.route("/models/<int:model_id>")
class Model(MethodView):
    @blp.response(200, ModelSchema(many=True))
    def get(self, model_id):
        result = model_service.get_model(model_id)
        return result

    @blp.arguments(ModelUpdateSchema)
    def put(self, model_body, model_id):
        result = model_service.update_model(model_body, model_id)
        return result

    @blp.response(200, ModelSchema(many=True))
    def delete(self, model_id):
        result = model_service.delete_model(model_id)
        return result
from datetime import datetime

from app.db import db


# name: Optional[str] = None,
# type_: Optional[_TypeEngineArgument[_T]] = None,
# autoincrement: _AutoIncrementType = "auto",
# default: Optional[Any] = None,
# doc: Optional[str] = None,
# key: Optional[str] = None,
# index: Optional[bool] = None,
# unique: Optional[bool] = None,
# info: Optional[_InfoType] = None,
# nullable: Optional[
#     Union[bool, Literal[SchemaConst.NULL_UNSPECIFIED]]
# ] = SchemaConst.NULL_UNSPECIFIED,
# onupdate: Optional[Any] = None,
# primary_key: bool = False,
# server_default: Optional[_ServerDefaultType] = None,
# server_onupdate: Optional[FetchedValue] = None,
# quote: Optional[bool] = None,
# system: bool = False,
# comment: Optional[str] = None,

class Model(db.Model):
    __tablename__ = "models"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)

    sourceFileId = db.Column(db.Integer, nullable=False)
    outputFileId = db.Column(db.Integer, nullable=False)

    projectId = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    project = db.relationship("Project", back_populates="models", foreign_keys=[projectId])

    mesh = db.relationship("Mesh", back_populates="model", cascade="all, delete")
    simulations = db.relationship("Simulation", back_populates="model", cascade="all, delete")
    simulationRuns = db.relationship("SimulationRun", back_populates="model", cascade="all, delete")

    createdAt = db.Column(db.String(), default=datetime.now())
    updatedAt = db.Column(db.String(), default=datetime.now())
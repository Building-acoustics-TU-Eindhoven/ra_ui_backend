import json
import logging
import os
from datetime import datetime

import gmsh
from celery import shared_task
from flask_smorest import abort
from sqlalchemy.orm import joinedload, scoped_session, sessionmaker

import config
from app.db import db
from app.models import File, Simulation, SimulationRun, Task
from app.services import file_service, material_service, mesh_service, model_service
from app.types import Status, TaskType

# Create logger for this module
logger = logging.getLogger(__name__)


def create_new_simulation(simulation_data):
    new_simulation = Simulation(**simulation_data)

    try:
        db.session.add(new_simulation)
        db.session.commit()

    except Exception as ex:
        db.session.rollback()
        logger.error(f"Can not create a new model: {ex}")
        abort(400, message=f"Can not create a new model: {ex}")

    return new_simulation


def update_simulation_by_id(simulation_data, simulation_id):
    simulation = get_simulation_by_id(simulation_id)

    try:
        for key, value in simulation_data.items():
            setattr(simulation, key, value)

        simulation.updatedAt = datetime.now()
        db.session.commit()

    except Exception as ex:
        db.session.rollback()
        logger.error(f"Can not update the simulation: {ex}")
        abort(400, message=f"Can not update the simulation: {ex}")

    return simulation


def get_simulation_by_model_id(model_id):
    return (
        Simulation.query.filter_by(modelId=model_id)
        .order_by(Simulation.updatedAt.desc())
        .all()
    )


def get_simulation_run():
    result = (
        SimulationRun.query.options(joinedload(SimulationRun.simulation))
        .filter(SimulationRun.simulation)
        .all()
    )

    for simulation_run in result:
        update_simulation_run_status(simulation_run, simulation_run.simulation)

    return result


def get_simulation_run_by_id(simulation_run_id):
    simulation_run = SimulationRun.query.filter_by(id=simulation_run_id).first()
    if not simulation_run:
        logger.error(
            "Simulation Run with id " + str(simulation_run_id) + "does not exists!"
        )
        abort(400, message="Simulation Run doesn't exists!")
    return simulation_run


def delete_simulation(simulation_id):
    try:
        simulation = Simulation.query.filter_by(id=simulation_id).one()
        SimulationRun.query.filter_by(id=simulation.id).delete()
        Simulation.query.filter_by(id=simulation.id).delete()

        db.session.commit()

    except Exception as ex:
        db.session.rollback()
        logger.error(f"Error deleting the simulation: {ex}")
        abort(500, message=f"Error deleting the simulation: {ex}")


def delete_simulation_run(simulation_run_id):
    try:
        SimulationRun.query.filter_by(id=simulation_run_id).delete()
        db.session.commit()

    except Exception as ex:
        db.session.rollback()
        logger.error(f"Error deleting the previous simulation run: {ex}")
        abort(500, message=f"Error deleting the previous simulation run: {ex}")


def get_simulation_by_id(simulation_id):
    simulation = Simulation.query.filter_by(id=simulation_id).first()
    if not simulation:
        logger.error("Simulation with id " + str(simulation_id) + "does not exists!")
        abort(400, message="Simulation doesn't exists!")
    return simulation


def create_source_task(task_type, source_id):
    try:
        task = Task(taskType=task_type, status=Status.Created)
        db.session.add(task)
        db.session.commit()

    except Exception as ex:
        db.session.rollback()
        logger.error(f"Error creating the task: {ex}")
        abort(500, message=f"Error creating the task: {ex}")

    return {
        "id": task.id,
        "taskType": task.taskType.value,
        "status": task.status.value,
        "message": task.message,
        "percentage": 0,
        "sourcePointId": source_id,
    }


def create_result_source_object(source, receivers, result_type):
    responses_obj = []

    for receiver in receivers:
        responses_obj.append(
            {
                "label": receiver["label"],
                "orderNumber": receiver["orderNumber"],
                "x": receiver["x"],
                "y": receiver["y"],
                "z": receiver["z"],
                "pointId": receiver["id"],
                "parameters": {
                    "edt": [],
                    "t20": [],
                    "t30": [],
                    "c80": [],
                    "d50": [],
                    "ts": [],
                    "spl_t0_freq": [],
                },
                "receiverResults": [],
            }
        )

    return {
        "label": source["label"],
        "orderNumber": source["orderNumber"],
        "percentage": 0,
        "sourcePointId": source["id"],
        "sourceX": source["x"],
        "sourceY": source["y"],
        "sourceZ": source["z"],
        "resultType": result_type,
        "frequencies": [125, 250, 500, 1000, 2000],
        "responses": responses_obj,
    }


def start_solver_task(simulation_id):
    simulation = get_simulation_by_id(simulation_id)

    if simulation.simulationRunId:
        delete_simulation_run(simulation.simulationRunId)

    model = model_service.get_model(simulation.modelId)
    json_path = file_service.get_file_related_path(
        model.outputFileId, simulation_id, extension="json"
    )
    msh_path = file_service.get_file_related_path(
        model.outputFileId, simulation_id, extension="msh"
    )

    sources_tasks = []
    results_container = []

    for source in simulation.sources:
        task_statuses = []
        if simulation.taskType.value in (TaskType.DE.value, TaskType.BOTH.value):
            task_statuses.append(create_source_task(TaskType.DE.value, source["id"]))
            results_container.append(
                create_result_source_object(
                    source, simulation.receivers, TaskType.DE.value
                )
            )
        if simulation.taskType.value in (TaskType.DG.value, TaskType.BOTH.value):
            task_statuses.append(create_source_task(TaskType.DG.value, source["id"]))
            results_container.append(
                create_result_source_object(
                    source, simulation.receivers, TaskType.DG.value
                )
            )

        sources_tasks.append(
            {
                "label": source["label"],
                "orderNumber": source["orderNumber"],
                "percentage": 0,
                "sourcePointId": source["id"],
                "taskStatuses": task_statuses,
            }
        )

    new_simulation_run = SimulationRun(
        sources=sources_tasks,
        receivers=simulation.receivers,
        taskType=simulation.taskType,
        settingsPreset=simulation.settingsPreset,
        layerIdByMaterialId=simulation.layerIdByMaterialId,
        solverSettings=simulation.solverSettings,
        status=Status.Created,
    )

    try:
        simulation.completedAt = ""
        simulation.status = Status.Created

        db.session.add(new_simulation_run)
        db.session.commit()

        simulation.simulationRunId = new_simulation_run.id
        db.session.commit()

    except Exception as ex:
        db.session.rollback()
        logger.error(f"Can not create a new simulation run: {ex}")
        abort(400, message=f"Can not create a new simulation run: {ex}")

    # Run the background task asynchronously
    absorption_coefficients = {}
    for layer, material_id in simulation.layerIdByMaterialId.items():
        material = material_service.get_material_by_id(material_id)
        # Ignore the lower frequencies in [63, 125, 250, 500, 1000, 2000, 4000]
        absorption_coefficients[layer] = ", ".join(
            map(str, material.absorptionCoefficients[1:-1])
        )

    with open(json_path, "w") as json_result_file:
        json_result_file.write(
            json.dumps(
                {
                    "absorption_coefficients": absorption_coefficients,
                    "msh_path": msh_path,
                    "results": results_container,
                },
                indent=4,
            )
        )

    run_solver.delay(new_simulation_run.id, json_path)
    try:
        simulation.status = Status.Queued
        new_simulation_run.status = Status.Queued
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        logger.error(f"Can not update the new simulation run status: {ex}")
        abort(400, message=f"Can not update a new simulation run status: {ex}")

    return new_simulation_run


@shared_task
def run_solver(simulation_run_id, json_path):
    import logging
    import time

    from app.db import db
    from app.models import SimulationRun
    from app.types import Status
    from Diffusion.FiniteVolumeMethod.FVMInterface import de_method

    # Create logger for this module

    logger.info(f"Running solver task for simulation_run_id: {simulation_run_id}")

    # Scoped session factory to ensure proper session management
    session_factory = sessionmaker(bind=db.engine)
    session = scoped_session(session_factory)()  # Create a new session for this thread

    try:
        simulation_run = session.query(SimulationRun).get(simulation_run_id)
        if simulation_run is None:
            logger.error(f"SimulationRun with id {simulation_run_id} not found")
            return

        logger.info(f"SimulationRun found: {simulation_run}")
        simulation = (
            session.query(Simulation)
            .filter_by(simulationRunId=simulation_run.id)
            .first()
        )

        if simulation_run:
            simulation_run.status = Status.Queued

        if simulation:
            simulation.status = Status.Queued
        session.commit()
        logger.info(f"Simulation(run) status updated to {simulation_run.status}")

        try:
            if simulation_run:
                simulation_run.status = Status.InProgress
            simulation.status = Status.InProgress
            session.commit()
            logger.info(f"SimulationRun status updated to {simulation_run.status}")
            de_method(json_file_path=json_path)
            if simulation_run:
                simulation_run.status = Status.Completed
                simulation_run.updatedAt = datetime.now()
                simulation_run.completedAt = datetime.now()
            simulation.status = Status.Completed
            simulation.updatedAt = datetime.now()
            simulation.completedAt = datetime.now()
            session.commit()
            logger.info(f"SimulationRun status updated to {simulation_run.status}")
        except Exception as ex:
            simulation_run.status = Status.Error
            simulation.status = Status.Error
            session.commit()
            logger.error(f"Cannot run the method because: {ex}")

    except Exception as ex:
        session.rollback()
        logger.error(f"Cannot update simulation run: {ex}")

    finally:
        session.close()  # Ensure the session is closed after use
        logger.info(f"Session closed for simulation_run_id: {simulation_run_id}")


def get_simulation_result_by_id(simulation_id):
    simulation = get_simulation_by_id(simulation_id)
    model = model_service.get_model(simulation.modelId)
    json_path = file_service.get_file_related_path(
        model.outputFileId, simulation_id, extension="json"
    )

    with open(json_path, "r") as json_file:
        result_container = json.load(json_file)

    return result_container["results"]


def update_simulation_run_status(simulation_run, simulation):
    # TODO: update source percentage later
    model = model_service.get_model(simulation.modelId)
    json_path = file_service.get_file_related_path(
        model.outputFileId, simulation.id, extension="json"
    )
    with open(json_path, "r") as json_file:
        result_container = json.load(json_file)
        try:
            simulation_run.percentage = result_container["results"][0]["percentage"]
            db.session.commit()
        except Exception as ex:
            db.session.rollback()
            logger.warning(msg=f"Can not update percentage of the simulation run: {ex}")
            abort(400, message=f"Can not update percentage of the simulation run: {ex}")


def get_simulation_run_status_by_id(simulation_run_id):
    simulation = Simulation.query.filter_by(simulationRunId=simulation_run_id).first()
    if not simulation:
        logger.error(
            f"Simulation for the simulation run id {str(simulation_run_id)} does not exists!"
        )
        abort(400, message="Simulation doesn't exists!")

    simulation_run = SimulationRun.query.filter_by(id=simulation_run_id).first()
    if not simulation_run:
        abort(400, message="Simulation run doesn't exists!")

    update_simulation_run_status(simulation_run, simulation)

    return simulation_run

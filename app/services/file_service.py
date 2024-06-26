import os
import logging
from app.db import db
from app.models import File
from flask_smorest import abort
import config
from werkzeug.utils import secure_filename
import uuid

# Create logger for this module
logger = logging.getLogger(__name__)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.DefaultConfig.ALLOWED_EXTENSIONS


def get_slot():
    try:
        file = File()

        db.session.add(file)
        db.session.commit()
        return {
            'id': file.slot,
            'uploadUrl': f"http://{os.getenv('FLASK_RUN_HOST')}:{os.getenv('FLASK_RUN_PORT')}/files?slot={file.slot}"
        }
    except Exception as ex:
        db.session.rollback()
        logger.error(f"Can not insert a new file slot: {ex}")
        abort(400, message=f"Can not insert a new file slot: {ex}")


def create_file(query_data, body_data):
    file = File.query.filter_by(slot=query_data['slot']).first()
    if not file:
        logger.error("There is not empty slot in the system, try later!")
        abort(400, message="There is not empty slot in the system, try later!")

    upload_file = body_data['file']
    try:
        # Upload the file to the system
        if upload_file.filename == '':
            abort(404, 'No selected file')

        if upload_file and allowed_file(upload_file.filename):
            filename = secure_filename(upload_file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{filename.rsplit('.', 1)[0]}_{uuid.uuid4().hex}.{file_ext}"

            file.fileName = unique_filename
            upload_file.save(
                os.path.join(
                    config.DefaultConfig.UPLOAD_FOLDER, unique_filename
                )
            )

            db.session.commit()
    except Exception as ex:
        db.session.rollback()
        logger.error(f"The file can not uploaded!: {ex}")
        abort(400, message=f"The file can not uploaded!: {ex}")

    return file


def consume(slot):
    file = File.query.filter_by(slot=slot).first()
    if not file:
        logger.error('File with slot ' + str(slot) + 'does not exists!')
        abort(400, message="File doesn't exists!")

    try:
        file.consumed = True

        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        logger.error(f"The file can not uploaded!: {ex}")
        abort(400, message=f"The file can not uploaded!: {ex}")

    return file


def get_file_url(file_id):
    file = File.query.filter_by(id=file_id).first()
    if not file:
        logger.error('File with id ' + str(file_id) + 'does not exists!')
        abort(400, message="File doesn't exists!")

    return f"http://{os.getenv('API_HOST')}:{os.getenv('API_PORT')}/uploads/{file.filename.replace('.3dm', '.zip')}"
import logging
from flask_smorest import abort
from app.services import model_service, file_service
import rhino3dm
import os
import config
import gmsh
from Diffusion.FiniteVolumeMethod.CreateMeshFVM import generate_mesh

from app.models import Mesh

# Create logger for this module
logger = logging.getLogger(__name__)


def get_meshes_by_model_id(model_id):
    return Mesh.query.filter_by(
        modelId=model_id
    ).all()


def get_mesh_by_id(mesh_id):
    mesh = Mesh.query.filter_by(id=mesh_id).first()
    if not mesh:
        abort(404, message="Mesh does not exist")
    return mesh


def start_mesh_task(model_id):
    model = model_service.get_model(model_id)
    file = file_service.get_file_by_id(model.outputFileId)

    directory = config.DefaultConfig.UPLOAD_FOLDER
    file_name, file_extension = os.path.splitext(
        os.path.basename(file.fileName)
    )
    rhino3dm_path = os.path.join(directory, f"{file_name}.3dm")
    geo_path = os.path.join(directory, f"{file_name}.geo")
    msh_path = os.path.join(directory, f"{file_name}.msh")
    generate_geo_file(rhino3dm_path, geo_path)
    generate_mesh(geo_path, msh_path, 1)

    # create a new task with type mesh
    # create a mesh
    # in the end you should return mesh model


def generate_geo_file(rhino_file_path, geo_file_path):
    file3dm = rhino3dm.File3dm()
    model = file3dm.Read(rhino_file_path)

    # Collect points, lines, line loops, and physical surfaces
    points = {}
    lines = {}
    line_loops = {}
    plane_surfaces = {}
    physical_surfaces = {}

    point_index = 1
    line_index = 1
    surface_index = 1
    physical_surface_counter = 1

    # Iterate over the objects in the 3dm model
    for obj in model.Objects:
        if isinstance(obj.Geometry, rhino3dm.Mesh):

            faces = obj.Geometry.Faces
            faces.ConvertTrianglesToQuads(0.5, 0)
            vertices = obj.Geometry.Vertices
            vertices.CombineIdentical(True, True)

            # Create a mapping from vertex index to Gmsh point index
            vertex_map = {}

            # Write points to .geo file
            for i, vertex in enumerate(vertices):
                print(vertex)
                points[point_index] = f"Point({point_index}) = {{{vertex.X}, {vertex.Y}, {vertex.Z}, 1.0}};\n"
                vertex_map[i] = point_index
                point_index += 1

            # Write line loops and plane surfaces for each face
            for i in range(faces.Count):
                face = faces[i]

                if len(face) == 4:  # Quad face
                    face_indices = [face[0], face[1], face[2], face[3]]
                elif len(face) == 3:  # Triangle face
                    face_indices = [face[0], face[1], face[2]]
                else:
                    continue

                # Create line loops for the face
                line_loop_indices = []
                for j in range(len(face_indices)):
                    start_point = vertex_map[face_indices[j]]
                    end_point = vertex_map[face_indices[(j + 1) % len(face_indices)]]
                    lines[line_index] = f"Line({line_index}) = {{{start_point}, {end_point}}};\n"
                    line_loop_indices.append(line_index)
                    line_index += 1

                line_loops[
                    surface_index] = f"Line Loop({surface_index}) = {{{', '.join(map(str, line_loop_indices))}}};\n"
                plane_surfaces[surface_index] = f"Plane Surface({surface_index}) = {{{surface_index}}};\n"
                surface_index += 1

            # Write physical surface group
            physical_surfaces[
                obj.Attributes.Id] = f"Physical Surface(\"{obj.Attributes.Id}\") = {{{', '.join(map(str, range(1, surface_index)))}}};\n"
            physical_surface_counter += 1

    with open(geo_file_path, 'w') as geo_file:
        # Write sorted points
        for point_index in sorted(points.keys()):
            geo_file.write(points[point_index])

        # Write sorted lines
        for line_index in sorted(lines.keys()):
            geo_file.write(lines[line_index])

        # Write sorted line loops
        for line_loop_index in sorted(line_loops.keys()):
            geo_file.write(line_loops[line_loop_index])

        # Write sorted plane surfaces
        for surface_index in sorted(plane_surfaces.keys()):
            geo_file.write(plane_surfaces[surface_index])

        # Write sorted plane surfaces
        for pysical_index in sorted(physical_surfaces.keys()):
            geo_file.write(physical_surfaces[pysical_index])

    print(f"Converted {rhino_file_path} to {geo_file_path}")
    return geo_file_path


gmsh.initialize()


def generate_geo_file_using_gmsh(rhino_file_path, geo_file_path):
    try:
        file3dm = rhino3dm.File3dm()
        model = file3dm.Read(rhino_file_path)

        # Start defining the geometry
        model_geo = gmsh.model.geo

        points = {}
        lines = {}
        line_loops = {}
        plane_surfaces = {}
        physical_surfaces = {}

        point_index = 1
        line_index = 1
        surface_index = 1
        physical_surface_counter = 1

        # Iterate over the objects in the 3dm model
        for obj in model.Objects:
            if isinstance(obj.Geometry, rhino3dm.Mesh):
                faces = obj.Geometry.Faces
                faces.ConvertTrianglesToQuads(0.5, 0)
                vertices = obj.Geometry.Vertices
                vertices.CombineIdentical(True, True)

                # Define vertices as Gmsh points
                gmsh_points = []
                for vertex in vertices:
                    gmsh_point = model_geo.addPoint(vertex.X, vertex.Y, vertex.Z)
                    gmsh_points.append(gmsh_point)
                    points[point_index] = gmsh_point
                    point_index += 1

                # Define lines and line loops for each face
                for i in range(faces.Count):
                    face = faces[i]

                    if len(face) == 4:  # Quad face
                        face_indices = [face[0], face[1], face[2], face[3]]
                    elif len(face) == 3:  # Triangle face
                        face_indices = [face[0], face[1], face[2]]
                    else:
                        continue

                    # Define lines
                    gmsh_lines = []
                    for j in range(len(face_indices)):
                        start_point = gmsh_points[face_indices[j]]
                        end_point = gmsh_points[face_indices[(j + 1) % len(face_indices)]]
                        gmsh_line = model_geo.addLine(start_point, end_point)
                        gmsh_lines.append(gmsh_line)
                        lines[line_index] = gmsh_line
                        line_index += 1

                    # Define line loop and plane surface
                    line_loop = model_geo.addCurveLoop(gmsh_lines)
                    plane_surface = model_geo.addPlaneSurface([line_loop])
                    line_loops[surface_index] = line_loop
                    plane_surfaces[surface_index] = plane_surface
                    surface_index += 1

                # Define physical surface group
                physical_surface = model_geo.addPhysicalGroup(2, [plane_surfaces[surface_index] for surface_index in
                                                                  range(1, surface_index)])
                physical_surfaces[obj.Attributes.Id] = physical_surface
                physical_surface_counter += 1

        # Write the .geo file
        model_geo.synchronize()
        gmsh.write(f"{geo_file_path}_unrolled")

        print(f"Converted {rhino_file_path} to {geo_file_path}")
        return geo_file_path

    finally:
        gmsh.finalize()

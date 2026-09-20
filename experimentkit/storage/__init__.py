"""Project storage sync: DaVis projects on C: kept on a work drive and a backup drive.

Design and decisions: docs/design/storage-sync.md. Needs only the standard
library (daviskit, if installed, reads the .set files; OpenCV is not needed).

    from experimentkit.storage import registry, sync, volumes
    for project in registry.load_projects():
        results, status = sync.sync_project(project)
"""
